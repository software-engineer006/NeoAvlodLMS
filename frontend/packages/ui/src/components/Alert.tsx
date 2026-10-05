import React from "react";
import { AlertCircle, CheckCircle, Info, TriangleAlert, X } from "lucide-react";

export interface AlertProps {
  variant?: "info" | "success" | "warning" | "danger";
  title?: string;
  children: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

export const Alert: React.FC<AlertProps> = ({
  variant = "info",
  title,
  children,
  onDismiss,
  className = "",
}) => {
  const configs = {
    info: {
      bg: "bg-blue-50 border-blue-200 text-blue-800",
      icon: <Info className="w-5 h-5 text-blue-600 shrink-0" />,
    },
    success: {
      bg: "bg-emerald-50 border-emerald-200 text-emerald-800",
      icon: <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />,
    },
    warning: {
      bg: "bg-amber-50 border-amber-200 text-amber-800",
      icon: <TriangleAlert className="w-5 h-5 text-amber-600 shrink-0" />,
    },
    danger: {
      bg: "bg-rose-50 border-rose-200 text-rose-800",
      icon: <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />,
    },
  };

  const current = configs[variant];

  return (
    <div
      role="alert"
      className={`rounded-lg border p-4 flex items-start gap-3 ${current.bg} ${className}`}
    >
      {current.icon}
      <div className="flex-1 text-sm">
        {title && <h5 className="font-semibold mb-1">{title}</h5>}
        <div className="leading-relaxed">{children}</div>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="p-1 -mr-1 -mt-1 text-current opacity-70 hover:opacity-100 rounded-sm focus:outline-none focus:ring-2 focus:ring-current"
          aria-label="Yopish"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};
