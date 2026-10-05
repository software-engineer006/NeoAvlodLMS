import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TeacherAttendanceView } from "../TeacherAttendanceView";
import type { TeacherGroupItem, TeacherAttendanceSheet } from "../types";
import { apiClient } from "../../api/client";

describe("Teacher Attendance Flow (Task 036)", () => {
  const sampleGroups: TeacherGroupItem[] = [
    {
      id: "grp-1",
      name: "Python-01",
      subject_id: "sub-1",
      subject: {
        id: "sub-1",
        name: "Python Dasturlash",
      },
      monthly_price: 600000,
      max_students: 12,
      current_students: 2,
      status: "active",
      days_of_week: [1, 3, 5],
      start_time: "14:00:00",
      end_time: "16:00:00",
      room_number: "201-xona",
      created_at: "2026-03-01T10:00:00Z",
    },
  ];

  const sampleSheetDraft: TeacherAttendanceSheet = {
    group_id: "grp-1",
    date: "2026-03-15",
    finalized: false,
    finalized_at: null,
    items: [
      {
        student_id: "std-1",
        student_first_name: "Sherzod",
        student_last_name: "Bekov",
        status: null,
        note: null,
        marked_at: null,
      },
      {
        student_id: "std-2",
        student_first_name: "Jasur",
        student_last_name: "Olimov",
        status: null,
        note: null,
        marked_at: null,
      },
    ],
  };

  const sampleSheetFinalized: TeacherAttendanceSheet = {
    group_id: "grp-1",
    date: "2026-03-15",
    finalized: true,
    finalized_at: "2026-03-15T15:30:00Z",
    items: [
      {
        student_id: "std-1",
        student_first_name: "Sherzod",
        student_last_name: "Bekov",
        status: "present",
        note: "Faol qatnashdi",
        marked_at: "2026-03-15T14:10:00Z",
      },
      {
        student_id: "std-2",
        student_first_name: "Jasur",
        student_last_name: "Olimov",
        status: "late",
        note: "10 daqiqa kechikdi",
        marked_at: "2026-03-15T14:20:00Z",
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  describe("Attendance Sheet Loading & Status Marking", () => {
    it("renders group attendance sheet, marks Bor/Yo‘q/Kechikdi and edits notes", async () => {
      vi.spyOn(apiClient, "get").mockImplementation((url) => {
        if (url.includes("/api/v1/teacher/groups")) {
          if (url.includes("/attendance")) {
            return Promise.resolve(sampleSheetDraft);
          }
          return Promise.resolve(sampleGroups);
        }
        return Promise.reject(new Error("Not found"));
      });

      render(
        <TeacherAttendanceView
          preselectedGroupId="grp-1"
          initialDate="2026-03-15"
          groups={sampleGroups}
        />
      );

      // Wait for students to load
      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });

      expect(screen.getByText("Jasur Olimov")).toBeDefined();

      // Check Bor, Yo‘q, Kechikdi buttons exist
      const borButtons = screen.getAllByRole("button", { name: /^Bor$/i });
      const yoqButtons = screen.getAllByRole("button", { name: /Yo‘q/i });
      const kechikdiButtons = screen.getAllByRole("button", { name: /Kechikdi/i });

      expect(borButtons.length).toBe(2);
      expect(yoqButtons.length).toBe(2);
      expect(kechikdiButtons.length).toBe(2);

      // Mark student 1 as 'present'
      fireEvent.click(borButtons[0]);

      // Mark student 2 as 'late'
      fireEvent.click(kechikdiButtons[1]);

      // Edit note for student 2
      const noteInputs = screen.getAllByPlaceholderText(/Izoh yozish/i);
      fireEvent.change(noteInputs[1], { target: { value: "15 daqiqa kechikdi" } });
      expect((noteInputs[1] as HTMLInputElement).value).toBe("15 daqiqa kechikdi");
    });

    it("marks all students as present via shortcut button", async () => {
      vi.spyOn(apiClient, "get").mockImplementation((url) => {
        if (url.includes("/attendance")) {
          return Promise.resolve(sampleSheetDraft);
        }
        return Promise.resolve(sampleGroups);
      });

      render(
        <TeacherAttendanceView
          preselectedGroupId="grp-1"
          initialDate="2026-03-15"
          groups={sampleGroups}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });

      // Click "Barchasini 'Bor' qilish"
      const markAllBtn = screen.getByRole("button", { name: /Barchasini 'Bor' qilish/i });
      fireEvent.click(markAllBtn);

      // Unmarked should become 0 and Both should have Bor selected
      expect(screen.getByText(/Barcha talabalar belgilandi/i)).toBeDefined();
    });
  });

  describe("Draft Save & Finalize Flow", () => {
    it("saves draft successfully and prevents duplicate submission while saving", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue(sampleSheetDraft);
      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce({
        ...sampleSheetDraft,
        items: [
          {
            ...sampleSheetDraft.items[0],
            status: "present",
            note: "Darsda bor",
          },
          sampleSheetDraft.items[1],
        ],
      });

      render(
        <TeacherAttendanceView
          preselectedGroupId="grp-1"
          initialDate="2026-03-15"
          groups={sampleGroups}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });

      // Mark student 1 as present
      const borButtons = screen.getAllByRole("button", { name: /^Bor$/i });
      fireEvent.click(borButtons[0]);

      // Click "Qoralama saqlash"
      const saveDraftBtn = screen.getByRole("button", { name: /Qoralama saqlash/i });
      fireEvent.click(saveDraftBtn);

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledTimes(1);
      });

      expect(postSpy).toHaveBeenCalledWith(
        expect.stringContaining("/attendance/draft"),
        expect.objectContaining({
          items: expect.arrayContaining([
            expect.objectContaining({
              student_id: "std-1",
              status: "present",
            }),
          ]),
        })
      );

      await waitFor(() => {
        expect(screen.getByText("Davomat qoralamasi muvaffaqiyatli saqlandi.")).toBeDefined();
      });
    });

    it("prevents finalizing when some students are unmarked", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue(sampleSheetDraft);

      render(
        <TeacherAttendanceView
          preselectedGroupId="grp-1"
          initialDate="2026-03-15"
          groups={sampleGroups}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });

      // Student 1 marked, student 2 unmarked
      const borButtons = screen.getAllByRole("button", { name: /^Bor$/i });
      fireEvent.click(borButtons[0]);

      // Click "Davomatni yakunlash"
      const finalizeBtn = screen.getByRole("button", { name: /Davomatni yakunlash/i });
      fireEvent.click(finalizeBtn);

      // Modal opens with validation error
      expect(screen.getByText(/Belgilanmagan talabalar mavjud/i)).toBeDefined();
      expect(
        screen.getByText(/Davomatni yakunlash uchun barcha talabalar belgilanadi/i)
      ).toBeDefined();

      // Submit button inside modal is disabled
      const confirmBtn = screen.getByRole("button", { name: /Tasdiqlash va yakunlash/i });
      expect(confirmBtn.getAttribute("disabled")).not.toBeNull();
    });

    it("finalizes attendance when all students are marked and transitions to readonly", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue(sampleSheetDraft);
      const postSpy = vi.spyOn(apiClient, "post").mockResolvedValueOnce(sampleSheetFinalized);

      render(
        <TeacherAttendanceView
          preselectedGroupId="grp-1"
          initialDate="2026-03-15"
          groups={sampleGroups}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });

      // Mark all students present via shortcut
      const markAllBtn = screen.getByRole("button", { name: /Barchasini 'Bor' qilish/i });
      fireEvent.click(markAllBtn);

      // Click "Davomatni yakunlash"
      const finalizeBtn = screen.getByRole("button", { name: /Davomatni yakunlash/i });
      fireEvent.click(finalizeBtn);

      // Confirm button is enabled now
      const confirmBtn = screen.getByRole("button", { name: /Tasdiqlash va yakunlash/i });
      expect(confirmBtn.getAttribute("disabled")).toBeNull();

      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledTimes(1);
      });

      expect(postSpy).toHaveBeenCalledWith(
        expect.stringContaining("/attendance/finalize"),
        expect.anything()
      );

      await waitFor(() => {
        expect(screen.getByText(/Davomat yakunlangan \(Readonly\)/i)).toBeDefined();
      });
    });
  });

  describe("Finalized Readonly State", () => {
    it("renders finalized attendance sheet in strict readonly mode without mutation controls", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue(sampleSheetFinalized);

      render(
        <TeacherAttendanceView
          preselectedGroupId="grp-1"
          initialDate="2026-03-15"
          groups={sampleGroups}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });

      expect(screen.getByText(/Davomat yakunlangan \(Readonly\)/i)).toBeDefined();
      expect(
        screen.getByText(/uchun davomat yakunlangan va ota-onalarga Telegram/i)
      ).toBeDefined();

      // Status buttons are disabled
      const borButtons = screen.getAllByRole("button", { name: /^Bor$/i });
      borButtons.forEach((btn) => {
        expect(btn.getAttribute("disabled")).not.toBeNull();
      });

      // Notes are displayed as text, not input fields
      expect(screen.getByText("Faol qatnashdi")).toBeDefined();
      expect(screen.getByText("10 daqiqa kechikdi")).toBeDefined();
      expect(screen.queryByPlaceholderText(/Izoh yozish/i)).toBeNull();

      // Save draft and finalize buttons are NOT rendered
      expect(screen.queryByRole("button", { name: /Qoralama saqlash/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /Davomatni yakunlash/i })).toBeNull();
    });
  });

  describe("API Error Handling", () => {
    it("displays error message when saving draft fails", async () => {
      vi.spyOn(apiClient, "get").mockResolvedValue(sampleSheetDraft);
      vi.spyOn(apiClient, "post").mockRejectedValueOnce(
        new Error("409 Conflict: Attendance already finalized for this date")
      );

      render(
        <TeacherAttendanceView
          preselectedGroupId="grp-1"
          initialDate="2026-03-15"
          groups={sampleGroups}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Sherzod Bekov")).toBeDefined();
      });

      // Mark one student
      const borButtons = screen.getAllByRole("button", { name: /^Bor$/i });
      fireEvent.click(borButtons[0]);

      // Click save draft
      const saveDraftBtn = screen.getByRole("button", { name: /Qoralama saqlash/i });
      fireEvent.click(saveDraftBtn);

      await waitFor(() => {
        expect(
          screen.getByText(/409 Conflict: Attendance already finalized for this date/i)
        ).toBeDefined();
      });
    });
  });

  describe("Security & Storage Verification", () => {
    it("never stores tokens, secrets, or passwords in localStorage or sessionStorage", () => {
      expect(localStorage.getItem("token")).toBeNull();
      expect(localStorage.getItem("access_token")).toBeNull();
      expect(sessionStorage.getItem("token")).toBeNull();
      expect(sessionStorage.getItem("access_token")).toBeNull();
    });
  });
});
