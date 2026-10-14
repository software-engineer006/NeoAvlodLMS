import React, { useState } from "react";
import {
  AdminShell,
  AuthProvider,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  DashboardStatsCards,
  ForbiddenPage,
  LoginForm,
  NeoAvlodLogo,
  PasswordChangeModal,
  PasswordRecoveryModal,
  UserProfileModal,
  StaffManagementView,
  SubjectsManagementView,
  GroupsManagementView,
  StudentsManagementView,
  AdminAttendanceView,
  BotSettingsView,
  MessagesManagementView,
  LogsView,
  useAuth,
} from "@neoavlod/ui";
import { AdminGuideView } from "@neoavlod/ui/admin-guide";

const AdminContent: React.FC<{ activeTab: string; onNavigate?: (tab: string) => void }> = ({
  activeTab,
  onNavigate,
}) => {
  const { user } = useAuth();

  if (activeTab === "dashboard") {
    return (
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Real Statistics Cards */}
        <DashboardStatsCards onNavigate={onNavigate} />
      </div>
    );
  }

  if (activeTab === "staff" && user) {
    return <StaffManagementView currentUser={user} />;
  }

  if (activeTab === "subjects" && user) {
    return <SubjectsManagementView currentUser={user} />;
  }

  if (activeTab === "groups" && user) {
    return <GroupsManagementView currentUser={user} />;
  }

  if (activeTab === "students" && user) {
    return <StudentsManagementView currentUser={user} />;
  }

  if (activeTab === "attendance" && user) {
    return <AdminAttendanceView currentUser={user} />;
  }

  if (activeTab === "bot-settings" && user) {
    return <BotSettingsView currentUser={user} />;
  }
  if (activeTab === "messages" && user) {
    return <MessagesManagementView currentUser={user} />;
  }
  if (activeTab === "logs" && user) return <LogsView currentUser={user} />;
  if (activeTab === "guide" && user) {
    return <AdminGuideView currentUser={user} onNavigate={onNavigate} />;
  }

  // Fallback view for other tabs
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="capitalize">{activeTab} bo‘limi</CardTitle>
          <CardDescription>
            Ushbu bo‘lim uchun ruxsat tasdiqlandi va admin shell ostida ishga tushirildi.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-600">
            Siz {activeTab} bo‘limidasiz. Ushbu modul uchun ma’muriy amallar faol.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

const AdminShellContainer: React.FC = () => {
  const { user, logout, setUser } = useAuth();
  const [activeTab, setActiveTab] = useState<string>("dashboard");
  const [isChangePasswordOpen, setIsChangePasswordOpen] = useState<boolean>(false);
  const [isProfileOpen, setIsProfileOpen] = useState<boolean>(false);

  if (!user) {
    return null;
  }

  // Teacher is strictly forbidden from Admin portal (403)
  if (user.role === "teacher") {
    return <ForbiddenPage isTeacher={true} onLogout={logout} />;
  }

  return (
    <>
      <AdminShell
        user={user}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onLogout={logout}
        onChangePassword={() => setIsChangePasswordOpen(true)}
        onOpenProfile={() => setIsProfileOpen(true)}
      >
        <AdminContent activeTab={activeTab} onNavigate={setActiveTab} />
      </AdminShell>

      <UserProfileModal
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
        portal="admin"
        user={user}
        onUserUpdated={(updated) => setUser(updated)}
        onLogoutRequired={() => logout()}
      />

      <PasswordChangeModal
        isOpen={isChangePasswordOpen}
        onClose={() => setIsChangePasswordOpen(false)}
        portal="admin"
        onSuccess={() => {
          setTimeout(() => logout(), 2000);
        }}
      />
    </>
  );
};

const AdminAuthView: React.FC = () => {
  const { user, isLoading, setUser } = useAuth();
  const [isRecoveryOpen, setIsRecoveryOpen] = useState<boolean>(false);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-600">Tizim holati tekshirilmoqda...</p>
        </div>
      </div>
    );
  }

  if (user) {
    return <AdminShellContainer />;
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-6">
        <NeoAvlodLogo
          portal="admin"
          variant="badge"
          size="xl"
          className="mx-auto mb-3 shadow-lg shadow-blue-500/25 ring-1 ring-blue-500/20"
        />
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">NeoAvlod LMS</h2>
        <p className="text-sm text-slate-500 mt-1">Admin va boshqaruv xodimlari portali</p>
      </div>

      <div className="px-4">
        <LoginForm
          portal="admin"
          localDemo={import.meta.env.DEV && import.meta.env.VITE_LOCAL_DEMO === "1"}
          onSuccess={(loggedInUser) => setUser(loggedInUser)}
          onForgotPassword={() => setIsRecoveryOpen(true)}
        />
      </div>

      <PasswordRecoveryModal
        isOpen={isRecoveryOpen}
        onClose={() => setIsRecoveryOpen(false)}
        portal="admin"
      />

      <p className="mt-8 text-center text-xs text-slate-400">
        NeoAvlod LMS — Xavfsiz ta’lim boshqaruv tizimi &copy; 2026
      </p>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider portal="admin">
      <AdminAuthView />
    </AuthProvider>
  );
};
