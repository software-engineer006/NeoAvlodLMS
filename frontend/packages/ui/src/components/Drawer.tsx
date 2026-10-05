import React, { useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "./Button";

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "md" | "lg" | "xl";
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const sizeClasses = {
    md: "max-w-md",
    lg: "max-w-xl",
    xl: "max-w-2xl",
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div
          className={`w-screen ${sizeClasses[size]} bg-white shadow-2xl flex flex-col transform transition-transform ease-in-out duration-300`}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">{title}</h2>
              {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="p-1 text-slate-400 hover:text-slate-600 rounded-lg -mr-2 -mt-1"
              aria-label="Yopish"
            >
              <X className="w-5 h-5" />
            </Button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6">{children}</div>

          {/* Footer */}
          {footer && (
            <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex items-center justify-end gap-3">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
