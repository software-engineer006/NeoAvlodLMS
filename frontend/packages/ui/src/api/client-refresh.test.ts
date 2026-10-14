import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClient } from "./client";

const unauthorized = () => Response.json({ detail: "Sessiya muddati tugagan" }, { status: 401 });
const ok = () => Response.json({ saved: true });

beforeEach(() => {
  document.cookie = "neoavlod_csrf=session-csrf; Path=/";
  localStorage.clear(); sessionStorage.clear();
});
afterEach(() => {
  document.cookie = "neoavlod_csrf=; Max-Age=0; Path=/";
  vi.unstubAllGlobals(); vi.restoreAllMocks();
});

describe("Seven-day session recovery", () => {
  it("downloads compressed audit with CSRF and recovers an expired session without JSON decoding", async () => {
    const binary = new Response("compressed-fixture", { headers: { "Content-Type": "application/gzip" } });
    const fetchMock = vi.fn().mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(new Response(null, { status: 204 })).mockResolvedValueOnce(binary);
    vi.stubGlobal("fetch", fetchMock);
    const result = await new ApiClient().get<Blob>("/api/v1/admin/logs/2026-10-14/download", { responseType: "blob" });
    expect(result.type).toBe("application/gzip");
    for (const index of [0, 3]) {
      const options = fetchMock.mock.calls[index][1] as RequestInit;
      expect(new Headers(options.headers).get("X-CSRF-Token")).toBe("session-csrf");
      expect(new Headers(options.headers).get("Accept")).toBe("application/gzip");
      expect(options.cache).toBe("no-store");
      expect(options).not.toHaveProperty("responseType");
    }
  });
  it.each(["draft", "finalize", "correct"])("refreshes and resends the exact teacher %s payload", async (action) => {
    const fetchMock = vi.fn().mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(new Response(null, { status: 204 })).mockResolvedValueOnce(ok());
    vi.stubGlobal("fetch", fetchMock);
    const path = `/api/v1/teacher/groups/group1/attendance/${action}`;
    const body = { date: "2026-10-13", items: [{ student_id: "student1", status: "absent", note: "Kasal" }] };
    expect(await new ApiClient().post(path, body)).toEqual({ saved: true });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      path, "/api/v1/auth/teacher/me", "/api/v1/auth/teacher/refresh", path,
    ]);
    const first = fetchMock.mock.calls[0][1] as RequestInit;
    const retried = fetchMock.mock.calls[3][1] as RequestInit;
    expect(retried.body).toBe(first.body);
    expect(retried.method).toBe("POST");
    const refresh = fetchMock.mock.calls[2][1] as RequestInit;
    expect(new Headers(refresh.headers).get("X-CSRF-Token")).toBe("session-csrf");
    expect(refresh.credentials).toBe("include");
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
  });

  it.each(["admin", "teacher"])("restores %s on reopening the portal with expired access", async (portal) => {
    const fetchMock = vi.fn().mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(new Response(null, { status: 204 })).mockResolvedValueOnce(Response.json({ role: portal }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await new ApiClient().get(`/api/v1/auth/${portal}/me`)).toEqual({ role: portal });
    expect(fetchMock.mock.calls[2][0]).toBe(`/api/v1/auth/${portal}/refresh`);
  });

  it("shares one refresh across concurrent API clients and delayed 401 responses", async () => {
    let accessValid = false;
    let requests = 0;
    const fetchMock = vi.fn(async (path: string) => {
      if (path.endsWith("/refresh")) { accessValid = true; return new Response(null, { status: 204 }); }
      if (path.endsWith("/me")) return accessValid ? ok() : unauthorized();
      requests++;
      return requests <= 2 ? unauthorized() : ok();
    });
    vi.stubGlobal("fetch", fetchMock);
    const a = new ApiClient(), b = new ApiClient();
    const results = await Promise.all([a.get("/api/v1/teacher/groups"), b.get("/api/v1/teacher/students/student1")]);
    expect(results).toEqual([{ saved: true }, { saved: true }]);
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/refresh"))).toHaveLength(1);
    fetchMock.mockResolvedValueOnce(unauthorized());
    expect(await a.get("/api/v1/teacher/groups")).toEqual({ saved: true });
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/refresh"))).toHaveLength(1);
  });

  it("coordinates two tabs with a Web Lock and checks cookies after acquiring it", async () => {
    const pendingLocks = new Map<string, Promise<unknown>>();
    const locks = { request: vi.fn(async (name: string, callback: () => Promise<void>) => {
      const previous = pendingLocks.get(name) || Promise.resolve();
      const next = previous.then(callback);
      pendingLocks.set(name, next);
      await next;
    }) };
    vi.stubGlobal("navigator", { locks });
    // Independently loaded modules have independent in-tab refresh flights.
    vi.resetModules();
    const TabA = (await import("./client")).ApiClient;
    vi.resetModules();
    const TabB = (await import("./client")).ApiClient;
    let valid = false;
    let originalRequests = 0;
    const fetchMock = vi.fn(async (path: string) => {
      if (path.endsWith("/refresh")) { valid = true; return new Response(null, { status: 204 }); }
      if (path.endsWith("/me")) return valid ? ok() : unauthorized();
      originalRequests++;
      return originalRequests <= 2 ? unauthorized() : ok();
    });
    vi.stubGlobal("fetch", fetchMock);
    const results = await Promise.all([
      new TabA().get("/api/v1/teacher/groups"), new TabB().get("/api/v1/teacher/groups"),
    ]);
    expect(results).toHaveLength(2);
    expect(locks.request).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/refresh"))).toHaveLength(1);
  });

  it.each(["login", "login/confirm", "password/reset", "password/reset/confirm", "logout", "refresh"])(
    "does not retry a rejected auth %s request", async (action) => {
      const fetchMock = vi.fn().mockResolvedValue(unauthorized());
      vi.stubGlobal("fetch", fetchMock);
      await expect(new ApiClient().post(`/api/v1/auth/teacher/${action}`, {})).rejects.toMatchObject({ status: 401 });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    },
  );

  it("does not retry permission errors or loop when refresh/renewed access is invalid", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(Response.json({ detail: "Ruxsat yo‘q" }, { status: 403 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(new ApiClient().get("/api/v1/teacher/groups")).rejects.toMatchObject({ status: 403 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fetchMock.mockReset().mockResolvedValue(unauthorized());
    await expect(new ApiClient().get("/api/v1/teacher/groups")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(3); // request, current-cookie probe, refresh
    fetchMock.mockReset().mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(new Response(null, { status: 204 })).mockResolvedValueOnce(unauthorized());
    await expect(new ApiClient().get("/api/v1/teacher/groups")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });
});
