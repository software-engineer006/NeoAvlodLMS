import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../../api/client";
import { LoginForm } from "../LoginForm";
import { PasswordRecoveryModal } from "../PasswordRecoveryModal";

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-13T12:00:00Z"));
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe.each(["admin", "teacher"] as const)("%s OTP deadline", (portal) => {
  it.each(["login", "reset"])("%s shows 3 minutes and stops at the server deadline", async (flow) => {
    vi.spyOn(apiClient, "post").mockResolvedValue({
      challenge_id: "test-challenge", expires_at: new Date(Date.now() + 180000).toISOString(),
    });
    if (flow === "login") render(<LoginForm portal={portal} onSuccess={vi.fn()} />);
    else render(<PasswordRecoveryModal isOpen portal={portal} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Foydalanuvchi nomi/i), { target: { value: "teacher" } });
    if (flow === "login") fireEvent.change(screen.getByLabelText(/Parol/i), { target: { value: "Password123" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: flow === "login" ? /^Kirish$/i : /Kodni yuborish/i })); });
    expect(screen.getByText("03:00")).toBeDefined();
    fireEvent.change(screen.getByLabelText(/Tasdiqlash kodi/i), { target: { value: "123456" } });
    const button = screen.getByRole("button", { name: flow === "login" ? /^Tasdiqlash$/i : /Parolni yangilash/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    act(() => { vi.advanceTimersByTime(179000); });
    expect(screen.getByText("00:01")).toBeDefined();
    expect(button.disabled).toBe(false);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByText("00:00")).toBeDefined();
    expect(button.disabled).toBe(true);
  });

  it.each(["login", "reset"])("%s keeps an already expired response expired", async (flow) => {
    vi.spyOn(apiClient, "post").mockResolvedValue({ challenge_id: "old", expires_at: new Date(Date.now() - 1000).toISOString() });
    if (flow === "login") render(<LoginForm portal={portal} onSuccess={vi.fn()} />);
    else render(<PasswordRecoveryModal isOpen portal={portal} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Foydalanuvchi nomi/i), { target: { value: "teacher" } });
    if (flow === "login") fireEvent.change(screen.getByLabelText(/Parol/i), { target: { value: "Password123" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: flow === "login" ? /^Kirish$/i : /Kodni yuborish/i })); });
    expect(screen.getByText("00:00")).toBeDefined();
    expect(screen.queryByText("03:00")).toBeNull();
    expect((screen.getByLabelText(/Tasdiqlash kodi/i) as HTMLInputElement).disabled).toBe(true);
  });
});
