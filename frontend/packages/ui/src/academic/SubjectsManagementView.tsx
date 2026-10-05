import React, { useState, useEffect, useCallback } from "react";
import type { CurrentUser } from "../api/types";
import type { SubjectItem, SubjectListResponse } from "./types";
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
import { SubjectModal } from "./SubjectModal";
import { BookOpen, Plus, Search, RefreshCw, Edit2, Trash2, CheckCircle2, XCircle } from "lucide-react";

export interface SubjectsManagementViewProps {
  currentUser: CurrentUser;
}

export const SubjectsManagementView: React.FC<SubjectsManagementViewProps> = ({ currentUser: _currentUser }) => {
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 10;

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingSubject, setEditingSubject] = useState<SubjectItem | null>(null);
  const [deletingSubject, setDeletingSubject] = useState<SubjectItem | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const loadSubjects = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | boolean> = {
        page,
        page_size: pageSize,
      };
      if (debouncedSearch.trim()) {
        params.q = debouncedSearch.trim();
      }
      if (statusFilter === "active") {
        params.is_active = true;
      } else if (statusFilter === "inactive") {
        params.is_active = false;
      }

      const res = await apiClient.get<SubjectListResponse>("/api/v1/admin/subjects", { params });
      setSubjects(res.items);
      setTotal(res.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Fanlar ro‘yxatini yuklashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, debouncedSearch, statusFilter]);

  useEffect(() => {
    loadSubjects();
  }, [loadSubjects]);

  const handleOpenCreate = () => {
    setEditingSubject(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (subject: SubjectItem) => {
    setEditingSubject(subject);
    setIsModalOpen(true);
  };

  const handleToggleStatus = async (subject: SubjectItem) => {
    setTogglingId(subject.id);
    try {
      if (subject.is_active) {
        await apiClient.post(`/api/v1/admin/subjects/${subject.id}/deactivate`);
      } else {
        await apiClient.post(`/api/v1/admin/subjects/${subject.id}/activate`);
      }
      await loadSubjects();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Fan holatini o‘zgartirishda xatolik yuz berdi");
      }
    } finally {
      setTogglingId(null);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deletingSubject) return;
    setIsDeleting(true);
    try {
      await apiClient.delete(`/api/v1/admin/subjects/${deletingSubject.id}`);
      setDeletingSubject(null);
      await loadSubjects();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Fanni o‘chirishda xatolik yuz berdi");
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
          <h1 className="text-2xl font-bold text-slate-900">Fanlar boshqaruvi</h1>
          <p className="text-sm text-slate-500 mt-1">
            O‘quv yo‘nalishlari, kurslar va ularga biriktirilgan guruhlar statistikasi
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadSubjects()}
            disabled={isLoading}
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
          >
            Yangilash
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleOpenCreate}
            leftIcon={<Plus className="w-4 h-4" />}
          >
            Yangi fan
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="sm:col-span-2">
            <Input
              placeholder="Fan nomi bo‘yicha qidiruv..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftAddon={<Search className="w-4 h-4 text-slate-400" />}
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
                { value: "active", label: "Faol fanlar" },
                { value: "inactive", label: "Nofaol fanlar" },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Error alert if any */}
      {error && !isLoading && subjects.length > 0 && (
        <Alert variant="danger" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Content */}
      {isLoading && subjects.length === 0 ? (
        <LoadingState message="Fanlar ro‘yxati yuklanmoqda..." />
      ) : error && subjects.length === 0 ? (
        <ErrorState title="Fanlarni yuklab bo‘lmadi" message={error} onRetry={loadSubjects} />
      ) : subjects.length === 0 ? (
        <EmptyState
          title="Fanlar topilmadi"
          description="Hozircha hech qanday fan kiritilmagan yoki qidiruv natijasi bo‘sh."
        />
      ) : (
        <div className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fan nomi va tavsif</TableHead>
                <TableHead>Holati</TableHead>
                <TableHead>Guruhlar soni</TableHead>
                <TableHead>Yaratilgan sana</TableHead>
                <TableHead className="text-right">Amallar</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {subjects.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="flex items-start gap-2.5">
                      <div className="p-2 rounded-lg bg-blue-50 text-blue-600 shrink-0 mt-0.5">
                        <BookOpen className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="font-semibold text-slate-900">{item.name}</div>
                        {item.description ? (
                          <p className="text-xs text-slate-500 line-clamp-1 mt-0.5 max-w-md">
                            {item.description}
                          </p>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Tavsif berilmagan</span>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    {item.is_active ? (
                      <Badge variant="success">Faol</Badge>
                    ) : (
                      <Badge variant="danger">Nofaol</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="text-xs text-slate-700">
                      <span className="font-semibold text-slate-900">{item.active_groups}</span> faol guruh
                      <span className="text-slate-400 ml-1">/ {item.total_groups} jami</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-xs text-slate-500">
                      {new Date(item.created_at).toLocaleDateString("uz-UZ")}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Tahrirlash"
                        onClick={() => handleOpenEdit(item)}
                        className="px-2"
                      >
                        <Edit2 className="w-4 h-4 text-slate-600" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        title={item.is_active ? "Nofaol qilish" : "Faollashtirish"}
                        onClick={() => handleToggleStatus(item)}
                        isLoading={togglingId === item.id}
                        className={`px-2 ${
                          item.is_active
                            ? "text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                            : "text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                        }`}
                      >
                        {item.is_active ? (
                          <XCircle className="w-4 h-4" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        title="O‘chirish"
                        onClick={() => setDeletingSubject(item)}
                        className="px-2 text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-1 py-2 text-xs text-slate-600">
            <div>
              Jami: <span className="font-semibold text-slate-900">{total}</span> ta fan
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
      <SubjectModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        subject={editingSubject}
        onSuccess={() => loadSubjects()}
      />

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={Boolean(deletingSubject)}
        onClose={() => setDeletingSubject(null)}
        title="Fanni o‘chirish"
        description={`"${deletingSubject?.name}" fanini tizimdan o‘chirishni tasdiqlaysizmi?`}
        size="sm"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeletingSubject(null)}
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
          Agar ushbu fanga biriktirilgan guruhlar mavjud bo‘lsa, fanni o‘chirib bo‘lmaydi. U holda fanni nofaol qilish tavsiya etiladi.
        </p>
      </Modal>
    </div>
  );
};
