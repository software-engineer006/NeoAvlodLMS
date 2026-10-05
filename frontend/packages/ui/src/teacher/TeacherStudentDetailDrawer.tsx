import React from "react";
import type { TeacherStudentItem } from "./types";
import { Drawer } from "../components/Drawer";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import {
  User,
  Users,
  Phone,
  Calendar,
  Send,
  ShieldAlert,
  CheckCircle2,
  Layers,
} from "lucide-react";

export interface TeacherStudentDetailDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  student: TeacherStudentItem | null;
}

export const TeacherStudentDetailDrawer: React.FC<TeacherStudentDetailDrawerProps> = ({
  isOpen,
  onClose,
  student,
}) => {
  if (!student) {
    return null;
  }

  const formattedDate = student.created_at
    ? new Date(student.created_at).toLocaleDateString("uz-UZ", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "-";

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title="Talaba ma’lumotlari"
      description={`${student.first_name} ${student.last_name} bo‘yicha batafsil profil`}
      size="lg"
      footer={
        <Button variant="outline" onClick={onClose}>
          Yopish
        </Button>
      }
    >
      <div className="space-y-6">
        {/* Student Section */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 space-y-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-lg">
                <User className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  {student.first_name} {student.last_name}
                </h3>
                <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500">
                  <Layers className="w-3.5 h-3.5 text-slate-400" />
                  <span>{student.group_name}</span>
                  <span>•</span>
                  <span>{student.age} yoshda</span>
                </div>
              </div>
            </div>

            <Badge
              variant={student.status === "active" ? "success" : "neutral"}
              size="sm"
            >
              {student.status === "active" ? "Faol" : "Nofaol"}
            </Badge>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-200/60 text-sm">
            <div>
              <p className="text-xs text-slate-500 font-medium">Telefon raqami</p>
              <a
                href={`tel:${student.phone}`}
                className="inline-flex items-center gap-1.5 text-slate-900 font-semibold hover:text-emerald-600 transition-colors mt-0.5"
              >
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                {student.phone}
              </a>
            </div>

            <div>
              <p className="text-xs text-slate-500 font-medium">Telegram holati</p>
              <div className="mt-1 flex items-center gap-1.5">
                {student.telegram_connected ? (
                  <Badge variant="success" size="sm">
                    <Send className="w-3 h-3 mr-1 inline" />
                    Telegram ulangan
                  </Badge>
                ) : (
                  <Badge variant="neutral" size="sm">
                    Telegram ulanmagan
                  </Badge>
                )}
              </div>
            </div>

            <div>
              <p className="text-xs text-slate-500 font-medium">Qo‘shilgan sana</p>
              <div className="flex items-center gap-1.5 text-slate-700 font-medium mt-0.5 text-xs">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                {formattedDate}
              </div>
            </div>
          </div>
        </div>

        {/* Parent Section */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-2xs">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Users className="w-4 h-4 text-emerald-600" />
            <span>Ota-ona ma’lumotlari</span>
          </div>

          <div className="space-y-3">
            <div>
              <p className="text-xs text-slate-500 font-medium">F.I.Sh</p>
              <p className="text-sm font-semibold text-slate-900 mt-0.5">
                {student.parent.first_name} {student.parent.last_name}
              </p>
            </div>

            <div>
              <p className="text-xs text-slate-500 font-medium">Aloqa telefoni</p>
              <a
                href={`tel:${student.parent.phone}`}
                className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900 hover:text-emerald-600 transition-colors mt-0.5"
              >
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                {student.parent.phone}
              </a>
            </div>

            <div>
              <p className="text-xs text-slate-500 font-medium">Telegram xabarnoma holati</p>
              <div className="mt-1.5">
                {student.parent.telegram_connected ? (
                  <div className="flex items-start gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-900 text-xs">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold block">Telegram hisobi ulangan</span>
                      <span className="text-emerald-700 text-[11px]">
                        Davomat natijalari (Bor/Yo‘q/Kechikdi) avtomatik ravishda ushbu hisobga yuboriladi.
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 text-xs">
                    <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold block">Telegram ulanmagan</span>
                      <span className="text-amber-700 text-[11px]">
                        Ota-ona botga ulanmagan. Davomat xabarnomalari ota-ona hisobini bog‘lagandan keyin yetkaziladi.
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Drawer>
  );
};
