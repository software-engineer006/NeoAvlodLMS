import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { apiClient } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { CurrentUser } from "../../api/types";
import { MessagesManagementView } from "../MessagesManagementView";
import { MessageHistory } from "../MessageHistory";
import { MESSAGE_API, emptyCounts, type MessageDetail, type MessagePreview } from "../types";

const admin: CurrentUser = { id: "admin", username: "admin", first_name: "Namuna", last_name: null,
  phone: null, role: "admin", status: "active", permissions: ["messages:send"] };
const parent = { id: "p1", kind: "parent", name: "Namuna ota-ona", group_names: ["English A"],
  student_names: ["Namuna bola"], connected: true, connection_reason: null };
const student = { ...parent, id: "s1", kind: "student", name: "Namuna bola", student_names: [] };
const preview: MessagePreview = { digest: "a".repeat(64), message: "NeoAvlod LMS\n\nE’lon\n\nDars soat 9 da.",
  bot_configured: true, total: 3, eligible: 2, unlinked: 1, duplicates: 0, parents: 2, students: 1, sample: [] };
const detail: MessageDetail = { campaign: { id: "campaign", title: "E’lon", body: "Dars soat 9 da.",
  author_name: "Namuna", created_at: "2026-10-13T09:00:00Z", cancelled_at: null,
  audience: { scope: "all", kind: "both", group_ids: [], parent_ids: [], student_ids: [] },
  status: "queued", counts: { ...emptyCounts, pending: 1, failed: 1, delivered: 1 }, total: 3 },
  recipients: [], total: 0, page: 1, page_size: 25 };

function mockGet() {
  return vi.spyOn(apiClient, "get").mockImplementation(async (path, options) => {
    if (path.endsWith("/groups")) return [{ id: "g1", name: "English A", students: 3 }];
    if (path.endsWith("/recipients")) return { items: options?.params?.kind === "student" ? [student] : [parent], total: 1, page: 1, page_size: 25 };
    if (path === MESSAGE_API) return { items: [], total: 0, page: 1, page_size: 10, summary: emptyCounts };
    return detail;
  });
}
function fill() {
  fireEvent.change(screen.getByLabelText(/Xabar sarlavhasi/), { target: { value: "E’lon" } });
  fireEvent.change(screen.getByLabelText(/Xabar matni/), { target: { value: "Dars soat 9 da." } });
}
async function reviewAll() {
  render(<MessagesManagementView currentUser={admin} />);
  await screen.findByText("Namuna ota-ona");
  fireEvent.click(screen.getByRole("button", { name: /Barchaga/ }));
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Qabul qiluvchilarni ko‘rib chiqish" }));
  await screen.findByRole("button", { name: "Yuborishni tasdiqlash" });
}
beforeEach(() => { vi.restoreAllMocks(); });

