import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { AuthProvider, useAuth } from "../AuthContext";
import { apiClient } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { CurrentUser } from "../../api/types";
const user: CurrentUser = { id: "admin", username: "namuna", first_name: "Namuna", last_name: null,
  phone: null, role: "admin", status: "active", permissions: ["messages:send"] };
function Probe() {
  const auth = useAuth(); const [draft, setDraft] = useState("");
  return <><p>{auth.isLoading ? "Loading" : auth.user ? auth.user.permissions.length ? "Granted" : "Revoked" : "Login"}</p>
    <input aria-label="Qoralama" value={draft} onChange={(event) => setDraft(event.target.value)} /></>;
}
afterEach(() => vi.restoreAllMocks());
it("updates grants on refocus without unmounting or clearing the draft", async () => {
  const get = vi.spyOn(apiClient, "get").mockResolvedValue(user);
  render(<AuthProvider portal="admin"><Probe /></AuthProvider>);
  await screen.findByText("Granted");
  fireEvent.change(screen.getByLabelText("Qoralama"), { target: { value: "Saqlanishi kerak" } });
  get.mockResolvedValue({ ...user, permissions: [] });
  fireEvent(window, new Event("focus")); await screen.findByText("Revoked");
  expect((screen.getByLabelText("Qoralama") as HTMLInputElement).value).toBe("Saqlanishi kerak");
  get.mockRejectedValue(new ApiError(401, "Session revoked"));
  fireEvent(window, new Event("focus")); await screen.findByText("Login");
});
it("does not log out an active account merely because the network briefly fails", async () => {
  const get = vi.spyOn(apiClient, "get").mockResolvedValue(user);
  render(<AuthProvider portal="teacher"><Probe /></AuthProvider>);
  await screen.findByText("Granted");
  get.mockRejectedValue(new ApiError(503, "Unavailable"));
  fireEvent(window, new Event("focus"));
  expect(screen.getByText("Granted")).toBeDefined();
});
