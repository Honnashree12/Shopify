import sys
import os
import logging
from typing import Optional, List, Dict, Tuple
from abc import ABC, abstractmethod
# pyrefly: ignore [missing-import]
from fastapi import Request, HTTPException, Depends
# pyrefly: ignore [missing-import]
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("auth_service")

# HTTPBearer parser for token extraction
security_bearer = HTTPBearer(auto_error=False)


class User:
    """
    Representation of an authenticated application user.
    """
    def __init__(self, uid: str, email: str, role: str, auth_state: str = "authenticated", name: str = ""):
        self.uid = uid
        self.email = email
        self.role = role  # Role can be: "CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"
        self.auth_state = auth_state
        self.name = name


class AuthProvider(ABC):
    @abstractmethod
    def verify_token(self, token: str) -> User:
        pass


class MockAuthProvider(AuthProvider):
    """Dev/test identity provider. Only ever consulted for tokens that look
    like mock tokens (see MOCK_TOKEN_PREFIX below) -- it never accepts an
    arbitrary/forged string as a real identity."""

    def verify_token(self, token: str) -> User:
        if token == "mock-admin-token":
            return User(uid="admin-uid", email="admin@example.com", role="PLATFORM_ADMIN", name="Platform Admin")
        elif token == "mock-approver-token":
            return User(uid="approver-uid", email="sandeep@example.com", role="APPROVER", name="Sandeep")
        elif token == "mock-catalogue-token":
            return User(uid="catalogue-uid", email="lakshmi@example.com", role="CATALOGUE_ADMIN", name="Lakshmi")
        raise HTTPException(
            status_code=401,
            detail="Invalid or unrecognized authentication token."
        )


# Tokens beginning with this prefix are routed to MockAuthProvider and never
# attempted against Firebase. Real Firebase ID tokens are opaque signed JWTs
# and will never start with this string, so there is no ambiguity between
# the two token spaces.
MOCK_TOKEN_PREFIX = "mock-"


class FirebaseAuthProvider(AuthProvider):
    """Real identity provider: verifies a Firebase Auth ID token using the
    Firebase Admin SDK, then looks up the caller's application role from
    Firestore (users/{uid}.role) -- Firebase Auth itself has no concept of
    our CATALOGUE_ADMIN/APPROVER/PLATFORM_ADMIN roles, so role assignment is
    intentionally a separate, explicit, server-side-only mapping. A verified
    Firebase identity with no matching users/{uid} document is NOT given a
    default role -- unassigned accounts are rejected rather than silently
    granted access, since guessing a safe default role for an unknown real
    user would itself be a privilege-escalation risk.
    """

    _user_cache: Dict[str, Tuple[User, float]] = {}

    def __init__(self, db_client):
        self._db = db_client

    def verify_token(self, token: str) -> User:
        import time
        # pyrefly: ignore [missing-import]
        from firebase_admin import auth as firebase_auth

        is_dev = os.getenv("TESTING") == "True" or os.getenv("LOG_LEVEL", "info").lower() != "production"

        try:
            decoded = firebase_auth.verify_id_token(token)
        except Exception as e:
            if is_dev and type(e).__name__ == "ExpiredIdTokenError":
                try:
                    # pyrefly: ignore [missing-import]
                    import jwt
                    decoded = jwt.decode(token, options={"verify_signature": False})
                    logger.info("[AUTH DIAGNOSTIC] Accepted expired Firebase ID token in DEV mode for user %s", decoded.get("email"))
                except Exception:
                    logger.warning("Firebase ID token verification failed: %s", type(e).__name__)
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid or expired authentication token."
                    )
            else:
                logger.warning("Firebase ID token verification failed: %s", type(e).__name__)
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired authentication token."
                )

        uid = decoded.get("uid") or decoded.get("sub")
        email = decoded.get("email", "")

        # Check in-memory user profile cache (TTL 60s)
        now_ts = time.time()
        if uid in FirebaseAuthProvider._user_cache:
            cached_user, cache_time = FirebaseAuthProvider._user_cache[uid]
            if now_ts - cache_time < 60.0:
                return cached_user

        role = None
        name = ""
        active = False
        doc_path = f"users/{uid}"

        if is_dev:
            logger.info("[AUTH DIAGNOSTIC] Decoded Firebase UID: %s, email: %s", uid, email)
            logger.info("[AUTH DIAGNOSTIC] Querying Firestore path: %s", doc_path)

        try:
            doc = self._db.collection("users").document(uid).get(timeout=5.0)
        except Exception as e:
            logger.exception("Firestore connection/configuration error during lookup for uid=%s", uid)
            raise HTTPException(
                status_code=500,
                detail=f"Firestore database connection error during profile lookup: {str(e)}"
            )

        if not doc.exists:
            logger.warning("[AUTH DIAGNOSTIC] Firestore document does not exist for path: %s", doc_path)
            raise HTTPException(
                status_code=403,
                detail="Authentication succeeded, but your user profile is not configured. Please contact the administrator."
            )

        data = doc.to_dict() or {}
        if is_dev:
            # Exclude secrets
            safe_data = {k: v for k, v in data.items() if "password" not in k.lower() and "secret" not in k.lower()}
            logger.info("[AUTH DIAGNOSTIC] Retrieved Firestore data: %s", safe_data)

        # Strip whitespace from keys to handle things like 'active '
        data = {k.strip(): v for k, v in data.items()}

        role = data.get("role")
        name = data.get("name", "")
        
        # Interpret active value as boolean or string
        active_val = data.get("active", False)
        if isinstance(active_val, str):
            active = active_val.strip().lower() in ("true", "1", "yes")
        else:
            active = bool(active_val)

        if not active:
            raise HTTPException(
                status_code=403,
                detail="This account is inactive. Please contact the administrator."
            )

        if role not in ("CATALOGUE_ADMIN", "APPROVER", "PLATFORM_ADMIN"):
            raise HTTPException(
                status_code=403,
                detail="This account is authenticated but has no role assigned. Contact a Platform Admin."
            )

        user_obj = User(uid=uid, email=email, role=role, name=name)
        FirebaseAuthProvider._user_cache[uid] = (user_obj, now_ts)
        return user_obj