describe("Xabarlar administrator oqimlari", () => {
  it("hides unauthorized UI and makes no recipient/history request", () => {
    const get = mockGet();
    render(<MessagesManagementView currentUser={{ ...admin, permissions: [] }} />);
    expect(screen.queryByLabelText(/Xabar sarlavhasi/)).toBeNull();
    expect(get).not.toHaveBeenCalled();
  });
  it("selects parents and children separately, previews before explicit confirmation", async () => {
    mockGet();
    const post = vi.spyOn(apiClient, "post").mockImplementation(async (path) => path.endsWith("/preview") ? preview : detail);
    render(<MessagesManagementView currentUser={admin} />);
    await screen.findByText("Namuna ota-ona");
    fireEvent.click(screen.getByRole("button", { name: "Ota-onalar va o‘quvchilar" }));
    fireEvent.click(await screen.findByLabelText("Tanlash: Namuna ota-ona (English A)"));
    fireEvent.click(screen.getByRole("button", { name: /O‘quvchilarni tanlash/ }));
    fireEvent.click(await screen.findByLabelText("Tanlash: Namuna bola (English A)"));
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Qabul qiluvchilarni ko‘rib chiqish" }));
    await screen.findByRole("button", { name: "Yuborishni tasdiqlash" });
    expect(post).toHaveBeenCalledWith(`${MESSAGE_API}/preview`, expect.objectContaining({ audience: {
      scope: "selected", kind: "both", parent_ids: ["p1"], student_ids: ["s1"], group_ids: [] } }));
    expect(post).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Yuborishni tasdiqlash" }));
    const dialog = screen.getByRole("dialog", { name: "Xabar yuborishni tasdiqlash" });
    expect(within(dialog).getByText(/2 ta Telegram hisobiga yuboriladi/)).toBeDefined();
    fireEvent.click(within(dialog).getByRole("button", { name: "Navbatga qo‘shish" }));
    await screen.findByText("Xabar qabul qilindi");
    expect(post.mock.calls[1][1]).toMatchObject({ request_id: expect.any(String), preview_digest: preview.digest });
    expect(screen.getByRole("dialog", { name: "Xabar: E’lon" })).toBeDefined();
  });
  it("retains idempotency key after network failure, avoids duplicate click sends", async () => {
    mockGet();
    const post = vi.spyOn(apiClient, "post").mockResolvedValueOnce(preview)
      .mockRejectedValueOnce(new ApiError(503, "Tarmoq uzildi")) .mockResolvedValueOnce(detail);
    await reviewAll();
    fireEvent.click(screen.getByRole("button", { name: "Yuborishni tasdiqlash" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Navbatga qo‘shish" }));
    await within(dialog).findByText("Tarmoq uzildi");
    const button = within(dialog).getByRole("button", { name: "Navbatga qo‘shish" });
    fireEvent.click(button); fireEvent.click(button);
    await screen.findByText("Xabar qabul qilindi");
    expect(post).toHaveBeenCalledTimes(3);
    expect(post.mock.calls[1][1]).toEqual(post.mock.calls[2][1]);
  });
  it("rejects stale preview without losing input, requires a fresh review", async () => {
    mockGet();
    vi.spyOn(apiClient, "post").mockResolvedValueOnce(preview).mockRejectedValueOnce(new ApiError(409, "Ro‘yxat o‘zgardi"));
    await reviewAll();
    fireEvent.click(screen.getByRole("button", { name: "Yuborishni tasdiqlash" }));
    fireEvent.click(screen.getByRole("button", { name: "Navbatga qo‘shish" }));
    await screen.findByText("Ro‘yxat o‘zgardi");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect((screen.getByLabelText(/Xabar sarlavhasi/) as HTMLInputElement).value).toBe("E’lon");
    expect(screen.queryByRole("button", { name: "Yuborishni tasdiqlash" })).toBeNull();
  });
  it("ignores an in-flight preview if text changes", async () => {
    mockGet();
    let resolve!: (value: MessagePreview) => void;
    vi.spyOn(apiClient, "post").mockImplementation(() => new Promise((done) => { resolve = done; }));
    render(<MessagesManagementView currentUser={admin} />);
    await screen.findByText("Namuna ota-ona");
    fireEvent.click(screen.getByRole("button", { name: /Barchaga/ })); fill();
    fireEvent.click(screen.getByRole("button", { name: "Qabul qiluvchilarni ko‘rib chiqish" }));
    fireEvent.change(screen.getByLabelText(/Xabar sarlavhasi/), { target: { value: "Yangi e’lon" } });
    await act(async () => { resolve(preview); });
    expect(screen.queryByRole("button", { name: "Yuborishni tasdiqlash" })).toBeNull();
  });
  it.each([{ bot_configured: false }, { eligible: 0 }])("disables sending when delivery is impossible: %j", async (change) => {
    mockGet(); vi.spyOn(apiClient, "post").mockResolvedValue({ ...preview, ...change });
    await reviewAll();
    expect((screen.getByRole("button", { name: "Yuborishni tasdiqlash" }) as HTMLButtonElement).disabled).toBe(true);
  });
  it("scope switches do not leak selected IDs and the full formatted UTF16 limit is enforced", async () => {
    mockGet(); const post = vi.spyOn(apiClient, "post").mockResolvedValue(preview);
    render(<MessagesManagementView currentUser={admin} />);
    fireEvent.click(await screen.findByLabelText("Tanlash: Namuna ota-ona (English A)")); fill();
    fireEvent.click(screen.getByRole("button", { name: /Guruhlar bo‘yicha/ }));
    fireEvent.click(await screen.findByLabelText("Guruhni tanlash: English A"));
    fireEvent.click(screen.getByRole("button", { name: "Qabul qiluvchilarni ko‘rib chiqish" }));
    await screen.findByRole("button", { name: "Yuborishni tasdiqlash" });
    expect(post.mock.calls[0][1]).toMatchObject({ audience: { group_ids: ["g1"], parent_ids: [], student_ids: [] } });
    fireEvent.change(screen.getByLabelText(/Xabar matni/), { target: { value: "😀".repeat(2040) } });
    expect((screen.getByRole("button", { name: "Qabul qiluvchilarni ko‘rib chiqish" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Yuborishni tasdiqlash" })).toBeNull();
  });
  it("keeps selected recipients across pages and resets filtered pagination", async () => {
    const get = mockGet();
    get.mockImplementation(async (path, options) => {
      if (path.endsWith("/groups")) return [{ id: "g1", name: "English A", students: 30 }];
      if (path === MESSAGE_API) return { items: [], total: 0, page: 1, page_size: 10, summary: emptyCounts };
      const page = options?.params?.page ?? 1;
      return { items: [{ ...parent, id: `p${page}`, name: `Namuna ota-ona ${page}` }], total: 30, page, page_size: 25 };
    });
    const post = vi.spyOn(apiClient, "post").mockResolvedValue(preview);
    render(<MessagesManagementView currentUser={admin} />);
    fireEvent.click(await screen.findByLabelText("Tanlash: Namuna ota-ona 1 (English A)"));
    fireEvent.click(screen.getByRole("button", { name: "Keyingi" }));
    fireEvent.click(await screen.findByLabelText("Tanlash: Namuna ota-ona 2 (English A)"));
    fireEvent.change(screen.getByLabelText("Qabul qiluvchini qidirish"), { target: { value: "Namuna" } });
    await waitFor(() => expect(get).toHaveBeenCalledWith(`${MESSAGE_API}/recipients`, { params: { kind: "parent", page: 1, page_size: 25, q: "Namuna" } }));
    expect((await screen.findByLabelText("Tanlash: Namuna ota-ona 1 (English A)") as HTMLInputElement).checked).toBe(true);
    fill(); fireEvent.click(screen.getByRole("button", { name: "Qabul qiluvchilarni ko‘rib chiqish" }));
    await screen.findByRole("button", { name: "Yuborishni tasdiqlash" });
    expect(post.mock.calls[0][1]).toMatchObject({ audience: { parent_ids: ["p1", "p2"] } });
  });
  it.each(["retry", "cancel"])("confirms %s and filters detail status server-side", async (action) => {
    const get = mockGet(); const post = vi.spyOn(apiClient, "post").mockResolvedValue(detail);
    render(<MessageHistory focus={detail} onSummary={() => undefined} />);
    const dialog = await screen.findByRole("dialog", { name: "Xabar: E’lon" });
    fireEvent.change(within(dialog).getByLabelText("Yetkazish holati bo‘yicha saralash"), { target: { value: "failed" } });
    await waitFor(() => expect(get).toHaveBeenCalledWith(`${MESSAGE_API}/campaign`, { params: { page: 1, page_size: 25, status: "failed" } }));
    fireEvent.click(within(dialog).getByRole("button", { name: action === "retry" ? "Xatoli yuborishlarni qayta urinish" : "Navbatni to‘xtatish" }));
    expect(post).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Amalni tasdiqlash" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(`${MESSAGE_API}/campaign/${action}`, {}));
  });
});
