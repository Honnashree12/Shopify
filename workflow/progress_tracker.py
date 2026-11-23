"""
Lightweight, in-process publishing coordination primitives.

Phase 4 needs two small, additive capabilities that don't exist anywhere else
in the codebase yet:

1. Live "current stage" visibility while a folder workflow run is in
   progress. `active_sessions[session_id]` (in main.py) is only updated in
   bulk once the whole background run finishes, so today there is no way for
   `/status/{id}` to report which of ingest/validate/create/media/verify/
   report is actually executing right now. Each ADK tool in
   tools/folder_tools.py calls `set_stage()` as it starts; main.py's
   `get_status()` calls `get_stage()` to surface it.

2. A same-process publish lock preventing two concurrent publishing
   executions for the same session/product (double-click on Approve, a
   retried request racing the original, etc.). This is intentionally the
   smallest safe mechanism for a single-process deployment — an in-memory
   guarded set — not a new queue or external lock service, consistent with
   "do not introduce unnecessary infrastructure."

Both are plain in-memory dicts/sets behind a single lock each. They hold no
secrets and are safe to import from both main.py and tools/folder_tools.py
without creating a circular import (neither of those modules is imported
here).
"""

import threading
from typing import Dict, Optional, Set

_stage_guard = threading.Lock()
_current_stage: Dict[str, str] = {}

_publish_guard = threading.Lock()
_active_publishing_sessions: Set[str] = set()


def set_stage(session_id: Optional[str], stage: str) -> None:
    """Record the pipeline stage currently executing for a session."""
    if not session_id:
        return
    with _stage_guard:
        _current_stage[session_id] = stage


def get_stage(session_id: Optional[str]) -> Optional[str]:
    """Return the pipeline stage currently executing for a session, if any."""
    if not session_id:
        return None
    with _stage_guard:
        return _current_stage.get(session_id)


def clear_stage(session_id: Optional[str]) -> None:
    """Clear stage tracking once a run reaches a terminal state."""
    if not session_id:
        return
    with _stage_guard:
        _current_stage.pop(session_id, None)


def try_acquire_publish_lock(session_id: str) -> bool:
    """
    Atomically claim the right to run the publishing pipeline for this
    session. Returns False if another execution already holds it (e.g. a
    duplicate/near-simultaneous approve request) — the caller must not
    schedule a second background run in that case.
    """
    with _publish_guard:
        if session_id in _active_publishing_sessions:
            return False
        _active_publishing_sessions.add(session_id)
        return True


def release_publish_lock(session_id: Optional[str]) -> None:
    """Release the publish lock. Safe to call even if never acquired."""
    if not session_id:
        return
    with _publish_guard:
        _active_publishing_sessions.discard(session_id)


def is_publishing(session_id: Optional[str]) -> bool:
    if not session_id:
        return False
    with _publish_guard:
        return session_id in _active_publishing_sessions
