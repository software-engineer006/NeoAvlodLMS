import React, { useState } from "react";
import {
  AdminShell,
  Alert,
  AuthProvider,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  ErrorState,
  ForbiddenPage,
  LoginForm,
  Modal,
  PasswordChangeModal,
  PasswordRecoveryModal,
  StaffManagementView,
  SubjectsManagementView,
  GroupsManagementView,
  StudentsManagementView,
  AdminAttendanceView,
  BotSettingsView,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  apiClient,
  useAuth,
} from "@neoavlod/ui";
import {
  ShieldCheck,
  Users,
  Layers,
  CheckCircle2,
} from "lucide-react";

interface HealthStatus {
  status: string;
  database: string;
}

const AdminContent: React.FC<{ activeTab: string }> = ({ activeTab }) => {
  const { user, fetchMe } = useAuth();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isLoadingHealth, setIsLoadingHealth] = useState<boolean>(false);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [isSampleModalOpen, setIsSampleModalOpen] = useState<boolean>(false);

  const checkHealth = async () => {
    setIsLoadingHealth(true);
    setHealthError(null);
    try {
      const data = await apiClient.get<HealthStatus>("/api/v1/health");
      setHealth(data);
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : "API bilan bog‘lanishda xatolik yuz berdi");
    } finally {
      setIsLoadingHealth(false);
    }
  };

  React.useEffect(() => {
    checkHealth();
  }, []);

  if (activeTab === "dashboard") {
    return (
      <div className="space-y-6 max-w-7xl mx-auto">
        <Alert variant="info" title="Xush kelibsiz">
          Siz tizimga <strong>{user?.username}</strong> ({user?.role === "superadmin" ? "Superadmin" : "Admin"}) sifatida kirdingiz.
          Admin shell va navigatsiya orqali ruxsat berilgan bo‘limlarni boshqarishingiz mumkin.
        </Alert>

        {/* Status Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">Backend API</CardTitle>
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            </CardHeader>
            <CardContent>
              {isLoadingHealth ? (
                <div className="text-sm text-slate-500">Tekshirilmoqda...</div>
              ) : healthError ? (
                <div className="text-sm text-rose-600 font-medium">{healthError}</div>
              ) : (
                <>
                  <div className="text-2xl font-bold text-slate-900 uppercase">
                    {health?.status || "Faol"}
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Baza holati: <span className="font-semibold text-emerald-600">{health?.database || "Bog‘langan"}</span>
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">Xodimlar bo‘limi</CardTitle>
              <Users className="w-5 h-5 text-blue-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">RBAC Ruxsatlari</div>
              <p className="text-xs text-slate-500 mt-1">
                {user?.permissions?.length ? `${user.permissions.length} ta ruxsat biriktirilgan` : "Superadmin to‘liq huquqi"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">Xavfsizlik protokoli</CardTitle>
              <ShieldCheck className="w-5 h-5 text-indigo-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">Telegram OTP</div>
              <p className="text-xs text-slate-500 mt-1">Kirish va parolni tiklash himoyalangan</p>
            </CardContent>
          </Card>
        </div>

        {/* Dashboard Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Boshqaruv paneli holati</CardTitle>
            <CardDescription>
              Tizim ma’lumotlari va joriy foydalanuvchi ma’lumotlari
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary" onClick={() => setIsSampleModalOpen(true)}>
                Namuna modal
              </Button>
              <Button variant="secondary" onClick={checkHealth} isLoading={isLoadingHealth}>
                Statusni yangilash
              </Button>
              <Button variant="outline" onClick={fetchMe}>
                Profilni qayta yuklash
              </Button>
            </div>

            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <Layers className="w-4 h-4 text-slate-500" />
                Joriy hisob ma’lumotlari
              </h4>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Maydon</TableHead>
                    <TableHead>Qiymat</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className="font-medium text-slate-600">ID</TableCell>
                    <TableCell className="font-mono text-xs">{user?.id}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-slate-600">Foydalanuvchi nomi</TableCell>
                    <TableCell className="font-semibold">{user?.username}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-slate-600">Telefon</TableCell>
                    <TableCell>{user?.phone}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-slate-600">Rol</TableCell>
                    <TableCell>
                      <Badge variant={user?.role === "superadmin" ? "danger" : "info"}>
                        {user?.role === "superadmin" ? "Superadmin" : "Admin"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-slate-600">Telegram ID</TableCell>
                    <TableCell>{user?.telegram_id || "Bog‘lanmagan"}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        {healthError && (
          <Card>
            <CardContent>
              <ErrorState title="API bilan bog‘lanish xatosi" message={healthError} onRetry={checkHealth} />
            </CardContent>
          </Card>
        )}

        <Modal
          isOpen={isSampleModalOpen}
          onClose={() => setIsSampleModalOpen(false)}
          title="Ma’muriy amal tasdig‘i"
          description="Amalni bajarishga ishonchingiz komilmi?"
          footer={
            <Button variant="primary" onClick={() => setIsSampleModalOpen(false)}>
              Tushundim
            </Button>
          }
        >
          <p className="text-sm text-slate-600">
            Ushbu amal barcha tizim loglariga kiritiladi va audit qaydlarida aks etadi.
          </p>
        </Modal>
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
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<string>("dashboard");
  const [isChangePasswordOpen, setIsChangePasswordOpen] = useState<boolean>(false);

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
      >
        <AdminContent activeTab={activeTab} />
      </AdminShell>

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
        <div className="inline-flex w-12 h-12 rounded-xl bg-blue-600 text-white items-center justify-center font-bold text-xl shadow-md mb-2">
          N
        </div>
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
