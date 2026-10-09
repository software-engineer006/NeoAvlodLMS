import React from "react";
import type { CurrentUser } from "../api/types";
import type { StaffItem } from "./types";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/Table";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { Edit2, Send, UserX, UserCheck, CheckCircle2, XCircle } from "lucide-react";

export interface StaffTableProps {
  staffList: StaffItem[];
  isLoading: boolean;
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (newPage: number) => void;
  currentUser: CurrentUser;
  onEdit: (staff: StaffItem) => void;
  onToggleStatus: (staff: StaffItem) => void;
  onOpenTelegramModal: (staff: StaffItem) => void;
  isStatusTogglingId?: string | null;
}

export const StaffTable: React.FC<StaffTableProps> = ({
  staffList,
  isLoading,
  total,
  page,
  pageSize,
  onPageChange,
  currentUser,
  onEdit,
  onToggleStatus,
  onOpenTelegramModal,
  isStatusTogglingId,
}) => {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (isLoading && staffList.length === 0) {
    return <LoadingState message="Xodimlar ro‘yxati yuklanmoqda..." />;
  }

  if (!isLoading && staffList.length === 0) {
    return (
      <EmptyState
        title="Xodimlar topilmadi"
        description="Qidiruv shartlariga mos xodimlar mavjud emas yoki ro‘yxat bo‘sh."
      />
    );
  }

  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Xodim</TableHead>
            <TableHead>Telefon</TableHead>
            <TableHead>Roli</TableHead>
            <TableHead>Holati</TableHead>
            <TableHead>Telegram</TableHead>
            <TableHead className="text-right">Amallar</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {staffList.map((staff) => {
            const isSelf = staff.id === currentUser.id;
            const isSuperadmin = currentUser.role === "superadmin";
            const canManage = isSuperadmin || (currentUser.role === "admin" && staff.role === "teacher");

            return (
              <TableRow key={staff.id}>
                <TableCell>
                  <div className="font-medium text-slate-900">
                    {staff.first_name} {staff.last_name}
                  </div>
                  <div className="text-xs text-slate-500 font-mono">@{staff.username}</div>
                </TableCell>
                <TableCell>
                  <span className="font-mono text-xs text-slate-700">{staff.phone ?? "Kiritilmagan"}</span>
                </TableCell>
                <TableCell>
                  {staff.role === "superadmin" ? (
                    <Badge variant="danger">Bosh admin</Badge>
                  ) : staff.role === "admin" ? (
                    <Badge variant="warning">Administrator</Badge>
                  ) : (
                    <Badge variant="neutral">O‘qituvchi</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {staff.status === "active" ? (
                    <Badge variant="success">Faol</Badge>
                  ) : (
                    <Badge variant="danger">Nofaol</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {staff.telegram_connected ? (
                    <span className="inline-flex items-center gap-1.5 text-xs text-emerald-700 font-medium">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      Bog‘langan
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                      <XCircle className="w-4 h-4 text-slate-400" />
                      Bog‘lanmagan
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      title="Telegram onboarding havolasi"
                      onClick={() => onOpenTelegramModal(staff)}
                      className="px-2"
                    >
                      <Send className="w-4 h-4 text-slate-600" />
                    </Button>

                    {canManage && (
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Tahrirlash"
                        onClick={() => onEdit(staff)}
                        className="px-2"
                      >
                        <Edit2 className="w-4 h-4 text-slate-600" />
                      </Button>
                    )}

                    {canManage && !isSelf && (
                      <Button
                        variant="ghost"
                        size="sm"
                        title={staff.status === "active" ? "Nofaol qilish" : "Faollashtirish"}
                        onClick={() => onToggleStatus(staff)}
                        isLoading={isStatusTogglingId === staff.id}
                        className={`px-2 ${
                          staff.status === "active"
                            ? "text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                            : "text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                        }`}
                      >
                        {staff.status === "active" ? (
                          <UserX className="w-4 h-4" />
                        ) : (
                          <UserCheck className="w-4 h-4" />
                        )}
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      {/* Pagination & stats */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-1 py-2 text-xs text-slate-600">
        <div>
          Jami: <span className="font-semibold text-slate-900">{total}</span> ta xodim
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
              onClick={() => onPageChange(page - 1)}
            >
              Oldingi
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages || isLoading}
              onClick={() => onPageChange(page + 1)}
            >
              Keyingi
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};
