import React, { useState, useEffect, useCallback } from "react";
import type { DashboardStats } from "../api/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { Card, CardContent, CardHeader, CardTitle } from "../components/Card";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { ErrorState } from "../components/ErrorState";
import { Layers, GraduationCap, Users, RefreshCw, ArrowRight } from "lucide-react";

export interface DashboardStatsCardsProps {
  onNavigate?: (tabId: string) => void;
  className?: string;
}

export const DashboardStatsCards: React.FC<DashboardStatsCardsProps> = ({
  onNavigate,
  className = "",
}) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<DashboardStats>("/api/v1/admin/dashboard/stats");
      setStats(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Statistika ko‘rsatkichlarini yuklashda xatolik yuz berdi");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  if (isLoading) {
    return (
      <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 ${className}`}>
        {[1, 2, 3].map((idx) => (
          <Card key={idx} className="p-6 animate-pulse">
            <div className="flex items-center justify-between pb-2">
              <div className="h-4 bg-slate-200 rounded w-24" />
              <div className="w-8 h-8 bg-slate-200 rounded-lg" />
            </div>
            <div className="h-8 bg-slate-200 rounded w-16 my-2" />
            <div className="h-3 bg-slate-200 rounded w-40" />
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card className={`p-4 ${className}`}>
        <ErrorState
          title="Statistika yuklanmadi"
          message={error}
          onRetry={loadStats}
        />
      </Card>
    );
  }

  if (!stats) {
    return null;
  }

  const hasAnyStat =
    stats.groups_count !== null ||
    stats.students_count !== null ||
    stats.staff_count !== null;

  if (!hasAnyStat) {
    return (
      <Card className={`p-6 text-center text-slate-500 text-sm ${className}`}>
        Ushbu hisob uchun statistik ko‘rsatkichlar ruxsati berilmagan.
      </Card>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">
          Asosiy ko‘rsatkichlar
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={loadStats}
          disabled={isLoading}
          className="text-xs text-slate-500 hover:text-slate-800 gap-1.5"
          leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
        >
          Yangilash
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Faol Guruhlar */}
        {stats.groups_count !== null && (
          <Card className="hover:shadow-md transition-shadow relative overflow-hidden group">
            <div className="absolute top-0 left-0 right-0 h-1 bg-blue-600" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">Guruhlar</CardTitle>
              <div className="w-9 h-9 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                <Layers className="w-5 h-5" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <div className="text-3xl font-extrabold text-slate-900 tracking-tight">
                  {stats.groups_count}
                </div>
                <Badge variant="success" size="sm">Faol</Badge>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Tizimdagi barcha faol o‘quv guruhlari soni
              </p>
              {onNavigate && (
                <button
                  type="button"
                  onClick={() => onNavigate("groups")}
                  className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                >
                  Guruhlarni ko‘rish
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </button>
              )}
            </CardContent>
          </Card>
        )}

        {/* Faol O‘quvchilar */}
        {stats.students_count !== null && (
          <Card className="hover:shadow-md transition-shadow relative overflow-hidden group">
            <div className="absolute top-0 left-0 right-0 h-1 bg-emerald-600" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">O‘quvchilar</CardTitle>
              <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <GraduationCap className="w-5 h-5" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <div className="text-3xl font-extrabold text-slate-900 tracking-tight">
                  {stats.students_count}
                </div>
                <Badge variant="success" size="sm">Faol</Badge>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Tizimda ta’lim olayotgan faol o‘quvchilar soni
              </p>
              {onNavigate && (
                <button
                  type="button"
                  onClick={() => onNavigate("students")}
                  className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 transition-colors"
                >
                  O‘quvchilarni ko‘rish
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </button>
              )}
            </CardContent>
          </Card>
        )}

        {/* Faol Xodimlar */}
        {stats.staff_count !== null && (
          <Card className="hover:shadow-md transition-shadow relative overflow-hidden group">
            <div className="absolute top-0 left-0 right-0 h-1 bg-purple-600" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">Xodimlar</CardTitle>
              <div className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
                <Users className="w-5 h-5" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <div className="text-3xl font-extrabold text-slate-900 tracking-tight">
                  {stats.staff_count}
                </div>
                <Badge variant="success" size="sm">Faol</Badge>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                {stats.staff_breakdown
                  ? `${stats.staff_breakdown.teachers} ta o‘qituvchi, ${stats.staff_breakdown.admins} ta admin, ${stats.staff_breakdown.superadmins} ta superadmin`
                  : "Superadmin, admin va o‘qituvchilar jami"}
              </p>
              {onNavigate && (
                <button
                  type="button"
                  onClick={() => onNavigate("staff")}
                  className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-purple-600 hover:text-purple-700 transition-colors"
                >
                  Xodimlarni boshqarish
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </button>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};
