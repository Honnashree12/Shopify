import type { LaunchSummary, ProductLaunchState } from "./types";

export const BASE: string = (import.meta as any).env?.VITE_API_BASE_URL || "";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let authToken = "";
let onUnauthorizedCallback: (() => void) | null = null;

export function setClientAuthToken(token: string) {
  authToken = token;
}

export function registerUnauthorizedCallback(cb: () => void) {
  onUnauthorizedCallback = cb;
}

export function getAuthToken(): string {
  if (!authToken) {
    const savedKey = localStorage.getItem("mock_user_key");
    if (savedKey === "catalogue") return "mock-catalogue-token";
    if (savedKey === "approver") return "mock-approver-token";
    if (savedKey === "admin") return "mock-admin-token";
    return "mock-catalogue-token"; // Default fallback for dev
  }
  return authToken;
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore — no JSON body
    }
    if (res.status === 401) {
      setClientAuthToken("");
      localStorage.removeItem("mock_user_key");
      if (onUnauthorizedCallback) {
        onUnauthorizedCallback();
      } else {
        if (typeof window !== "undefined" && window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      }
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const getHeaders = (): Record<string, string> => {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

const getAuthHeadersOnly = (): Record<string, string> => {
  const token = getAuthToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
};

export const api = {
  health: () => fetch(`${BASE}/health`).then((r) => asJson<{ status: string; adk_ready: boolean; runner: boolean }>(r)),
  
  getMe: () =>
    fetch(`${BASE}/api/auth/me`, {
      headers: getHeaders(),
    }).then((r) => asJson<{ uid: string; email: string; role: "CATALOGUE_ADMIN" | "APPROVER" | "PLATFORM_ADMIN"; name: string }>(r)),

  listLaunches: async (): Promise<LaunchSummary[]> => {
    try {
      const res = await fetch(`${BASE}/api/launches`, {
        headers: getHeaders(),
      });
      if (!res.ok) return [];
      return await asJson<LaunchSummary[]>(res);
    } catch {
      return [];
    }
  },

  getStatus: (sessionId: string) =>
    fetch(`${BASE}/status/${sessionId}`, {
      headers: getHeaders(),
    }).then((r) => asJson<ProductLaunchState>(r)),

  launchFolder: (files: File[], preview: boolean) => {
    const form = new FormData();
    for (const f of files) {
      const relPath = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
      form.append("files", f, relPath);
    }
    form.append("preview", String(preview));
    return fetch(`${BASE}/launch-folder`, {
      method: "POST",
      headers: getAuthHeadersOnly(),
      body: form
    }).then((r) => asJson<{ session_id: string; status: string; message: string }>(r));
  },

  approveFolderLaunch: (
    sessionId: string,
    payload: {
      product_name?: string;
      product_description?: string;
      product_price?: number;
      sku?: string;
      inventory_quantity?: number;
      duplicate_action?: string;
      approved_to_publish: boolean;
    }
  ) =>
    fetch(`${BASE}/api/folder-launch/${sessionId}/approve`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify(payload),
    }).then((r) => asJson<{ session_id: string; status: string; message: string }>(r)),

  submitProduct: (id: string) =>
    fetch(`${BASE}/api/products/${id}/submit`, {
      method: "POST",
      headers: getHeaders(),
    }).then((r) => asJson<any>(r)),

  requestProductChanges: (id: string, comment: string) =>
    fetch(`${BASE}/api/products/${id}/request-changes`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ comment }),
    }).then((r) => asJson<any>(r)),

  approveProduct: (id: string) =>
    fetch(`${BASE}/api/products/${id}/approve`, {
      method: "POST",
      headers: getHeaders(),
    }).then((r) => asJson<any>(r)),

  updateProduct: (id: string, payload: any) =>
    fetch(`${BASE}/api/products/${id}`, {
      method: "PATCH",
      headers: getHeaders(),
      body: JSON.stringify(payload),
    }).then((r) => asJson<any>(r)),

  // Platform Admin only -- resumes a technically-failed publishing run.
  // Distinct from approveProduct/approveFolderLaunch: retry never grants a
  // new approval, it only re-runs an already-approved workflow, and it's
  // refused if the approval on record is missing or stale (backend re-checks
  // this independently; see POST /api/products/{id}/retry in main.py).
  retryProduct: (id: string) =>
    fetch(`${BASE}/api/products/${id}/retry`, {
      method: "POST",
      headers: getHeaders(),
    }).then((r) => asJson<{ session_id: string; status: string; message: string }>(r)),

  getAuditLogs: () =>
    fetch(`${BASE}/api/audit-logs`, {
      headers: getHeaders(),
    }).then((r) => asJson<Array<Record<string, unknown>>>(r)),
};

export { ApiError };

