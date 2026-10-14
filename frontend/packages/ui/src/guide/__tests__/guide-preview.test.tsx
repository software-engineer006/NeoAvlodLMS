import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { GuidePreview } from "../scenes/GuidePreview";
import { adminTopics } from "../adminTopics";
import { teacherTopics } from "../teacherTopics";
import { apiClient } from "../../api/client";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it.each([...adminTopics, ...teacherTopics].map((topic) => [topic.id, topic] as const))(
  "%s renders crisp, inert React controls with one marker per step and no network", (_, topic) => {
    const get = vi.spyOn(apiClient, "get");
    const post = vi.spyOn(apiClient, "post");
    const { container } = render(<GuidePreview scene={topic.scene} description={topic.previewAlt} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector("[inert]")).not.toBeNull();
    expect(container.querySelector("[role=img]")?.getAttribute("aria-label")).toBe(topic.previewAlt);
    expect(Array.from(container.querySelectorAll("[data-guide-marker]")).map((marker) =>
      Number(marker.getAttribute("data-guide-marker")))).toEqual(topic.steps.map((_, index) => index + 1));
    for (const control of container.querySelectorAll("button,input,select")) {
      expect(control.getAttribute("tabindex")).toBe("-1");
      fireEvent.click(control);
    }
    for (const region of topic.scene.regions) {
      for (const field of region.fields || []) {
        if (field.type === "password" || /tasdiqlash kodi/i.test(field.label)) expect(field.value).toBeUndefined();
        if (field.type === "date") {
          const [year, month, day] = field.value!.split("-");
          expect(container.querySelector(`input[value="${day}.${month}.${year}"]`)).not.toBeNull();
        }
      }
    }
    expect(get).not.toHaveBeenCalled(); expect(post).not.toHaveBeenCalled();
  },
);
