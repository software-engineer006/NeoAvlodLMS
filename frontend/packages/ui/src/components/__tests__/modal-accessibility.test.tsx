import { expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { Modal } from "../Modal";

it("names the dialog, traps keyboard focus and restores the opener", () => {
  const opener = document.createElement("button");
  document.body.append(opener); opener.focus();
  const close = vi.fn();
  const view = render(<Modal isOpen onClose={close} title="Tasdiqlash" description="Navbatga qo‘shish">
    <button>Oxirgi amal</button>
  </Modal>);
  const dialog = screen.getByRole("dialog", { name: "Tasdiqlash" });
  const first = within(dialog).getByRole("button", { name: "Yopish" });
  const last = within(dialog).getByRole("button", { name: "Oxirgi amal" });
  expect(document.activeElement).toBe(first);
  fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
  expect(document.activeElement).toBe(last);
  fireEvent.keyDown(last, { key: "Tab" });
  expect(document.activeElement).toBe(first);
  fireEvent.keyDown(first, { key: "Escape" }); expect(close).toHaveBeenCalledTimes(1);
  view.unmount(); expect(document.activeElement).toBe(opener); opener.remove();
});

it("a closed sibling cannot unlock scrolling while another dialog is open", () => {
  const close = vi.fn();
  const view = render(<><Modal isOpen onClose={close} title="Birinchi"><button>OK</button></Modal>
    <Modal isOpen={false} onClose={() => undefined}>Yopiq</Modal></>);
  expect(document.body.style.overflow).toBe("hidden");
  view.rerender(<><Modal isOpen onClose={close} title="Birinchi"><button>OK</button></Modal>
    <Modal isOpen onClose={close} title="Ikkinchi"><button>OK</button></Modal></>);
  fireEvent.keyDown(window, { key: "Escape" }); expect(close).toHaveBeenCalledTimes(1);
  view.unmount(); expect(document.body.style.overflow).toBe("");
});
