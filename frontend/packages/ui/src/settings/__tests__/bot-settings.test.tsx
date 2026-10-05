import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BotSettingsView } from "../BotSettingsView";
import type { CurrentUser } from "../../api/types";
import type { BotSettingsItem } from "../types";
import { apiClient } from "../../api/client";

describe("Superadmin Bot Settings (Task 033)", () => {
  const superadminUser: CurrentUser = {
    id: "sa-1",
    username: "superowner",
    first_name: "Asad",
    last_name: "Karimov",
    phone: "+998901112233",
    role: "superadmin",
    status: "active",
    permissions: [],
  };

  const regularAdminUser: CurrentUser = {
    id: "ad-1",
    username: "regular_admin",
    first_name: "Bobur",
    last_name: "Aliyev",
    phone: "+998902223344",
    role: "admin",
    status: "active",
    permissions: ["staff:manage", "students:read"],
  };

  const sampleBotSettings: BotSettingsItem = {
    configured: true,
    bot_username: "neoavlod_lms_bot",
    version: 3,
    active_version: 3,
    last_error: null,
    reload_in_progress: false,
  };

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("strictly forbids regular admin and teacher from accessing bot settings", () => {
    const getSpy = vi.spyOn(apiClient, "get");

    render(<BotSettingsView currentUser={regularAdminUser} />);

    // Shows 403 alert
    expect(screen.getByText(/403 Forbidden/)).toBeDefined();
    expect(screen.getByText(/Telegram bot sozlamalarini faqat Bosh administrator/)).toBeDefined();

    // No API calls made
    expect(getSpy).not.toHaveBeenCalled();
  });

  it("loads and displays bot status, username, version and masked preview for superadmin", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(sampleBotSettings);

    render(<BotSettingsView currentUser={superadminUser} />);

    await waitFor(() => {
      expect(screen.getByText("Telegram Bot sozlamalari")).toBeDefined();
      expect(screen.getByText("@neoavlod_lms_bot")).toBeDefined();
      expect(screen.getByText("Sozlangan")).toBeDefined();
      expect(screen.getByText("Sinxronlashtirilgan")).toBeDefined();
      expect(screen.getAllByText(/v3/).length).toBeGreaterThanOrEqual(1);
    });

    // Masked token preview
    expect(screen.getByText("••••••••••••••••••••••••••••••••••••••••")).toBeDefined();

    // Strict security assertion
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("toggles password masking and updates bot token via confirmation modal", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(sampleBotSettings);
    const postSpy = vi.spyOn(apiClient, "post").mockResolvedValue({
      ...sampleBotSettings,
      version: 4,
      reload_in_progress: true,
    });

    render(<BotSettingsView currentUser={superadminUser} />);

    await waitFor(() => {
      expect(screen.getByText("Telegram Bot sozlamalari")).toBeDefined();
    });

    const tokenInput = screen.getByLabelText(/Yangi Bot Tokeni/) as HTMLInputElement;
    expect(tokenInput.type).toBe("password");

    // Toggle visibility
    const eyeBtn = screen.getByLabelText("Tokenni ko‘rsatish");
    fireEvent.click(eyeBtn);
    expect(tokenInput.type).toBe("text");

    // Type new token
    fireEvent.change(tokenInput, { target: { value: "987654321:NEW_BOT_TOKEN_SECRET" } });

    // Submit form -> opens confirmation modal
    const saveBtn = screen.getByRole("button", { name: "Tokenni saqlash va yangilash" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByText("Bot tokenini yangilash tasdig‘i")).toBeDefined();
    });

    // Confirm in modal
    const confirmBtn = screen.getByRole("button", { name: "Tasdiqlash va saqlash" });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith("/api/v1/admin/settings/bot", {
        token: "987654321:NEW_BOT_TOKEN_SECRET",
      });
      expect(screen.getByText(/Bot tokeni muvaffaqiyatli yangilandi/)).toBeDefined();
    });

    // Still 0 secrets in localStorage or sessionStorage
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("displays reload in progress and last error when reported", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({
      ...sampleBotSettings,
      reload_in_progress: true,
      last_error: "Telegram API Error 401: Unauthorized bot token",
    });

    render(<BotSettingsView currentUser={superadminUser} />);

    await waitFor(() => {
      expect(screen.getByText(/Qayta yuklanmoqda.../)).toBeDefined();
      expect(screen.getByText("Telegram API Error 401: Unauthorized bot token")).toBeDefined();
    });
  });
});
