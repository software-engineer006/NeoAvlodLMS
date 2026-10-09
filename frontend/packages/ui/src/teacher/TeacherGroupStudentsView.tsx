import React, { useEffect, useState, useMemo } from "react";
import type { TeacherGroupItem, TeacherStudentItem } from "./types";
import { apiClient } from "../api/client";
import { TeacherStudentDetailDrawer } from "./TeacherStudentDetailDrawer";
import { OccupancyBadge } from "../academic/OccupancyBadge";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, CardContent } from "../components/Card";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "../components/Table";
import {
  ArrowLeft,
  CalendarCheck,
  Search,
  User,
  Users,
  Send,
  Phone,
  RefreshCw,
  Eye,
  ShieldAlert,
} from "lucide-react";

export interface TeacherGroupStudentsViewProps {
  group: TeacherGroupItem;
  onBack: () => void;
  onSelectGroupForAttendance?: (group: TeacherGroupItem) => void;
}

export const TeacherGroupStudentsView: React.FC<TeacherGroupStudentsViewProps> = ({
  group,
  onBack,
  onSelectGroupForAttendance,
}) => {
  const [students, setStudents] = useState<TeacherStudentItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isUnauthorized, setIsUnauthorized] = useState<boolean>(false);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const [selectedStudent, setSelectedStudent] = useState<TeacherStudentItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  const fetchStudents = async () => {
    setIsLoading(true);
    setError(null);
    setIsUnauthorized(false);
    try {
      const data = await apiClient.get<TeacherStudentItem[]>(
        `/api/v1/teacher/groups/${group.id}/students`
      );
      setStudents(data);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "O‘quvchilar ro‘yxatini yuklashda xatolik yuz berdi";
      if (
        errMsg.includes("403") ||
        errMsg.includes("404") ||
        errMsg.toLowerCase().includes("not accessible") ||
        errMsg.toLowerCase().includes("taqiqlan")
      ) {
        setIsUnauthorized(true);
      }
      setError(errMsg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStudents();
  }, [group.id]);

  const filteredStudents = useMemo(() => {
    return students.filter((student) => {
      if (statusFilter !== "all" && student.status !== statusFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const matchesName = `${student.first_name} ${student.last_name ?? ""}`
          .toLowerCase()
          .includes(query);
        const matchesPhone = student.phone?.toLowerCase().includes(query);
        const matchesParentName = `${student.parent?.first_name ?? "Kiritilmagan"} ${student.parent?.last_name}`
          .toLowerCase()
          .includes(query);
        const matchesParentPhone = student.parent?.phone.toLowerCase().includes(query);

        if (!matchesName && !matchesPhone && !matchesParentName && !matchesParentPhone) {
          return false;
        }
      }
      return true;
    });
  }, [students, statusFilter, searchQuery]);

  const stats = useMemo(() => {
    const total = students.length;
    const active = students.filter((s) => s.status === "active").length;
    const parentTelegram = students.filter((s) => s.parent?.telegram_connected).length;
    return { total, active, parentTelegram };
  }, [students]);

  const handleOpenDetail = (student: TeacherStudentItem) => {
    setSelectedStudent(student);
    setIsDrawerOpen(true);
  };

  if (isUnauthorized) {
    return (
      <div className="max-w-md mx-auto my-12 bg-white rounded-xl shadow-xs border border-slate-200 p-8 text-center space-y-4">
        <div className="w-12 h-12 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
          <ShieldAlert className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">
          Ushbu guruhga kirish taqiqlangan
        </h3>
        <p className="text-sm text-slate-600">
          Sizda ushbu guruh ma’lumotlarini ko‘rish huquqi yo‘q yoki guruh mavjud emas.
        </p>
        <Button variant="primary" onClick={onBack} className="mt-2">
          Guruhlar ro‘yxatiga qaytish
        </Button>
      </div>
    );
  }

  if (isLoading && students.length === 0) {
    return <LoadingState message="Guruh o‘quvchilari yuklanmoqda..." />;
  }

  if (error && students.length === 0) {
    return (
      <ErrorState
        title="O‘quvchilarni yuklashda xatolik"
        message={error}
        onRetry={fetchStudents}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="p-2 -ml-2 text-slate-600 hover:text-slate-900"
            aria-label="Orqaga qaytish"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                {group.name}
              </h2>
              <Badge variant="neutral" size="sm">
                {group.subject?.name}
              </Badge>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Guruh o‘quvchilari ro‘yxati va ota-onalar bilan aloqa ma’lumotlari
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onSelectGroupForAttendance && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => onSelectGroupForAttendance(group)}
              leftIcon={<CalendarCheck className="w-4 h-4" />}
            >
              Davomat olish
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={fetchStudents}
            isLoading={isLoading}
            leftIcon={<RefreshCw className="w-4 h-4" />}
          >
            Yangilash
          </Button>
        </div>
      </div>

      {/* Group Quick Info & Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                Guruh bandligi
              </p>
              <div className="mt-1">
                <OccupancyBadge
                  current={group.current_students}
                  max={group.max_students}
                />
              </div>
            </div>
            <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center">
              <Users className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                Jami o‘quvchilar
              </p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{stats.total}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <User className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                Faol o‘quvchilar
              </p>
              <p className="text-2xl font-bold text-emerald-600 mt-1">{stats.active}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <User className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                Ota-ona Telegram
              </p>
              <p className="text-2xl font-bold text-indigo-600 mt-1">
                {stats.parentTelegram} / {stats.total}
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Send className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <Card>
        <CardContent className="p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
          <div className="flex-1 relative">
            <Input
              type="text"
              placeholder="O‘quvchi yoki ota-ona ismi, telefoni bo‘yicha qidirish..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftAddon={<Search className="w-4 h-4 text-slate-400" />}
            />
          </div>

          <div className="w-full md:w-56">
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: "all", label: "Barcha holatlar" },
                { value: "active", label: "Faqat faol" },
                { value: "inactive", label: "Nofaol" },
              ]}
            />
          </div>
        </CardContent>
      </Card>

      {/* Students Table */}
      {filteredStudents.length === 0 ? (
        <EmptyState
          title="O‘quvchilar topilmadi"
          description={
            searchQuery || statusFilter !== "all"
              ? "Qidiruv parametrlariga mos keladigan o‘quvchilar topilmadi."
              : "Ushbu guruhda hozircha o‘quvchilar mavjud emas."
          }
        />
      ) : (
        <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>O‘quvchi F.I.Sh</TableHead>
                <TableHead>Telefon raqami</TableHead>
                <TableHead>Yoshi</TableHead>
                <TableHead>Ota-onasi</TableHead>
                <TableHead>Ota-ona Telegram</TableHead>
                <TableHead>Holat</TableHead>
                <TableHead className="text-right">Amallar</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredStudents.map((student) => (
                <TableRow
                  key={student.id}
                  className="cursor-pointer hover:bg-slate-50/80 transition-colors"
                  onClick={() => handleOpenDetail(student)}
                >
                  <TableCell>
                    <button
                      type="button"
                      className="text-left focus:outline-none focus:ring-2 focus:ring-emerald-500 rounded p-0.5 group"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDetail(student);
                      }}
                    >
                      <div className="font-semibold text-slate-900 group-hover:text-emerald-600 group-hover:underline">
                        {student.first_name} {student.last_name}
                      </div>
                      {student.telegram_connected && (
                        <div className="text-[11px] text-emerald-600 flex items-center gap-1 mt-0.5 font-medium">
                          <Send className="w-3 h-3" />
                          <span>Telegram ulangan</span>
                        </div>
                      )}
                    </button>
                  </TableCell>

                  <TableCell>
                    <a
                      href={student.phone ? `tel:${student.phone}` : undefined}
                      onClick={(e) => e.stopPropagation()}
                      className="text-sm font-medium text-slate-700 hover:text-emerald-600 inline-flex items-center gap-1"
                    >
                      <Phone className="w-3.5 h-3.5 text-slate-400" />
                      {student.phone ?? "Kiritilmagan"}
                    </a>
                  </TableCell>

                  <TableCell>
                    <span className="text-sm text-slate-700">{student.age == null ? (student.school_grade ?? "Yosh kiritilmagan") : `${student.age} yosh`}</span>
                  </TableCell>

                  <TableCell>
                    <div>
                      <div className="text-sm font-medium text-slate-900">
                        {student.parent?.first_name ?? "Kiritilmagan"} {student.parent?.last_name}
                      </div>
                      <a
                        href={student.parent?.phone ? `tel:${student.parent.phone}` : undefined}
                        onClick={(e) => e.stopPropagation()}
                        className="text-xs text-slate-500 hover:text-emerald-600 inline-flex items-center gap-1 mt-0.5"
                      >
                        <Phone className="w-3 h-3 text-slate-400" />
                        {student.parent?.phone ?? "Kiritilmagan"}
                      </a>
                    </div>
                  </TableCell>

                  <TableCell>
                    {student.parent?.telegram_connected ? (
                      <Badge variant="success" size="sm">
                        <Send className="w-3 h-3 mr-1 inline" />
                        Ulangan
                      </Badge>
                    ) : (
                      <Badge variant="warning" size="sm">
                        Ulanmagan
                      </Badge>
                    )}
                  </TableCell>

                  <TableCell>
                    <Badge
                      variant={student.status === "active" ? "success" : "neutral"}
                      size="sm"
                    >
                      {student.status === "active" ? "Faol" : "Nofaol"}
                    </Badge>
                  </TableCell>

                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDetail(student);
                      }}
                      leftIcon={<Eye className="w-3.5 h-3.5" />}
                    >
                      Batafsil
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Student Detail Drawer */}
      <TeacherStudentDetailDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        student={selectedStudent}
      />
    </div>
  );
};
