import React from "react";
import { ShieldAlert, LogOut, ExternalLink } from "lucide-react";
import { Button } from "../components/Button";

export interface ForbiddenPageProps {
  onLogout?: () => void;
  message?: string;
  isTeacher?: boolean;
  isAdmin?: boolean;
}

export const ForbiddenPage: React.FC<ForbiddenPageProps> = ({
  onLogout,
  message,
  isTeacher = false,
  isAdmin = false,
}) => {
  let defaultMessage = "Sizda ushbu sahifa yoki amalni ko‘rish uchun yetarli huquq mavjud emas.";
  if (isTeacher) {
    defaultMessage = "Siz o‘qituvchi hisobiga egasiz. Admin boshqaruv portali faqat ma’muriyat xodimlari uchun mo‘ljallangan. Iltimos, o‘qituvchi portali orqali kiring.";
  } else if (isAdmin) {
    defaultMessage = "Siz ma’muriyat hisobiga egasiz. O‘qituvchi portali faqat o‘qituvchilar uchun mo‘ljallangan. Iltimos, admin portali orqali kiring.";
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center items-center p-4 text-center">
      <div className="bg-white rounded-2xl shadow-lg border border-slate-200 max-w-md w-full p-8 space-y-6">
        <div className="w-16 h-16 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center mx-auto shadow-inner">
          <ShieldAlert className="w-8 h-8" />
        </div>

        <div>
          <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200 mb-2">
            Xatolik 403
          </span>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            Ruxsat berilmagan
          </h2>
          <p className="text-sm text-slate-600 mt-3 leading-relaxed">
            {message || defaultMessage}
          </p>
        </div>

        <div className="pt-2 space-y-3">
          {isTeacher && (
            <a
              href="https://teacher.eduneo.uz"
              className="inline-flex items-center justify-center gap-2 w-full px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <ExternalLink className="w-4 h-4" />
              O‘qituvchi portaliga o‘tish
            </a>
          )}

          {isAdmin && (
            <a
              href="https://admin.eduneo.uz"
              className="inline-flex items-center justify-center gap-2 w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <ExternalLink className="w-4 h-4" />
              Admin portaliga o‘tish
            </a>
          )}

          {onLogout && (
            <Button
              variant="outline"
              className="w-full"
              onClick={onLogout}
              leftIcon={<LogOut className="w-4 h-4" />}
            >
              Boshqa hisob bilan kirish (Chiqish)
            </Button>
          )}
        </div>
      </div>

      <p className="mt-8 text-xs text-slate-400">
        NeoAvlod LMS — Xavfsiz ta’lim boshqaruv platformasi &copy; 2026
      </p>
    </div>
  );
};
