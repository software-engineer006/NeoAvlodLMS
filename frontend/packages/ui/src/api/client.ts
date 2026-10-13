import { getCsrfToken } from "./csrf";
import { ApiError } from "./errors";
import type { ApiErrorPayload, ApiValidationError, PortalType, RequestOptions } from "./types";

// Share one rotation across API client instances in this tab. Web Locks also
// serialize rotations in other tabs sharing the same host-only cookies.
const refreshFlights = new Map<string, Promise<void>>();

function protectedPortal(path: string): PortalType | null {
  const route = (path.startsWith("/") ? path : `/${path}`).split("?")[0];
  const portalRoute = route.match(/^\/api\/v1\/(admin|teacher)(?:\/|$)/);
  if (portalRoute) return portalRoute[1] as PortalType;
  const authRoute = route.match(/^\/api\/v1\/auth\/(admin|teacher)\/(me|profile|avatar|password\/change)$/);
  return authRoute ? authRoute[1] as PortalType : null;
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = "") {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private buildUrl(path: string, params?: Record<string, string | number | boolean | undefined | null>): string {
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    const full = `${this.baseUrl}${cleanPath}`;
    if (!params) {
      return full;
    }
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        search.append(key, String(value));
      }
    }
    const query = search.toString();
    return query ? `${full}?${query}` : full;
  }

  private async renewSession(portal: PortalType): Promise<void> {
    const key = `${this.baseUrl || (typeof window !== "undefined" ? window.location.origin : "")}/${portal}`;
    const existing = refreshFlights.get(key);
    if (existing) return existing;

    const renew = async () => {
      // A delayed 401 may belong to an access token another request/tab already
      // renewed. Check the current browser cookie before rotating it again.
      const profile = await fetch(this.buildUrl(`/api/v1/auth/${portal}/me`), {
        credentials: "include", headers: { Accept: "application/json" }, cache: "no-store",
      });
      if (profile.ok) return;
      if (profile.status !== 401) await this.decodeResponse(profile);
      const csrf = getCsrfToken();
      if (!csrf) throw new ApiError(401, "Tizimga kiring");
      const response = await fetch(this.buildUrl(`/api/v1/auth/${portal}/refresh`), {
        method: "POST", credentials: "include",
        headers: { Accept: "application/json", "X-CSRF-Token": csrf },
      });
      await this.decodeResponse(response);
    };
    const flight = (async () => {
      if (typeof navigator !== "undefined" && navigator.locks) {
        await navigator.locks.request(`neoavlod:session-refresh:${key}`, renew);
      } else {
        await renew();
      }
    })().finally(() => { refreshFlights.delete(key); });
    refreshFlights.set(key, flight);
    return flight;
  }

  public async request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
    const { params, body, headers = {}, ...rest } = options;
    const url = this.buildUrl(path, params);
    const method = (options.method || "GET").toUpperCase();

    const reqHeaders = new Headers(headers);
    if (!reqHeaders.has("Accept")) {
      reqHeaders.set("Accept", "application/json");
    }

    // Attach CSRF token on mutating requests
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      const csrf = getCsrfToken();
      if (csrf && !reqHeaders.has("X-CSRF-Token")) {
        reqHeaders.set("X-CSRF-Token", csrf);
      }
    }

    let reqBody: BodyInit | undefined;
    if (body !== undefined && body !== null) {
      if (body instanceof FormData || body instanceof URLSearchParams || typeof body === "string") {
        reqBody = body as BodyInit;
      } else {
        if (!reqHeaders.has("Content-Type")) {
          reqHeaders.set("Content-Type", "application/json");
        }
        reqBody = JSON.stringify(body);
      }
    }

    const send = () => fetch(url, {
      ...rest, method, headers: reqHeaders,
      credentials: options.credentials || "include", cache: options.cache || "no-store", body: reqBody,
    });
    let response = await send();
    const portal = protectedPortal(path);
    if (response.status === 401 && portal && options.credentials !== "omit" && !options.signal?.aborted) {
      await this.renewSession(portal);
      // The backend rejects expired access before running the mutation, so the
      // same attendance payload can be sent once more without losing edits.
      const csrf = getCsrfToken();
      if (csrf && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
        reqHeaders.set("X-CSRF-Token", csrf);
      }
      response = await send();
    }
    return this.decodeResponse<T>(response);
  }

  private async decodeResponse<T = unknown>(response: Response): Promise<T> {
    if (!response.ok) {
      let detail = `Server xatosi (${response.status})`;
      let errors: ApiValidationError[] | undefined;

      try {
        const payload: ApiErrorPayload = await response.clone().json();
        if (typeof payload?.detail === "string") {
          detail = payload.detail;
        } else if (Array.isArray(payload?.detail)) {
          errors = payload.detail;
          detail = errors.map((e) => e.msg).join(", ") || detail;
        }
      } catch {
        // non-JSON error response
        const text = await response.text().catch(() => "");
        if (text) {
          detail = text.slice(0, 300);
        }
      }

      throw new ApiError(response.status, detail, errors);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  }

  public get<T = unknown>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: "GET" });
  }

  public post<T = unknown>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: "POST", body });
  }

  public put<T = unknown>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: "PUT", body });
  }

  public patch<T = unknown>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: "PATCH", body });
  }

  public delete<T = unknown>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(path, { ...options, method: "DELETE" });
  }
}

export const apiClient = new ApiClient();
