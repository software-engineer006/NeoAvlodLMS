import React, { useState, useEffect, useCallback } from "react";
import type { CurrentUser } from "../api/types";
import type { GroupItem, GroupListResponse, SubjectItem } from "./types";
import type { StaffItem } from "../staff/types";
import { formatDaysOfWeek, formatPrice, DAYS_OF_WEEK } from "./types";
import { hasPermission, PERMISSIONS } from "../navigation/permissions";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Card } from "../components/Card";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Badge } from "../components/Badge";
import { Alert } from "../components/Alert";
import { Modal } from "../components/Modal";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/Table";
import { OccupancyBadge } from "./OccupancyBadge";
import { GroupModal } from "./GroupModal";
import {
  Layers,
  Plus,
  Search,
  RefreshCw,
  Edit2,
  Trash2,
  CheckCircle2,
  XCircle,
  Calendar,
  Clock,
  DoorOpen,
} from "lucide-react";

export interface GroupsManagementViewProps {
  currentUser: CurrentUser;
}

export const GroupsManagementView: React.FC<GroupsManagementViewProps> = ({ currentUser }) => {
  const canCreate = hasPermission(currentUser, PERMISSIONS.GROUPS_CREATE);
  const canEdit = hasPermission(currentUser, PERMISSIONS.GROUPS_EDIT);

  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 10;

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [subjectFilter, setSubjectFilter] = useState<string>("all");
  const [teacherFilter, setTeacherFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [dayFilter, setDayFilter] = useState<string>("all");

  // Options for dropdowns
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [teachers, setTeachers] = useState<StaffItem[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingGroup, setEditingGroup] = useState<GroupItem | null>(null);
  const [deletingGroup, setDeletingGroup] = useState<GroupItem | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load filter options once
  useEffect(() => {
    const loadFilterOptions = async () => {
      try {
        const [subRes, staffRes] = await Promise.all([
          apiClient.get<{ items: SubjectItem[] }>("/api/v1/admin/subjects", {
            params: { page_size: 100 },
          }),
          apiClient.get<{ items: StaffItem[] }>("/api/v1/admin/staff", {
            params: { page_size: 100, role: "teacher" },
          }),
        ]);
        setSubjects(subRes.items);
        setTeachers(staffRes.items);
      } catch {
        // Soft fail on filter options
      }
    };
    loadFilterOptions();
  }, []);

  const loadGroups = useCallback(async () => {
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
      if (subjectFilter !== "all") {
        params.subject_id = subjectFilter;
      }
      if (teacherFilter !== "all") {
        params.teacher_id = teacherFilter;
      }
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }
      if (dayFilter !== "all") {
        params.day_of_week = parseInt(dayFilter, 10);
      }

      const res = await apiClient.get<GroupListResponse>("/api/v1/admin/groups", { params });
      setGroups(res.items);
      setTotal(res.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Guruhlar ro‘yxatini yuklashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, debouncedSearch, subjectFilter, teacherFilter, statusFilter, dayFilter]);

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);

  const handleOpenCreate = () => {
    setEditingGroup(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (group: GroupItem) => {
    setEditingGroup(group);
    setIsModalOpen(true);
  };

  const handleToggleStatus = async (group: GroupItem) => {
    setTogglingId(group.id);
    try {
      if (group.status === "active") {
        await apiClient.post(`/api/v1/admin/groups/${group.id}/deactivate`);
      } else {
        await apiClient.post(`/api/v1/admin/groups/${group.id}/activate`);
      }
      await loadGroups();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Guruh holatini o‘zgartirishda xatolik yuz berdi");
      }
    } finally {
      setTogglingId(null);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deletingGroup) return;
    setIsDeleting(true);
    try {
      await apiClient.delete(`/api/v1/admin/groups/${deletingGroup.id}`);
      setDeletingGroup(null);
      await loadGroups();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Guruhni o‘chirishda xatolik yuz berdi");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Guruhlar boshqaruvi</h1>
          <p className="text-sm text-slate-500 mt-1">
            Dars jadvali, o‘qituvchilar, xonalar va guruhlar bandligi monitoringi
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadGroups()}
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
              leftIcon={<Plus className="w-4 h-4" />}
            >
              Yangi guruh
            </Button>
          )}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3">
          <div className="sm:col-span-2 md:col-span-1">
            <Input
              placeholder="Guruh nomi..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftAddon={<Search className="w-4 h-4 text-slate-400" />}
            />
          </div>

          <div>
            <Select
              value={subjectFilter}
              onChange={(e) => {
                setSubjectFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "Barcha fanlar" },
                ...subjects.map((s) => ({ value: s.id, label: s.name })),
              ]}
            />
          </div>

          <div>
            <Select
              value={teacherFilter}
              onChange={(e) => {
                setTeacherFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "Barcha o‘qituvchilar" },
                ...teachers.map((t) => ({
                  value: t.id,
                  label: `${t.first_name} ${t.last_name ?? ""}`,
                })),
              ]}
            />
          </div>

          <div>
            <Select
              value={dayFilter}
              onChange={(e) => {
                setDayFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "Barcha kunlar" },
                ...DAYS_OF_WEEK.map((d) => ({
                  value: String(d.value),
                  label: d.label,
                })),
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
                { value: "active", label: "Faol guruhlar" },
                { value: "inactive", label: "Nofaol guruhlar" },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Error alert if any */}
      {error && !isLoading && groups.length > 0 && (
        <Alert variant="danger" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Content */}
      {isLoading && groups.length === 0 ? (
        <LoadingState message="Guruhlar ro‘yxati yuklanmoqda..." />
      ) : error && groups.length === 0 ? (
        <ErrorState title="Guruhlarni yuklab bo‘lmadi" message={error} onRetry={loadGroups} />
      ) : groups.length === 0 ? (
        <EmptyState
          title="Guruhlar topilmadi"
          description="Filtrlarga mos keluvchi guruhlar mavjud emas yoki ro‘yxat bo‘sh."
        />
      ) : (
        <div className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Guruh nomi</TableHead>
                <TableHead>Fan & O‘qituvchi</TableHead>
                <TableHead>Jadval & Vaqt</TableHead>
                <TableHead>Xona & Narx</TableHead>
                <TableHead>Bandlik</TableHead>
                <TableHead>Holati</TableHead>
                <TableHead className="text-right">Amallar</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {groups.map((group) => (
                <TableRow key={group.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600 shrink-0">
                        <Layers className="w-4 h-4" />
                      </div>
                      <span className="font-semibold text-slate-900">{group.name}</span>
                    </div>
                  </TableCell>

                  <TableCell>
                    <div className="text-xs">
                      <div className="font-medium text-slate-900">{group.subject?.name}</div>
                      <div className="text-slate-500 mt-0.5">
                        {group.teacher?.first_name} {group.teacher?.last_name}
                      </div>
                    </div>
                  </TableCell>

                  <TableCell>
                    <div className="text-xs space-y-0.5">
                      <div className="flex items-center gap-1 text-slate-700 font-medium">
                        <Calendar className="w-3.5 h-3.5 text-slate-400" />
                        {formatDaysOfWeek(group.days_of_week)}
                      </div>
                      <div className="flex items-center gap-1 text-slate-500 font-mono">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        {group.start_time?.slice(0, 5) ?? "Kiritilmagan"} - {group.end_time?.slice(0, 5) ?? "Kiritilmagan"}
                      </div>
                    </div>
                  </TableCell>

                  <TableCell>
                    <div className="text-xs space-y-0.5">
                      <div className="flex items-center gap-1 text-slate-800">
                        <DoorOpen className="w-3.5 h-3.5 text-slate-400" />
                        {group.room_number}
                      </div>
                      <div className="font-medium text-slate-600">
                        {formatPrice(group.monthly_price)}
                      </div>
                    </div>
                  </TableCell>

                  <TableCell>
                    <OccupancyBadge
                      current={group.current_students}
                      max={group.max_students}
                    />
                  </TableCell>

                  <TableCell>
                    {group.status === "active" ? (
                      <Badge variant="success">Faol</Badge>
                    ) : (
                      <Badge variant="danger">Nofaol</Badge>
                    )}
                  </TableCell>

                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      {canEdit && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            title="Tahrirlash"
                            onClick={() => handleOpenEdit(group)}
                            className="px-2"
                          >
                            <Edit2 className="w-4 h-4 text-slate-600" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            title={group.status === "active" ? "Nofaol qilish" : "Faollashtirish"}
                            onClick={() => handleToggleStatus(group)}
                            isLoading={togglingId === group.id}
                            className={`px-2 ${
                              group.status === "active"
                                ? "text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                                : "text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                            }`}
                          >
                            {group.status === "active" ? (
                              <XCircle className="w-4 h-4" />
                            ) : (
                              <CheckCircle2 className="w-4 h-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            title="O‘chirish"
                            onClick={() => setDeletingGroup(group)}
                            className="px-2 text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                          >
                            <Trash2 className="w-4 h-4" />
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
              Jami: <span className="font-semibold text-slate-900">{total}</span> ta guruh
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

      {/* Create/Edit Modal */}
      <GroupModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        group={editingGroup}
        onSuccess={() => loadGroups()}
      />

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={Boolean(deletingGroup)}
        onClose={() => setDeletingGroup(null)}
        title="Guruhni o‘chirish"
        description={`"${deletingGroup?.name}" guruhini tizimdan o‘chirishni tasdiqlaysizmi?`}
        size="sm"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeletingGroup(null)}
              disabled={isDeleting}
            >
              Bekor qilish
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleDeleteConfirm}
              isLoading={isDeleting}
            >
              O‘chirish
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-600">
          Agar guruhda ro‘yxatdan o‘tgan o‘quvchilar yoki davomat qaydlari bo‘lsa, guruhni o‘chirib bo‘lmaydi. U holda guruhni nofaol qilish lozim.
        </p>
      </Modal>
    </div>
  );
};
