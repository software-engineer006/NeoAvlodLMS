import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NeoAvlodLogo, NeoAvlodLogoMark } from "../NeoAvlodLogo";

describe("NeoAvlodLogo Component & Brand Styling", () => {
  it("renders NeoAvlodLogoMark with exact geometric SVG path and attributes", () => {
    const { container } = render(<NeoAvlodLogoMark data-testid="logo-mark" />);
    const svg = container.querySelector("svg");
    expect(svg).toBeDefined();
    expect(svg?.getAttribute("viewBox")).toBe("0 0 160 310");

    const path = container.querySelector("path");
    expect(path).toBeDefined();
    expect(path?.getAttribute("d")).toBe(
      "M8 302V102L80 8l72 94v200l-72-97L8 302ZM8 102l72 103V8"
    );
    expect(path?.getAttribute("stroke")).toBe("currentColor");
  });

  it("renders admin portal badge with blue gradient styling", () => {
    const { container } = render(
      <NeoAvlodLogo portal="admin" variant="badge" size="sm" />
    );
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("from-blue-600");
    expect(badge.className).toContain("to-indigo-700");
    expect(badge.className).toContain("text-white");
    expect(container.querySelector("svg")).toBeDefined();
  });

  it("renders teacher portal badge with emerald gradient styling", () => {
    const { container } = render(
      <NeoAvlodLogo portal="teacher" variant="badge" size="sm" />
    );
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("from-emerald-600");
    expect(badge.className).toContain("to-teal-700");
    expect(badge.className).toContain("text-white");
    expect(container.querySelector("svg")).toBeDefined();
  });

  it("renders full variant with brand title and portal-specific subtitles", () => {
    const { rerender } = render(
      <NeoAvlodLogo portal="admin" variant="full" size="md" />
    );
    expect(screen.getByText("NeoAvlod LMS")).toBeDefined();
    expect(screen.getByText("Admin Shell")).toBeDefined();

    rerender(<NeoAvlodLogo portal="teacher" variant="full" size="md" />);
    expect(screen.getByText("NeoAvlod LMS")).toBeDefined();
    expect(screen.getByText("O‘qituvchi Portali")).toBeDefined();
  });

  it("supports mark variant without badge wrapper", () => {
    const { container } = render(
      <NeoAvlodLogo variant="mark" size="lg" className="custom-mark-class" />
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeDefined();
    expect(svg?.getAttribute("class")).toContain("custom-mark-class");
  });

  it("supports custom size presets (xs, sm, md, lg, xl)", () => {
    const { container, rerender } = render(
      <NeoAvlodLogo portal="admin" variant="badge" size="xs" />
    );
    expect((container.firstChild as HTMLElement).className).toContain("w-7 h-7");

    rerender(<NeoAvlodLogo portal="admin" variant="badge" size="xl" />);
    expect((container.firstChild as HTMLElement).className).toContain("w-14 h-14");
  });

  it("supports custom title and subtitle overrides", () => {
    render(
      <NeoAvlodLogo
        portal="admin"
        variant="full"
        title="NeoAvlod Academy"
        subtitle="Maxsus Boshqaruv"
      />
    );
    expect(screen.getByText("NeoAvlod Academy")).toBeDefined();
    expect(screen.getByText("Maxsus Boshqaruv")).toBeDefined();
  });
});
