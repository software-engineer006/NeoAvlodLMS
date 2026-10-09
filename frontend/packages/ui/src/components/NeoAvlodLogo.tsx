import React from "react";

export type NeoAvlodPortal = "admin" | "teacher" | "neutral";
export type NeoAvlodLogoSize = "xs" | "sm" | "md" | "lg" | "xl";
export type NeoAvlodLogoVariant = "mark" | "badge" | "full";

export interface NeoAvlodLogoMarkProps extends React.SVGProps<SVGSVGElement> {
  strokeWidth?: number | string;
  title?: string;
}

/**
 * Geometric prism ribbon "N" icon faithfully extracted from neoavlod-logo.svg
 */
export const NeoAvlodLogoMark: React.FC<NeoAvlodLogoMarkProps> = ({
  className = "h-full w-auto",
  strokeWidth = 14,
  title,
  ...props
}) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 160 310"
      fill="none"
      role="img"
      aria-hidden={title ? undefined : "true"}
      aria-label={title}
      className={className}
      {...props}
    >
      <path
        d="M8 302V102L80 8l72 94v200l-72-97L8 302ZM8 102l72 103V8"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export interface NeoAvlodLogoProps {
  /** Target portal to theme colors: admin (royal blue/indigo), teacher (emerald/teal), neutral (slate) */
  portal?: NeoAvlodPortal;
  /** Presentation variant: mark (raw SVG), badge (icon inside styled container), full (badge + text) */
  variant?: NeoAvlodLogoVariant;
  /** Size preset */
  size?: NeoAvlodLogoSize;
  /** Custom subtitle for full variant */
  subtitle?: string;
  /** Title text for full variant */
  title?: string;
  /** Additional CSS classes on outer container */
  className?: string;
}

const BADGE_SIZE_CLASSES: Record<NeoAvlodLogoSize, { container: string; icon: string }> = {
  xs: {
    container: "w-7 h-7 rounded-lg p-1",
    icon: "h-4.5 w-auto",
  },
  sm: {
    container: "w-8 h-8 rounded-lg p-1.5",
    icon: "h-5 w-auto",
  },
  md: {
    container: "w-10 h-10 rounded-xl p-2",
    icon: "h-6 w-auto",
  },
  lg: {
    container: "w-12 h-12 rounded-xl p-2.5",
    icon: "h-7 w-auto",
  },
  xl: {
    container: "w-14 h-14 rounded-2xl p-3",
    icon: "h-8 w-auto",
  },
};

const PORTAL_THEMES: Record<
  NeoAvlodPortal,
  {
    badgeGradient: string;
    badgeShadow: string;
    badgeRing: string;
    iconColor: string;
    subtitleColor: string;
    defaultSubtitle: string;
  }
> = {
  admin: {
    badgeGradient: "bg-gradient-to-br from-blue-600 via-blue-600 to-indigo-700",
    badgeShadow: "shadow-md shadow-blue-500/20",
    badgeRing: "ring-1 ring-white/10",
    iconColor: "text-white",
    subtitleColor: "text-slate-400",
    defaultSubtitle: "Admin Shell",
  },
  teacher: {
    badgeGradient: "bg-gradient-to-br from-emerald-600 via-emerald-600 to-teal-700",
    badgeShadow: "shadow-md shadow-emerald-500/20",
    badgeRing: "ring-1 ring-white/10",
    iconColor: "text-white",
    subtitleColor: "text-emerald-400",
    defaultSubtitle: "O‘qituvchi Portali",
  },
  neutral: {
    badgeGradient: "bg-gradient-to-br from-slate-700 via-slate-800 to-slate-900",
    badgeShadow: "shadow-md shadow-slate-900/20",
    badgeRing: "ring-1 ring-white/10",
    iconColor: "text-white",
    subtitleColor: "text-slate-400",
    defaultSubtitle: "Ta’lim Platformasi",
  },
};

export const NeoAvlodLogo: React.FC<NeoAvlodLogoProps> = ({
  portal = "neutral",
  variant = "badge",
  size = "md",
  subtitle,
  title = "NeoAvlod LMS",
  className = "",
}) => {
  const theme = PORTAL_THEMES[portal];
  const sizeConfig = BADGE_SIZE_CLASSES[size];

  if (variant === "mark") {
    return (
      <NeoAvlodLogoMark
        className={`${sizeConfig.icon} ${className}`}
      />
    );
  }

  const badgeElement = (
    <div
      className={`inline-flex items-center justify-center shrink-0 ${sizeConfig.container} ${theme.badgeGradient} ${theme.badgeShadow} ${theme.badgeRing} ${theme.iconColor} ${variant === "badge" ? className : ""}`}
    >
      <NeoAvlodLogoMark
        title={variant === "full" ? undefined : title}
        className={`${sizeConfig.icon} drop-shadow-xs`}
      />
    </div>
  );

  if (variant === "badge") {
    return badgeElement;
  }

  // variant === "full"
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {badgeElement}
      <div className="min-w-0">
        <span className="block font-bold text-white tracking-tight text-sm truncate">
          {title}
        </span>
        <span
          className={`block text-[10px] uppercase tracking-widest font-semibold truncate ${theme.subtitleColor}`}
        >
          {subtitle || theme.defaultSubtitle}
        </span>
      </div>
    </div>
  );
};
