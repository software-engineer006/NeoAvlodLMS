import React, { useState } from "react";
import type { CurrentUser } from "../api/types";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import {
  Layers,
  CalendarCheck,
  LogOut,
  KeyRound,
  Menu,
  X,
  UserCheck,
} from "lucide-react";

export interface TeacherNavItemConfig {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const TEACHER_NAV_ITEMS: TeacherNavItemConfig[] = [
  {
    id: "groups",
    label: "Mening guruhlarim",
    icon: Layers,
  },
  {
    id: "attendance",
    label: "Davomat olish",
    icon: CalendarCheck,
  },
];

export interface TeacherShellProps {
  user: CurrentUser;
  activeTab: string;
  onTabChange: (tabId: string) => void;
  onLogout: () => void;
  onChangePassword?: () => void;
  children: React.ReactNode;
}

export const TeacherShell: React.FC<TeacherShellProps> = ({
  user,
  activeTab,
  onTabChange,
  onLogout,
  onChangePassword,
  children,
}) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);

  const currentItem = TEACHER_NAV_ITEMS.find((item) => item.id === activeTab);

  const handleNavClick = (tabId: string) => {
    onTabChange(tabId);
    setIsMobileMenuOpen(false);
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
            <div className="w-8 h-8 rounded-lg bg-emerald-600 text-white flex items-center justify-center font-bold text-base shadow-sm">
              N
            </div>
            <div>
              <span className="font-bold text-white tracking-tight text-sm">NeoAvlod LMS</span>
              <span className="block text-[10px] text-emerald-400 uppercase tracking-widest font-semibold">
                O‘qituvchi Portali
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
          {TEACHER_NAV_ITEMS.map((item) => {
            const isActive = activeTab === item.id;
            const Icon = item.icon;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleNavClick(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-emerald-600 text-white shadow-xs"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon className={`w-5 h-5 shrink-0 ${isActive ? "text-white" : "text-slate-400"}`} />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* User preview inside sidebar */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-emerald-400">
              <UserCheck className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-white truncate">
                {user.first_name} {user.last_name}
              </p>
              <p className="text-[11px] text-slate-400 truncate">@{user.username}</p>
            </div>
            <Badge variant="success" size="sm">
              O‘qituvchi
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
              {currentItem?.label || "O‘qituvchi boshqaruvi"}
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
          {children}
        </main>
      </div>
    </div>
  );
};
