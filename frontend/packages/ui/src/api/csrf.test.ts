import { afterEach, expect, it, vi } from "vitest";
import { ApiClient } from "./client";

afterEach(() => {
  document.cookie = "neoavlod_csrf=; Max-Age=0; Path=/";
  vi.unstubAllGlobals();
});

it("sends the backend session CSRF cookie on mutations", async () => {
  document.cookie = "neoavlod_csrf=server-issued-token; Path=/";
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
  await new ApiClient().post("/api/v1/teacher/groups/example/attendance/draft", {});
  const options = fetchMock.mock.calls[0][1] as RequestInit;
  expect(new Headers(options.headers).get("X-CSRF-Token")).toBe("server-issued-token");
  expect(options.credentials).toBe("include");
});
