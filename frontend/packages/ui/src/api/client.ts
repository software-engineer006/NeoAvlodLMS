import { getCsrfToken } from "./csrf";
import { ApiError } from "./errors";
import type { ApiErrorPayload, ApiValidationError, RequestOptions } from "./types";

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

    const response = await fetch(url, {
      ...rest,
      method,
      headers: reqHeaders,
      credentials: options.credentials || "include",
      body: reqBody,
    });

    if (!response.ok) {
      let detail = `Server xatosi (${response.status})`;
      let errors: ApiValidationError[] | undefined;

      try {
        const payload: ApiErrorPayload = await response.json();
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
