import React from "react";
import type { CurrentUser } from "../api/types";
import { hasPermission, canManageBot } from "./permissions";
import { ShieldAlert } from "lucide-react";

export interface PermissionGuardProps {
  user: CurrentUser | null;
  permission?: string;
  requireSuperadmin?: boolean;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const PermissionGuard: React.FC<PermissionGuardProps> = ({
  user,
  permission,
  requireSuperadmin = false,
  children,
  fallback,
}) => {
  let isAllowed = false;

  if (requireSuperadmin) {
    isAllowed = canManageBot(user);
  } else if (permission) {
    isAllowed = hasPermission(user, permission);
  } else {
    isAllowed = true;
  }

  if (isAllowed) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  return (
    <div className="p-8 text-center bg-white rounded-xl border border-slate-200">
      <div className="w-12 h-12 rounded-xl bg-amber-100 text-amber-600 flex items-center justify-center mx-auto mb-3">
        <ShieldAlert className="w-6 h-6" />
      </div>
      <h3 className="text-base font-semibold text-slate-900 mb-1">Amal uchun ruxsat yo‘q</h3>
      <p className="text-sm text-slate-500 max-w-sm mx-auto">
        Ushbu amalni bajarish uchun sizning hisobingizda yetarli huquq mavjud emas.
      </p>
    </div>
  );
};
