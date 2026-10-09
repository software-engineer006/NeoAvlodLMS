import React, { useState } from "react";
import {
  AuthProvider,
  ForbiddenPage,
  LoginForm,
  NeoAvlodLogo,
  PasswordChangeModal,
  PasswordRecoveryModal,
  UserProfileModal,
  TeacherShell,
  TeacherGroupsView,
  TeacherGroupStudentsView,
  TeacherAttendanceView,
  MonthlyAttendanceHistoryView,
  useAuth,
} from "@neoavlod/ui";
import type { TeacherGroupItem } from "@neoavlod/ui";

const TeacherMainApp: React.FC = () => {
  const { user, logout, setUser } = useAuth();
  const [activeTab, setActiveTab] = useState<string>("groups");
  const [selectedGroup, setSelectedGroup] = useState<TeacherGroupItem | null>(null);
  const [viewingStudentsGroup, setViewingStudentsGroup] = useState<TeacherGroupItem | null>(null);
  const [isChangePasswordOpen, setIsChangePasswordOpen] = useState<boolean>(false);
  const [isProfileOpen, setIsProfileOpen] = useState<boolean>(false);

  if (!user) {
    return null;
  }

  // Portal Guard: Admin or Superadmin cannot access Teacher portal
  if (user.role !== "teacher") {
    return <ForbiddenPage isAdmin={true} onLogout={logout} />;
  }

  const handleTabChange = (newTab: string) => {
    setActiveTab(newTab);
    setViewingStudentsGroup(null);
  };

  return (
    <>
      <TeacherShell
        user={user}
        activeTab={activeTab}
        onTabChange={handleTabChange}
        onLogout={logout}
        onChangePassword={() => setIsChangePasswordOpen(true)}
        onOpenProfile={() => setIsProfileOpen(true)}
      >
        {activeTab === "groups" && !viewingStudentsGroup && (
          <TeacherGroupsView
            onSelectGroupForAttendance={(group) => {
              setSelectedGroup(group);
              setActiveTab("attendance");
            }}
            onSelectGroupForStudents={(group) => {
              setViewingStudentsGroup(group);
            }}
          />
        )}

        {activeTab === "groups" && viewingStudentsGroup && (
          <TeacherGroupStudentsView
            group={viewingStudentsGroup}
            onBack={() => setViewingStudentsGroup(null)}
            onSelectGroupForAttendance={(group) => {
              setSelectedGroup(group);
              setActiveTab("attendance");
            }}
          />
        )}

        {activeTab === "attendance" && (
          <TeacherAttendanceView
            preselectedGroupId={selectedGroup?.id}
          />
        )}
        {activeTab === "history" && (
          <MonthlyAttendanceHistoryView portal="teacher" initialGroupId={selectedGroup?.id} currentUser={user} />
        )}

        {/* Password Change Modal */}
        <PasswordChangeModal
          isOpen={isChangePasswordOpen}
          onClose={() => setIsChangePasswordOpen(false)}
          portal="teacher"
          onSuccess={() => {
            setTimeout(() => logout(), 1500);
          }}
        />
      </TeacherShell>

      {/* User Profile Modal */}
      <UserProfileModal
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
        portal="teacher"
        user={user}
        onUserUpdated={(updated) => setUser(updated)}
        onLogoutRequired={() => logout()}
      />
    </>
  );
};

const TeacherAuthView: React.FC = () => {
  const { user, isLoading, setUser } = useAuth();
  const [isRecoveryOpen, setIsRecoveryOpen] = useState<boolean>(false);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-600">Tizim holati tekshirilmoqda...</p>
        </div>
      </div>
    );
  }

  if (user) {
    return <TeacherMainApp />;
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-6">
        <NeoAvlodLogo
          portal="teacher"
          variant="badge"
          size="xl"
          className="mx-auto mb-3 shadow-lg shadow-emerald-500/25 ring-1 ring-emerald-500/20"
        />
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">NeoAvlod LMS</h2>
        <p className="text-sm text-slate-500 mt-1">O‘qituvchilar uchun shaxsiy kabinet</p>
      </div>

      <div className="px-4">
        <LoginForm
          portal="teacher"
          localDemo={import.meta.env.DEV && import.meta.env.VITE_LOCAL_DEMO === "1"}
          onSuccess={(loggedInUser) => setUser(loggedInUser)}
          onForgotPassword={() => setIsRecoveryOpen(true)}
        />
      </div>

      <PasswordRecoveryModal
        isOpen={isRecoveryOpen}
        onClose={() => setIsRecoveryOpen(false)}
        portal="teacher"
      />

      <p className="mt-8 text-center text-xs text-slate-400">
        NeoAvlod LMS — Xavfsiz ta’lim boshqaruv platformasi &copy; 2026
      </p>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider portal="teacher">
      <TeacherAuthView />
    </AuthProvider>
  );
};
