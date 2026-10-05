import React from "react";
import type { AttendanceStatusType } from "./types";
import { formatAttendanceStatus } from "./types";
import { Badge } from "../components/Badge";
import { Check, X, Clock } from "lucide-react";

export interface AttendanceBadgeProps {
  status: AttendanceStatusType;
  className?: string;
}

export const AttendanceBadge: React.FC<AttendanceBadgeProps> = ({ status, className = "" }) => {
  const { label, variant } = formatAttendanceStatus(status);

  const icons = {
    present: <Check className="w-3.5 h-3.5 text-emerald-600 mr-1" />,
    absent: <X className="w-3.5 h-3.5 text-rose-600 mr-1" />,
    late: <Clock className="w-3.5 h-3.5 text-amber-600 mr-1" />,
  };

  return (
    <Badge variant={variant} className={`inline-flex items-center ${className}`}>
      {icons[status]}
      <span>{label}</span>
    </Badge>
  );
};
