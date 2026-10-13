import React, { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

const openDialogs: HTMLElement[] = [];
let originalOverflow = "";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl" | "2xl";
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}) => {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    if (!isOpen || !dialogRef.current) return;
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    if (openDialogs.length === 0) {
      originalOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    openDialogs.push(dialog);
    const focusable = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled):not([type="hidden"]), textarea:not(:disabled), select:not(:disabled), a[href], [tabindex="0"]',
    )).filter((element) => !element.hidden && !element.closest('[hidden], [aria-hidden="true"]'));
    (focusable()[0] ?? dialog).focus();
    const handleKeyDown = (e: KeyboardEvent) => {
      if (openDialogs.at(-1) !== dialog) return;
      if (e.key === "Escape") {
        e.preventDefault();
        closeRef.current();
      }
      if (e.key === "Tab") {
        const elements = focusable();
        const first = elements[0] ?? dialog;
        const last = elements.at(-1) ?? dialog;
        if (!dialog.contains(document.activeElement) ||
          (e.shiftKey && document.activeElement === first) ||
          (!e.shiftKey && document.activeElement === last)) {
          e.preventDefault();
          (e.shiftKey ? last : first).focus();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      openDialogs.splice(openDialogs.indexOf(dialog), 1);
      if (openDialogs.length === 0) document.body.style.overflow = originalOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const sizeClasses = {
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-lg",
    xl: "max-w-2xl",
    "2xl": "max-w-3xl",
  };

  return (
    <div
      role="dialog"
      ref={dialogRef}
      tabIndex={-1}
      aria-modal="true"
      aria-labelledby={title ? titleId : undefined}
      aria-describedby={description ? descriptionId : undefined}
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/50 backdrop-blur-xs transition-opacity"
      onClick={onClose}
    >
      <div
        className={`bg-white rounded-xl shadow-xl border border-slate-100 w-full ${sizeClasses[size]} overflow-hidden transform transition-all flex flex-col max-h-[calc(100vh-2rem)] sm:max-h-[calc(100vh-4rem)]`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 sm:px-6 py-4 border-b border-slate-100 flex items-center justify-between shrink-0">
          <div>
            {title && <h3 id={titleId} className="text-base font-semibold text-slate-900">{title}</h3>}
            {description && <p id={descriptionId} className="text-xs text-slate-500 mt-0.5">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Yopish"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5 sm:px-6 py-5 overflow-y-auto flex-1">{children}</div>
        {footer && (
          <div className="px-5 sm:px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-end gap-3 shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