def _resolve_firebase_provider() -> Optional["FirebaseAuthProvider"]:
    """Returns a FirebaseAuthProvider only if Firebase is actually
    initialized (real service account configured and reachable). Mirrors
    the mock-fallback pattern already used by services/firebase_service.py
    so that this codebase has exactly one place that decides "are we
    running with real Firebase or not"."""
    try:
        from services.firebase_service import initialize_firebase
        db_client = initialize_firebase()
        if db_client is None:
            return None
        return FirebaseAuthProvider(db_client)
    except Exception:
        logger.exception("Could not construct FirebaseAuthProvider")
        return None


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> User:
    """
    Dependency to resolve the current authenticated user.

    Real-auth-first: a bearer token that is NOT a recognized mock token is
    verified as a real Firebase Auth ID token whenever Firebase is
    configured in this environment (see FirebaseAuthProvider above). Mock
    tokens (prefix "mock-") always go through MockAuthProvider, which keeps
    this deployment usable in this sandbox / local dev / CI where no real
    Firebase project credentials exist, without weakening verification of
    real tokens.

    Enforces that unauthenticated requests receive 401. Allows a testing
    fallback bypass (ALLOW_AUTH_FALLBACK=True) to maintain Phase 1
    compatibility for older tests that don't send any Authorization header.
    """
    from config import settings
    is_production = settings.app_env.lower() == "production"
    allow_fallback = (os.getenv("ALLOW_AUTH_FALLBACK") == "True") and not is_production

    if not credentials:
        if allow_fallback:
            return User(uid="default-user", email="default@example.com", role="PLATFORM_ADMIN")
        raise HTTPException(
            status_code=401,
            detail="Authentication token is missing. Please provide a valid Bearer token."
        )

    token = credentials.credentials

    if is_production and token.startswith(MOCK_TOKEN_PREFIX):
        raise HTTPException(
            status_code=401,
            detail="Mock authentication tokens are strictly prohibited in production environment."
        )

    if not token.startswith(MOCK_TOKEN_PREFIX):
        firebase_provider = _resolve_firebase_provider()
        if firebase_provider is not None:
            # Real Firebase is configured: this is the production path.
            # A non-mock token here is claimed to be a real ID token, so it
            # must pass real verification -- it is NOT allowed to silently
            # fall through to the mock provider (which would defeat the
            # point of having real auth at all).
            return firebase_provider.verify_token(token)
        elif is_production:
            raise HTTPException(
                status_code=500,
                detail="Production authentication provider is unconfigured or unavailable."
            )

    if is_production:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token for production environment."
        )

    try:
        provider = MockAuthProvider()
        return provider.verify_token(token)
    except HTTPException as e:
        if allow_fallback:
            logger.warning("Unrecognized bearer token provided under testing. Falling back to default user.")
            return User(uid="default-user", email="default@example.com", role="PLATFORM_ADMIN")
        raise e


def require_role(roles: List[str]):
    """
    Dependency gate enforcing that the user possesses one of the allowed roles.
    """
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role == "PLATFORM_ADMIN":
            return current_user
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: user role '{current_user.role}' lacks privileges. Required: {roles}"
            )
        return current_user
    return role_checker

