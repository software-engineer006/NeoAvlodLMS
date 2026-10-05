import React, { useState, useEffect, useCallback } from "react";
import type { CurrentUser } from "../api/types";
import type { StaffItem, StaffDetailItem, StaffListResponse, TelegramLinkState } from "./types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Card } from "../components/Card";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Alert } from "../components/Alert";
import { ErrorState } from "../components/ErrorState";
import { StaffTable } from "./StaffTable";
import { StaffModal } from "./StaffModal";
import { TelegramLinkModal } from "./TelegramLinkModal";
import { UserPlus, Search, RefreshCw } from "lucide-react";

export interface StaffManagementViewProps {
  currentUser: CurrentUser;
}

export const StaffManagementView: React.FC<StaffManagementViewProps> = ({ currentUser }) => {
  const [staffList, setStaffList] = useState<StaffItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 10;

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusTogglingId, setStatusTogglingId] = useState<string | null>(null);

  // Modal states
  const [isStaffModalOpen, setIsStaffModalOpen] = useState<boolean>(false);
  const [editingStaff, setEditingStaff] = useState<StaffItem | null>(null);

  const [isTelegramModalOpen, setIsTelegramModalOpen] = useState<boolean>(false);
  const [selectedStaffForTelegram, setSelectedStaffForTelegram] = useState<StaffItem | null>(null);
  const [telegramLinkState, setTelegramLinkState] = useState<TelegramLinkState | null>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const loadStaff = useCallback(async () => {
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
      if (roleFilter !== "all") {
        params.role = roleFilter;
      }
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }

      const res = await apiClient.get<StaffListResponse>("/api/v1/admin/staff", { params });
      setStaffList(res.items);
      setTotal(res.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Xodimlar ro‘yxatini yuklashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, debouncedSearch, roleFilter, statusFilter]);

  useEffect(() => {
    loadStaff();
  }, [loadStaff]);

  const handleOpenCreateModal = () => {
    setEditingStaff(null);
    setIsStaffModalOpen(true);
  };

  const handleOpenEditModal = (staff: StaffItem) => {
    setEditingStaff(staff);
    setIsStaffModalOpen(true);
  };

  const handleStaffSaved = (saved: StaffItem) => {
    // Check if new or updated
    loadStaff();
    // If it was created, optionally open telegram modal if telegram_link was provided
    const detail = saved as StaffDetailItem;
    if (detail.telegram_link) {
      setSelectedStaffForTelegram(saved);
      setTelegramLinkState(detail.telegram_link);
      setIsTelegramModalOpen(true);
    }
  };

  const handleToggleStatus = async (staff: StaffItem) => {
    setStatusTogglingId(staff.id);
    try {
      if (staff.status === "active") {
        await apiClient.post(`/api/v1/admin/staff/${staff.id}/deactivate`);
      } else {
        await apiClient.post(`/api/v1/admin/staff/${staff.id}/activate`);
      }
      await loadStaff();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Xodim holatini o‘zgartirishda xatolik yuz berdi");
      }
    } finally {
      setStatusTogglingId(null);
    }
  };

  const handleOpenTelegramModal = async (staff: StaffItem) => {
    setSelectedStaffForTelegram(staff);
    setTelegramLinkState(null);
    setIsTelegramModalOpen(true);
    try {
      const detail = await apiClient.get<StaffDetailItem>(`/api/v1/admin/staff/${staff.id}`);
      if (detail.telegram_link) {
        setTelegramLinkState(detail.telegram_link);
      }
    } catch {
      // If error loading current link, modal allows rotating a new one
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Xodimlar boshqaruvi</h1>
          <p className="text-sm text-slate-500 mt-1">
            O‘qituvchilar va administratorlar hisoblarini boshqarish hamda Telegramga ulash
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadStaff()}
            disabled={isLoading}
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
          >
            Yangilash
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleOpenCreateModal}
            leftIcon={<UserPlus className="w-4 h-4" />}
          >
            Yangi xodim
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="sm:col-span-1">
            <Input
              placeholder="Qidiruv (ism, familiya, login)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftAddon={<Search className="w-4 h-4 text-slate-400" />}
            />
          </div>
          <div>
            <Select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "all", label: "Barcha rollar" },
                { value: "teacher", label: "O‘qituvchi" },
                { value: "admin", label: "Administrator" },
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
                { value: "active", label: "Faol" },
                { value: "inactive", label: "Nofaol" },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Error alert if any */}
      {error && !isLoading && staffList.length > 0 && (
        <Alert variant="danger" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Main Table or Error State */}
      {error && staffList.length === 0 ? (
        <ErrorState
          title="Xodimlarni yuklab bo‘lmadi"
          message={error}
          onRetry={loadStaff}
        />
      ) : (
        <StaffTable
          staffList={staffList}
          isLoading={isLoading}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          currentUser={currentUser}
          onEdit={handleOpenEditModal}
          onToggleStatus={handleToggleStatus}
          onOpenTelegramModal={handleOpenTelegramModal}
          isStatusTogglingId={statusTogglingId}
        />
      )}

      {/* Modals */}
      <StaffModal
        isOpen={isStaffModalOpen}
        onClose={() => setIsStaffModalOpen(false)}
        staff={editingStaff}
        currentUser={currentUser}
        onSuccess={handleStaffSaved}
      />

      <TelegramLinkModal
        isOpen={isTelegramModalOpen}
        onClose={() => setIsTelegramModalOpen(false)}
        staff={selectedStaffForTelegram}
        linkState={telegramLinkState}
        onLinkUpdated={(newLink) => setTelegramLinkState(newLink)}
      />
    </div>
  );
};
