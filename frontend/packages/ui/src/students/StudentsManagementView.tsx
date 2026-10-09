import React, { useState, useEffect, useCallback } from "react";
import type { CurrentUser } from "../api/types";
import type { StudentItem, StudentListResponse } from "./types";
import type { GroupItem } from "../academic/types";
import { hasPermission, PERMISSIONS } from "../navigation/permissions";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Card } from "../components/Card";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Badge } from "../components/Badge";
import { Alert } from "../components/Alert";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/Table";
import { StudentModal } from "./StudentModal";
import { StudentTransferModal } from "./StudentTransferModal";
import { StudentDetailDrawer } from "./StudentDetailDrawer";
import {
  UserPlus,
  Search,
  RefreshCw,
  Edit2,
  ArrowRightLeft,
  CheckCircle2,
  XCircle,
  Eye,
  UserCheck,
  UserX,
} from "lucide-react";

export interface StudentsManagementViewProps {
  currentUser: CurrentUser;
}

export const StudentsManagementView: React.FC<StudentsManagementViewProps> = ({ currentUser }) => {
  const canCreate = hasPermission(currentUser, PERMISSIONS.STUDENTS_CREATE);
  const canEdit = hasPermission(currentUser, PERMISSIONS.STUDENTS_EDIT);

  const [students, setStudents] = useState<StudentItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 10;

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [groupFilter, setGroupFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Groups list for dropdown
  const [groups, setGroups] = useState<GroupItem[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Modals & Drawer
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingStudent, setEditingStudent] = useState<StudentItem | null>(null);

  const [isTransferModalOpen, setIsTransferModalOpen] = useState<boolean>(false);
  const [transferringStudent, setTransferringStudent] = useState<StudentItem | null>(null);

  const [drawerStudentId, setDrawerStudentId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load groups for filter dropdown
  useEffect(() => {
    const loadGroups = async () => {
      try {
        const res = await apiClient.get<{ items: GroupItem[] }>("/api/v1/admin/groups", {
          params: { page_size: 100 },
        });
        setGroups(res.items);
      } catch {
        // Soft fail on filter options
      }
    };
    loadGroups();
  }, []);

  const loadStudents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
      };
      if (debouncedSearch.trim()) {
        params.q = debouncedSearch.trim();
      }
      if (groupFilter !== "all") {
        params.group_id = groupFilter;
      }
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }

      const res = await apiClient.get<StudentListResponse>("/api/v1/admin/students", { params });
      setStudents(res.items);
      setTotal(res.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("O‘quvchilar ro‘yxatini yuklashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, debouncedSearch, groupFilter, statusFilter]);

  useEffect(() => {
    loadStudents();
  }, [loadStudents]);

  const handleOpenCreate = () => {
    setEditingStudent(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (student: StudentItem) => {
    setEditingStudent(student);
    setIsModalOpen(true);
  };

  const handleOpenTransfer = (student: StudentItem) => {
    setTransferringStudent(student);
    setIsTransferModalOpen(true);
  };

  const handleToggleStatus = async (student: StudentItem) => {
    setTogglingId(student.id);
    try {
      if (student.status === "active") {
        await apiClient.post(`/api/v1/admin/students/${student.id}/deactivate`);
      } else {
        await apiClient.post(`/api/v1/admin/students/${student.id}/activate`);
      }
      await loadStudents();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("O‘quvchi holatini o‘zgartirishda xatolik yuz berdi");
      }
    } finally {
      setTogglingId(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">O‘quvchilar boshqaruvi</h1>
          <p className="text-sm text-slate-500 mt-1">
            O‘quvchilar va ota-onalar hisoblari, Telegram ulanishlari hamda guruhlar taqsimoti
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadStudents()}
            disabled={isLoading}
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
          >
            Yangilash
          </Button>
          {canCreate && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleOpenCreate}
              leftIcon={<UserPlus className="w-4 h-4" />}
            >
              Yangi o‘quvchi
            </Button>
          )}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="sm:col-span-1">
            <Input
              placeholder="Qidiruv (ism, familiya, telefon)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftAddon={<Search className="w-4 h-4 text-slate-400" />}
            />
          </div>

          <div>
            <Select
              value={groupFilter}
              onChange={(e) => {
                setGroupFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "Barcha guruhlar" },
                ...groups.map((g) => ({ value: g.id, label: g.name })),
              ]}
            />
          </div>

          <div>
            <Select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "Barcha holatlar" },
                { value: "active", label: "Faol o‘quvchilar" },
                { value: "inactive", label: "Nofaol o‘quvchilar" },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Error alert if any */}
      {error && !isLoading && students.length > 0 && (
        <Alert variant="danger" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Content */}
      {isLoading && students.length === 0 ? (
        <LoadingState message="O‘quvchilar ro‘yxati yuklanmoqda..." />
      ) : error && students.length === 0 ? (
        <ErrorState title="O‘quvchilarni yuklab bo‘lmadi" message={error} onRetry={loadStudents} />
      ) : students.length === 0 ? (
        <EmptyState
          title="O‘quvchilar topilmadi"
          description="Filtrlarga mos keluvchi o‘quvchilar mavjud emas yoki ro‘yxat bo‘sh."
        />
      ) : (
        <div className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>O‘quvchi</TableHead>
                <TableHead>Telefon & Telegram</TableHead>
                <TableHead>Guruh</TableHead>
                <TableHead>Ota-ona</TableHead>
                <TableHead>Holati</TableHead>
                <TableHead className="text-right">Amallar</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {students.map((student) => (
                <TableRow
                  key={student.id}
                  className="cursor-pointer hover:bg-slate-50/80 transition-colors"
                  onClick={() => setDrawerStudentId(student.id)}
                >
                  <TableCell>
                    <button
                      type="button"
                      className="text-left focus:outline-none focus:ring-2 focus:ring-blue-500 rounded p-0.5 group"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDrawerStudentId(student.id);
                      }}
                    >
                      <div className="font-semibold text-slate-900 group-hover:text-blue-600 group-hover:underline">
                        {student.first_name} {student.last_name}
                      </div>
                      <div className="text-xs text-slate-500">{student.age == null ? (student.school_grade ?? "Yosh kiritilmagan") : `${student.age} yosh`}</div>
                    </button>
                  </TableCell>

                  <TableCell>
                    <div className="text-xs space-y-1">
                      <a
                        href={student.phone ? `tel:${student.phone}` : undefined}
                        onClick={(e) => e.stopPropagation()}
                        className="font-mono text-slate-700 hover:text-blue-600"
                      >
                        {student.phone ?? "Kiritilmagan"}
                      </a>
                      <div>
                        {student.telegram_connected ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Ulangan
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                            <XCircle className="w-3.5 h-3.5" /> Ulanmagan
                          </span>
                        )}
                      </div>
                    </div>
                  </TableCell>

                  <TableCell>
                    <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                      {student.group.name}
                    </span>
                  </TableCell>

                  <TableCell>
                    <div className="text-xs">
                      <div className="font-medium text-slate-900">
                        {student.parent?.first_name ?? "Kiritilmagan"} {student.parent?.last_name}
                      </div>
                      <a
                        href={student.parent?.phone ? `tel:${student.parent.phone}` : undefined}
                        onClick={(e) => e.stopPropagation()}
                        className="font-mono text-slate-500 hover:text-blue-600 block mt-0.5"
                      >
                        {student.parent?.phone ?? "Kiritilmagan"}
                      </a>
                      <div className="mt-0.5">
                        {student.parent?.telegram_connected ? (
                          <span className="text-[11px] text-emerald-700 font-medium flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Botga ulangan
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-400 flex items-center gap-1">
                            <XCircle className="w-3 h-3" /> Botga ulanmagan
                          </span>
                        )}
                      </div>
                    </div>
                  </TableCell>

                  <TableCell>
                    {student.status === "active" ? (
                      <Badge variant="success">Faol</Badge>
                    ) : (
                      <Badge variant="danger">Nofaol</Badge>
                    )}
                  </TableCell>

                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Batafsil ma’lumot"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDrawerStudentId(student.id);
                        }}
                        className="px-2"
                      >
                        <Eye className="w-4 h-4 text-slate-600" />
                      </Button>

                      {canEdit && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            title="Guruhni ko‘chirish"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenTransfer(student);
                            }}
                            className="px-2 text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50"
                          >
                            <ArrowRightLeft className="w-4 h-4" />
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            title="Tahrirlash"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenEdit(student);
                            }}
                            className="px-2 text-slate-600 hover:text-slate-800"
                          >
                            <Edit2 className="w-4 h-4" />
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            title={student.status === "active" ? "Nofaol qilish" : "Faollashtirish"}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleToggleStatus(student);
                            }}
                            isLoading={togglingId === student.id}
                            className={`px-2 ${
                              student.status === "active"
                                ? "text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                                : "text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                            }`}
                          >
                            {student.status === "active" ? (
                              <UserX className="w-4 h-4" />
                            ) : (
                              <UserCheck className="w-4 h-4" />
                            )}
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-1 py-2 text-xs text-slate-600">
            <div>
              Jami: <span className="font-semibold text-slate-900">{total}</span> ta o‘quvchi
              {totalPages > 1 && (
                <span>
                  {" "}(Sahifa: {page} / {totalPages})
                </span>
              )}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1 || isLoading}
                  onClick={() => setPage(page - 1)}
                >
                  Oldingi
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages || isLoading}
                  onClick={() => setPage(page + 1)}
                >
                  Keyingi
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create / Edit Modal */}
      <StudentModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        student={editingStudent}
        onSuccess={() => loadStudents()}
      />

      {/* Transfer Modal */}
      <StudentTransferModal
        isOpen={isTransferModalOpen}
        onClose={() => setIsTransferModalOpen(false)}
        student={transferringStudent}
        onSuccess={() => loadStudents()}
      />

      {/* Detail Slide-over Drawer */}
      <StudentDetailDrawer
        isOpen={Boolean(drawerStudentId)}
        onClose={() => setDrawerStudentId(null)}
        studentId={drawerStudentId}
        currentUser={currentUser}
        onEdit={(detail) => {
          setDrawerStudentId(null);
          handleOpenEdit(detail);
        }}
        onTransfer={(detail) => {
          setDrawerStudentId(null);
          handleOpenTransfer(detail);
        }}
        onStatusChanged={() => loadStudents()}
        onDeleted={() => loadStudents()}
      />
    </div>
  );
};
