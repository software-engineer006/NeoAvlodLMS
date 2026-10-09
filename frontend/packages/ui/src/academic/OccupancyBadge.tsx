import React from "react";

export interface OccupancyBadgeProps {
  current: number;
  max: number;
  showBar?: boolean;
  className?: string;
}

export const OccupancyBadge: React.FC<OccupancyBadgeProps> = ({
  current,
  max,
  showBar = true,
  className = "",
}) => {
  const safeMax = Math.max(1, max);
  const percentage = Math.min(100, Math.round((current / safeMax) * 100));

  let statusColor = "text-emerald-700 bg-emerald-50 border-emerald-200";
  let barColor = "bg-emerald-500";
  let statusText = "Bo‘sh o‘rinlar bor";

  if (current >= safeMax) {
    statusColor = "text-rose-700 bg-rose-50 border-rose-200";
    barColor = "bg-rose-500";
    statusText = "Guruh to‘lgan";
  } else if (percentage >= 75) {
    statusColor = "text-amber-700 bg-amber-50 border-amber-200";
    barColor = "bg-amber-500";
    statusText = "Joylar oz qoldi";
  }

  return (
    <div className={`inline-flex flex-col gap-1 ${className}`}>
      <div className="flex items-center gap-1.5">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${statusColor}`}
          title={`${current} / ${safeMax} o‘quvchi (${percentage}% bandlik - ${statusText})`}
        >
          {current} / {safeMax}
        </span>
        <span className="text-[11px] font-mono text-slate-500">{percentage}%</span>
      </div>

      {showBar && (
        <div className="w-24 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${barColor}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      )}
    </div>
  );
};
