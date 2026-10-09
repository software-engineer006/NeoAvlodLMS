import React, { useState, useEffect } from "react";
import type { CurrentUser } from "../api/types";
import { hasPermission, canManageBot, PERMISSIONS } from "./permissions";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { NeoAvlodLogo } from "../components/NeoAvlodLogo";
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
  ChevronLeft,
  ChevronRight,
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
    label: "Dashboard",
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
    label: "O‘quvchilar",
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
  onOpenProfile?: () => void;
  children: React.ReactNode;
}

export const AdminShell: React.FC<AdminShellProps> = ({
  user,
  activeTab,
  onTabChange,
  onLogout,
  onChangePassword,
  onOpenProfile,
  children,
}) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("neoavlod_admin_sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggleCollapsed = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("neoavlod_admin_sidebar_collapsed", String(next));
      } catch {
        // Ignore localStorage quota or access errors in sandbox/private mode
      }
      return next;
    });
  };

  // Close mobile menu on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isMobileMenuOpen) {
        setIsMobileMenuOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isMobileMenuOpen]);

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

  const initials = `${user.first_name[0] || ""}${user.last_name?.[0] || ""}`.toUpperCase();

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
        className={`fixed inset-y-0 left-0 z-50 bg-slate-900 text-white flex flex-col transform transition-all duration-200 ease-in-out lg:static lg:translate-x-0 ${
          isMobileMenuOpen ? "translate-x-0" : "-translate-x-0"
        } ${!isMobileMenuOpen && "hidden lg:flex"} ${
          isCollapsed ? "lg:w-20 w-64" : "w-64"
        }`}
      >
        {/* Brand header */}
        <div
          className={`h-16 flex items-center justify-between border-b border-slate-800 ${
            isCollapsed ? "lg:px-3 px-6" : "px-6"
          }`}
        >
          <div className="flex items-center gap-3 min-w-0">
            <NeoAvlodLogo portal="admin" variant="badge" size="sm" />
            <div className={`min-w-0 ${isCollapsed ? "lg:hidden" : ""}`}>
              <span className="block font-bold text-white tracking-tight text-sm truncate">
                NeoAvlod LMS
              </span>
              <span className="block text-[10px] text-slate-400 uppercase tracking-widest font-semibold truncate">
                Admin Shell
              </span>
            </div>
          </div>
          <div className="flex items-center">
            {/* Desktop collapse toggle */}
            <button
              type="button"
              onClick={toggleCollapsed}
              className="hidden lg:flex p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              aria-label={isCollapsed ? "Sidebarni kengaytirish" : "Sidebarni yig‘ish"}
              title={isCollapsed ? "Sidebarni kengaytirish" : "Sidebarni yig‘ish"}
            >
              {isCollapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
            </button>
            {/* Mobile close button */}
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(false)}
              className="p-1 rounded-lg text-slate-400 hover:text-white lg:hidden"
              aria-label="Menyuni yopish"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Navigation items list */}
        <nav
          className={`flex-1 space-y-1 overflow-y-auto ${
            isCollapsed ? "lg:px-2 px-3 py-4" : "px-3 py-4"
          }`}
        >
          {ADMIN_NAV_ITEMS.map((item) => {
            const allowed = isAccessible(item);
            const isActive = activeTab === item.id;
            const Icon = item.icon;

            if (!allowed) {
              return null;
            }

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleNavClick(item)}
                title={item.label}
                aria-label={item.label}
                className={`w-full flex items-center py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isCollapsed ? "lg:justify-center lg:px-0 px-3 gap-3" : "px-3 gap-3"
                } ${
                  isActive
                    ? "bg-blue-600 text-white shadow-xs"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon className={`w-5 h-5 shrink-0 ${isActive ? "text-white" : "text-slate-400"}`} />
                <span className={`truncate ${isCollapsed ? "lg:hidden" : ""}`}>{item.label}</span>
                {item.superadminOnly && (
                  <span
                    className={`ml-auto text-[10px] bg-red-950/80 text-red-300 border border-red-800 px-1.5 py-0.5 rounded-sm uppercase tracking-wide ${
                      isCollapsed ? "lg:hidden" : ""
                    }`}
                  >
                    Super
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* User preview inside sidebar */}
        <div
          className={`border-t border-slate-800 bg-slate-950/50 ${
            isCollapsed ? "lg:p-2.5 p-4" : "p-4"
          }`}
        >
          <div
            onClick={onOpenProfile}
            role={onOpenProfile ? "button" : undefined}
            tabIndex={onOpenProfile ? 0 : undefined}
            className={`flex items-center gap-3 mb-3 ${
              isCollapsed ? "lg:justify-center lg:gap-0 lg:mb-2" : ""
            } ${
              onOpenProfile ? "cursor-pointer hover:opacity-90 transition-opacity" : ""
            }`}
            title={`${user.first_name} ${user.last_name ?? ""} (@${user.username}) — Profilim`}
          >
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={`${user.first_name} ${user.last_name ?? ""}`}
                className="w-9 h-9 rounded-full object-cover border border-slate-700 shrink-0"
              />
            ) : (
              <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 font-bold text-xs shrink-0">
                {initials || <UserCheck className="w-5 h-5" />}
              </div>
            )}
            <div className={`flex-1 min-w-0 ${isCollapsed ? "lg:hidden" : ""}`}>
              <p className="text-xs font-semibold text-white truncate">
                {user.first_name} {user.last_name}
              </p>
              <p className="text-[11px] text-slate-400 truncate">@{user.username}</p>
            </div>
            <div className={isCollapsed ? "lg:hidden" : ""}>
              <Badge variant={user.role === "superadmin" ? "danger" : "info"} size="sm">
                {user.role === "superadmin" ? "Super" : "Admin"}
              </Badge>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onLogout}
            className={`w-full text-slate-400 hover:text-white hover:bg-slate-800 text-xs py-1.5 ${
              isCollapsed ? "lg:px-0 lg:justify-center" : ""
            }`}
            title="Chiqish"
            aria-label="Chiqish"
            leftIcon={<LogOut className="w-3.5 h-3.5" />}
          >
            <span className={isCollapsed ? "lg:hidden" : ""}>Chiqish</span>
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
            {/* Desktop header toggle */}
            <button
              type="button"
              onClick={toggleCollapsed}
              className="hidden lg:flex p-2 -ml-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
              aria-label={isCollapsed ? "Sidebarni kengaytirish" : "Sidebarni yig‘ish"}
              title={isCollapsed ? "Sidebarni kengaytirish" : "Sidebarni yig‘ish"}
            >
              {isCollapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
            </button>
            <div className="flex items-center gap-2">
              <NeoAvlodLogo portal="admin" variant="badge" size="xs" className="lg:hidden" />
              <h1 className="text-lg font-bold text-slate-900 tracking-tight">
                {currentItem?.label || "Boshqaruv"}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <div className="hidden sm:flex items-center gap-2">
              <span className="text-xs text-slate-500 font-medium">{user.phone ?? "Kiritilmagan"}</span>
              <div className="h-3.5 w-px bg-slate-200" />
            </div>

            {/* Temporary password alert badge */}
            {user.must_change_password && (
              <button
                type="button"
                onClick={onOpenProfile || onChangePassword}
                className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 border border-amber-300 hover:bg-amber-200 transition-colors animate-pulse"
                title="Vaqtinchalik parol: yangilash lozim"
              >
                Parolni yangilang
              </button>
            )}

            {/* Profile trigger with avatar */}
            {onOpenProfile && (
              <button
                type="button"
                onClick={onOpenProfile}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors text-left"
                title="Shaxsiy profil va rasm"
              >
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={`${user.first_name} ${user.last_name ?? ""}`}
                    className="w-7 h-7 rounded-full object-cover ring-1 ring-slate-300 shrink-0"
                  />
                ) : (
                  <div className="w-7 h-7 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold text-[10px] ring-1 ring-slate-300 shrink-0">
                    {initials || <UserCheck className="w-4 h-4" />}
                  </div>
                )}
                <div className="hidden sm:block">
                  <span className="block text-xs font-semibold text-slate-800 leading-tight">
                    {user.first_name} {user.last_name}
                  </span>
                  <span className="block text-[10px] text-slate-500 font-medium">Profilim</span>
                </div>
                <span className="sm:hidden text-xs font-semibold text-slate-700">Profilim</span>
              </button>
            )}

            {onChangePassword && (
              <Button
                variant="outline"
                size="sm"
                onClick={onChangePassword}
                leftIcon={<KeyRound className="w-3.5 h-3.5" />}
                className="hidden sm:inline-flex"
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
                Dashboardga qaytish
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
