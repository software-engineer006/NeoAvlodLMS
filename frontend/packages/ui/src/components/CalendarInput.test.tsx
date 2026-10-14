import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { CalendarInput, parseCalendarInput } from "./CalendarInput";

describe("local calendar input with ISO boundary", () => {
  it("rejects impossible dates and accepts leap dates/short pasted components", () => {
    expect(parseCalendarInput("29.02.2024", "date")).toBe("2024-02-29");
    expect(parseCalendarInput("1.2.2026", "date")).toBe("2026-02-01");
    expect(parseCalendarInput("29.02.2026", "date")).toBeNull();
    expect(parseCalendarInput("2026-10-14", "date")).toBeNull();
    expect(parseCalendarInput("13.2026", "month")).toBeNull();
  });
  it("keeps partial text editable but invalid values out of parent requests, then normalizes", () => {
    const change = vi.fn();
    function Form() {
      const [value, setValue] = useState("2026-10-14");
      return <CalendarInput label="Sana" value={value} onValueChange={iso => { setValue(iso); change(iso); }} />;
    }
    render(<Form />);
    const input = screen.getByLabelText("Sana") as HTMLInputElement;
    expect(input.value).toBe("14.10.2026");
    fireEvent.change(input, { target: { value: "29.02.2026" } });
    expect(input.value).toBe("29.02.2026");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(change).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "1.2.2026" } });
    expect(change).toHaveBeenLastCalledWith("2026-02-01");
    fireEvent.blur(input);
    expect(input.value).toBe("01.02.2026");
    fireEvent.change(input, { target: { value: "" } });
    expect(change).toHaveBeenLastCalledWith("");
  });
  it("honors controlled updates, bounds, disabled and calendar selection", () => {
    const change = vi.fn();
    const view = render(<CalendarInput label="Oy" type="month" value="2026-10" min="2026-01" max="2026-12" onValueChange={change} />);
    expect((screen.getByLabelText("Oy") as HTMLInputElement).value).toBe("10.2026");
    fireEvent.change(screen.getByLabelText("Oy"), { target: { value: "01.2027" } });
    expect(change).not.toHaveBeenCalled();
    const native = view.container.querySelector('input[type="month"]')!;
    fireEvent.change(native, { target: { value: "2026-11" } });
    expect(change).toHaveBeenLastCalledWith("2026-11");
    view.rerender(<CalendarInput label="Oy" type="month" value="2026-12" onValueChange={change} disabled />);
    expect((screen.getByLabelText("Oy") as HTMLInputElement).value).toBe("12.2026");
    expect((screen.getByRole("button", { name: "Oy — kalendar" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
