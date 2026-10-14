import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { CurrentUser } from "../../api/types";
import { AdminGuideView as GuideView } from "../AdminGuideView";
import { adminTopics } from "../adminTopics";
import { visibleGuideTopics } from "../types";
import { PERMISSIONS } from "../../navigation/permissions";

const user: CurrentUser = {
  id: "admin",
  username: "admin",
  first_name: "Namuna",
  last_name: null,
  phone: null,
  role: "admin",
  status: "active",
  permissions: [],
};
const common = [
  "admin-login",
  "admin-otp",
  "admin-dashboard",
  "admin-profile",
  "admin-password",
];
const expected: Record<string, string[]> = {
  "staff:manage": ["admin-staff"],
  "subjects:manage": ["admin-subjects"],
  "groups:read": ["admin-groups"],
  "groups:create": ["admin-groups", "admin-group-create"],
  "groups:edit": ["admin-groups", "admin-group-edit"],
  "students:read": ["admin-students"],
  "students:create": ["admin-students", "admin-student-create"],
  "students:edit": ["admin-students", "admin-student-edit"],
  "attendance:read": ["admin-history"],
  "attendance:write": [
    "admin-history",
    "admin-attendance",
    "admin-correction",
  ],
  "messages:send": ["admin-messages", "admin-delivery"],
};

describe("Ruxsatga mos admin qo‘llanmasi", () => {
  it.each(Object.entries(expected))(
    "shows only topics granted by %s",
    (grant, topics) => {
      expect(
        visibleGuideTopics(
          { ...user, permissions: [grant] },
          "admin",
          adminTopics,
        ).map((topic) => topic.id),
      ).toEqual([...common, ...topics]);
    },
  );
  it("full administrator sees every admin topic but cannot learn superadmin-only grants or bot changes", () => {
    const full = { ...user, permissions: Object.values(PERMISSIONS) };
    const topics = visibleGuideTopics(full, "admin", adminTopics);
    expect(topics.length).toBe(adminTopics.length - 4);
    expect(topics.map((topic) => topic.id)).not.toContain("admin-grants");
    expect(topics.map((topic) => topic.id)).not.toContain("admin-bot");
    expect(topics.map((topic) => topic.id)).not.toContain("admin-audit");
    expect(topics.map((topic) => topic.id)).not.toContain("admin-logs");
    expect(topics.map((topic) => topic.id)).toContain("admin-student-stats");
    expect(
      visibleGuideTopics({ ...user, role: "superadmin" }, "admin", adminTopics),
    ).toEqual(adminTopics);
  });
  it("denies teacher, inactive and wildcard accounts their unauthorized topics", () => {
    render(
      <GuideView currentUser={{ ...user, role: "teacher" }} portal="admin" />,
    );
    expect(screen.queryByLabelText("Qo‘llanmadan qidirish")).toBeNull();
    expect(
      visibleGuideTopics(
        { ...user, status: "inactive", role: "superadmin" },
        "admin",
        adminTopics,
      ),
    ).toEqual([]);
    expect(
      visibleGuideTopics(
        { ...user, permissions: ["*"] },
        "admin",
        adminTopics,
      ).map((topic) => topic.id),
    ).toEqual(common);
  });
  it("searches step text, normalizes Uzbek apostrophes and never reveals denied search results", () => {
    render(
      <GuideView
        currentUser={{ ...user, permissions: ["messages:send"] }}
        portal="admin"
      />,
    );
    fireEvent.change(screen.getByLabelText("Qo‘llanmadan qidirish"), {
      target: { value: "qayta preview" },
    });
    const nav = screen.getByRole("navigation", { name: "Qo‘llanma mavzulari" });
    expect(
      within(nav).getByRole("button", { name: /Tanlanganlarga/ }),
    ).toBeDefined();
    fireEvent.change(screen.getByLabelText("Qo‘llanmadan qidirish"), {
      target: { value: "administrator va barcha ruxsatlar" },
    });
    expect(screen.getByText("Mavzu topilmadi")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Qidiruvni tozalash" }));
    fireEvent.change(screen.getByLabelText("Qo‘llanmadan qidirish"), {
      target: { value: "o'quvchilarga" },
    });
    expect(screen.queryByText("Mavzu topilmadi")).toBeNull();
  });
  it("shows numbered steps, accessible image zoom, learned state and permission-safe destination", () => {
    const navigate = vi.fn();
    render(
      <GuideView
        currentUser={{ ...user, permissions: ["messages:send"] }}
        portal="admin"
        onNavigate={navigate}
      />,
    );
    fireEvent.click(
      screen
        .getByRole("navigation", { name: "Qo‘llanma mavzulari" })
        .querySelectorAll("button")[5],
    );
    const article = screen.getByRole("article");
    expect(
      within(article).getByRole("list", { name: "Amaliy qadamlar" }).children
        .length,
    ).toBe(4);
    const img = within(article).getByRole("img");
    expect(img.getAttribute("aria-label")).toMatch(/raqamlangan/);
    fireEvent.click(
      within(article).getByRole("button", { name: /Namunani kattalashtirish/ }),
    );
    expect(
      screen.getByRole("dialog", { name: /Tanlanganlarga/ }),
    ).toBeDefined();
    fireEvent.click(screen.getByRole("dialog").querySelector("button")!);
    fireEvent.click(within(article).getByRole("button", { name: "Tushundim" }));
    expect(
      within(article)
        .getByRole("button", { name: "O‘rganildi" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    fireEvent.click(
      within(article).getByRole("button", { name: "Bo‘limga o‘tish" }),
    );
    expect(navigate).toHaveBeenCalledWith("messages");
  });
  it("removes an open article and its zoom immediately when the grant is revoked", () => {
    const view = render(
      <GuideView
        currentUser={{ ...user, role: "superadmin" }}
        portal="admin"
      />,
    );
    fireEvent.click(
      screen
        .getByRole("navigation", { name: "Qo‘llanma mavzulari" })
        .querySelectorAll("button")[6],
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Namunani kattalashtirish/ }),
    );
    expect(screen.getByRole("dialog")).toBeDefined();
    view.rerender(<GuideView currentUser={user} portal="admin" />);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(
      screen.queryByRole("heading", {
        name: "Administrator va barcha ruxsatlar",
      }),
    ).toBeNull();
    expect(
      screen.getByRole("heading", { name: "Telegram orqali kirish" }),
    ).toBeDefined();
  });
});
