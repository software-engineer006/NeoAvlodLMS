import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, formatExactDateTime, formatMonth, formatTime,
  shiftMonth, tashkentMonth, tashkentToday } from "./dates";

describe("portal calendar and Tashkent clocks", () => {
  it("keeps calendar dates separate from timestamps and rejects impossible dates", () => {
    expect(formatDate("2024-02-29")).toBe("29.02.2024");
    for (const value of ["2026-02-29", "2026-02-30", "2026-13-01", "0000-01-01", "", "bad"])
      expect(formatDate(value)).toBe("—");
    expect(formatDate("2026-10-13")).toBe("13.10.2026");
    expect(formatDate("2026-10-13T19:00:00Z")).toBe("14.10.2026");
  });
  it("uses Tashkent at midnight/year rollover and for explicit/legacy offsets", () => {
    expect(formatDateTime("2026-12-31T19:00:01Z")).toBe("01.01.2027 00:00:01");
    expect(formatDateTime("2026-10-14T15:37:47+05:00")).toBe("14.10.2026 15:37:47");
    expect(formatDateTime("2026-10-14T10:37:47")).toBe("14.10.2026 15:37:47");
    expect(formatTime("2026-10-13T19:00:00Z")).toBe("00:00:00");
    expect(formatDateTime("invalid")).toBe("—");
    expect(formatExactDateTime("2026-10-14T10:37:47.123456Z")).toBe("14.10.2026 15:37:47.123456");
  });
  it("selects the current day/month in Tashkent and shifts months without browser timezone", () => {
    const now = new Date("2026-12-31T19:00:00Z");
    expect(tashkentToday(now)).toBe("2027-01-01");
    expect(tashkentMonth(now)).toBe("2027-01");
    expect(formatMonth("2027-01")).toBe("01.2027");
    expect(formatMonth("2027-13")).toBe("—");
    expect(formatMonth("0000-01")).toBe("—");
    expect(shiftMonth("0001-01", -1)).toBe("0001-01");
    expect(shiftMonth("9999-12", 1)).toBe("9999-12");
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
    expect(shiftMonth("2027-01", -1)).toBe("2026-12");
  });
});
