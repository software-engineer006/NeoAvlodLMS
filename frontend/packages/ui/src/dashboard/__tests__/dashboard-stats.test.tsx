import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DashboardStatsCards } from "../DashboardStatsCards";
import { apiClient } from "../../api/client";
import type { DashboardStats } from "../../api/types";

vi.mock("../../api/client", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

describe("DashboardStatsCards Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all three cards with counts and badges for full stats", async () => {
    const mockData: DashboardStats = {
      groups_count: 12,
      students_count: 145,
      staff_count: 18,
      staff_breakdown: {
        teachers: 14,
        admins: 3,
        superadmins: 1,
      },
    };

    vi.mocked(apiClient.get).mockResolvedValueOnce(mockData);

    const onNavigate = vi.fn();
    render(<DashboardStatsCards onNavigate={onNavigate} />);

    await waitFor(() => {
      expect(screen.getByText("Asosiy ko‘rsatkichlar")).toBeDefined();
    });

    // Check groups card
    expect(screen.getByText("Guruhlar")).toBeDefined();
    expect(screen.getByText("12")).toBeDefined();
    expect(screen.getByText("Tizimdagi barcha faol o‘quv guruhlari soni")).toBeDefined();

    // Check students card
    expect(screen.getByText("O‘quvchilar")).toBeDefined();
    expect(screen.getByText("145")).toBeDefined();
    expect(screen.getByText("Tizimda ta’lim olayotgan faol o‘quvchilar soni")).toBeDefined();

    // Check staff card
    expect(screen.getByText("Xodimlar")).toBeDefined();
    expect(screen.getByText("18")).toBeDefined();
    expect(
      screen.getByText("14 ta o‘qituvchi, 3 ta admin, 1 ta superadmin")
    ).toBeDefined();

    // Verify navigation clicks
    fireEvent.click(screen.getByText("Guruhlarni ko‘rish"));
    expect(onNavigate).toHaveBeenCalledWith("groups");

    fireEvent.click(screen.getByText("O‘quvchilarni ko‘rish"));
    expect(onNavigate).toHaveBeenCalledWith("students");

    fireEvent.click(screen.getByText("Xodimlarni boshqarish"));
    expect(onNavigate).toHaveBeenCalledWith("staff");
  });

  it("renders only permitted cards when non-permitted counts are null", async () => {
    const mockData: DashboardStats = {
      groups_count: null,
      students_count: 42,
      staff_count: null,
      staff_breakdown: null,
    };

    vi.mocked(apiClient.get).mockResolvedValueOnce(mockData);

    render(<DashboardStatsCards />);

    await waitFor(() => {
      expect(screen.getByText("42")).toBeDefined();
    });

    expect(screen.getByText("O‘quvchilar")).toBeDefined();
    expect(screen.queryByText("Guruhlar")).toBeNull();
    expect(screen.queryByText("Xodimlar")).toBeNull();
  });

  it("shows restricted notice when all counts are null", async () => {
    const mockData: DashboardStats = {
      groups_count: null,
      students_count: null,
      staff_count: null,
      staff_breakdown: null,
    };

    vi.mocked(apiClient.get).mockResolvedValueOnce(mockData);

    render(<DashboardStatsCards />);

    await waitFor(() => {
      expect(
        screen.getByText(/Ushbu hisob uchun statistik ko‘rsatkichlar ruxsati berilmagan/i)
      ).toBeDefined();
    });
  });

  it("handles error state and allows retry", async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error("Tarmoq xatosi"));

    render(<DashboardStatsCards />);

    await waitFor(() => {
      expect(screen.getByText("Statistika yuklanmadi")).toBeDefined();
    });

    const mockData: DashboardStats = {
      groups_count: 5,
      students_count: 30,
      staff_count: 4,
      staff_breakdown: { teachers: 3, admins: 1, superadmins: 0 },
    };
    vi.mocked(apiClient.get).mockResolvedValueOnce(mockData);

    const retryBtn = screen.getByRole("button", { name: /Qayta urinish/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText("5")).toBeDefined();
    });
  });
});
