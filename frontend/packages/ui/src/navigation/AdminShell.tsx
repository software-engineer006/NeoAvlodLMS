import React, { useState } from "react";
import type { CurrentUser } from "../api/types";
import { hasPermission, canManageBot, PERMISSIONS } from "./permissions";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import {
  LayoutDashboard,
  Users,
  BookOpen,
  Layers,
  GraduationCap,
  CalendarCheck,
  Bot,
  LogOut,
  KeyRound,
  Menu,
  X,
  UserCheck,
  ShieldAlert,
} from "lucide-react";

export interface NavItemConfig {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  permission?: string;
  superadminOnly?: boolean;
}

export const ADMIN_NAV_ITEMS: NavItemConfig[] = [
  {
    id: "dashboard",
    label: "Bosh sahifa",
    icon: LayoutDashboard,
  },
  {
    id: "staff",
    label: "Xodimlar",
    icon: Users,
    permission: PERMISSIONS.STAFF_MANAGE,
  },
  {
    id: "subjects",
    label: "Fanlar",
    icon: BookOpen,
    permission: PERMISSIONS.SUBJECTS_MANAGE,
  },
  {
    id: "groups",
    label: "Guruhlar",
    icon: Layers,
    permission: PERMISSIONS.GROUPS_READ,
  },
  {
    id: "students",
    label: "Talabalar",
    icon: GraduationCap,
    permission: PERMISSIONS.STUDENTS_READ,
  },
  {
    id: "attendance",
    label: "Davomat tarixi",
    icon: CalendarCheck,
    permission: PERMISSIONS.ATTENDANCE_READ,
  },
  {
    id: "bot-settings",
    label: "Bot sozlamalari",
    icon: Bot,
    superadminOnly: true,
  },
];

export interface AdminShellProps {
  user: CurrentUser;
  activeTab: string;
  onTabChange: (tabId: string) => void;
  onLogout: () => void;
  onChangePassword?: () => void;
  children: React.ReactNode;
}

export const AdminShell: React.FC<AdminShellProps> = ({
  user,
  activeTab,
  onTabChange,
  onLogout,
  onChangePassword,
  children,
}) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);

  // Check if item is accessible for current user
  const isAccessible = (item: NavItemConfig) => {
    if (item.superadminOnly) {
      return canManageBot(user);
    }
    if (item.permission) {
      return hasPermission(user, item.permission);
    }
    return true;
  };

  // Find current active item configuration
  const currentItem = ADMIN_NAV_ITEMS.find((item) => item.id === activeTab);
  const isCurrentTabAllowed = currentItem ? isAccessible(currentItem) : true;

  const handleNavClick = (item: NavItemConfig) => {
    if (isAccessible(item)) {
      onTabChange(item.id);
      setIsMobileMenuOpen(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Mobile Sidebar Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-xs lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 text-white flex flex-col transform transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 ${
          isMobileMenuOpen ? "translate-x-0" : "-translate-x-0"
        } ${!isMobileMenuOpen && "hidden lg:flex"}`}
      >
        {/* Brand header */}
        <div className="h-16 px-6 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-base shadow-sm">
              N
            </div>
            <div>
              <span className="font-bold text-white tracking-tight text-sm">NeoAvlod LMS</span>
              <span className="block text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
                Admin Shell
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen(false)}
            className="p-1 rounded-lg text-slate-400 hover:text-white lg:hidden"
            aria-label="Menyuni yopish"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation items list */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {ADMIN_NAV_ITEMS.map((item) => {
            const allowed = isAccessible(item);
            const isActive = activeTab === item.id;
            const Icon = item.icon;

            if (!allowed) {
              // Hide unauthorized items from sidebar
              return null;
            }

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleNavClick(item)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white shadow-xs"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon className={`w-5 h-5 shrink-0 ${isActive ? "text-white" : "text-slate-400"}`} />
                <span className="truncate">{item.label}</span>
                {item.superadminOnly && (
                  <span className="ml-auto text-[10px] bg-red-950/80 text-red-300 border border-red-800 px-1.5 py-0.5 rounded-sm uppercase tracking-wide">
                    Super
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* User preview inside sidebar */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
              <UserCheck className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-white truncate">
                {user.first_name} {user.last_name}
              </p>
              <p className="text-[11px] text-slate-400 truncate">@{user.username}</p>
            </div>
            <Badge variant={user.role === "superadmin" ? "danger" : "info"} size="sm">
              {user.role === "superadmin" ? "Super" : "Admin"}
            </Badge>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onLogout}
            className="w-full text-slate-400 hover:text-white hover:bg-slate-800 text-xs py-1.5"
            leftIcon={<LogOut className="w-3.5 h-3.5" />}
          >
            Chiqish
          </Button>
        </div>
      </aside>

      {/* Main Page Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 sm:px-6 lg:px-8 shrink-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="p-2 -ml-2 text-slate-600 hover:text-slate-900 rounded-lg lg:hidden"
              aria-label="Menyuni ochish"
            >
              <Menu className="w-6 h-6" />
            </button>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              {currentItem?.label || "Boshqaruv"}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2">
              <span className="text-xs text-slate-500 font-medium">{user.phone}</span>
              <div className="h-3.5 w-px bg-slate-200" />
            </div>

            {onChangePassword && (
              <Button
                variant="outline"
                size="sm"
                onClick={onChangePassword}
                leftIcon={<KeyRound className="w-3.5 h-3.5" />}
              >
                Parol
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={onLogout}
              leftIcon={<LogOut className="w-3.5 h-3.5 text-slate-500" />}
            >
              Chiqish
            </Button>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          {!isCurrentTabAllowed ? (
            <div className="max-w-md mx-auto my-12 bg-white rounded-xl shadow-xs border border-slate-200 p-8 text-center space-y-4">
              <div className="w-12 h-12 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <h3 className="text-base font-semibold text-slate-900">Ushbu bo‘limga kirish cheklangan</h3>
              <p className="text-sm text-slate-600">
                Sizning hisobingizda <strong>{currentItem?.label}</strong> bo‘limiga kirish huquqi mavjud emas.
              </p>
              <Button variant="primary" onClick={() => onTabChange("dashboard")} className="mt-2">
                Bosh sahifaga qaytish
              </Button>
            </div>
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  );
};
