import React, { useEffect, useState, useMemo } from "react";
import type { TeacherGroupItem } from "./types";
import { apiClient } from "../api/client";
import { formatDaysOfWeek, formatPrice } from "../academic/types";
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
  Layers,
  Search,
  CalendarCheck,
  Users,
  BookOpen,
  Clock,
  MapPin,
  RefreshCw,
} from "lucide-react";

export interface TeacherGroupsViewProps {
  onSelectGroupForAttendance?: (group: TeacherGroupItem) => void;
  onSelectGroupForStudents?: (group: TeacherGroupItem) => void;
}

export const TeacherGroupsView: React.FC<TeacherGroupsViewProps> = ({
  onSelectGroupForAttendance,
  onSelectGroupForStudents,
}) => {
  const [groups, setGroups] = useState<TeacherGroupItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const fetchGroups = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<TeacherGroupItem[]>("/api/v1/teacher/groups");
      setGroups(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Guruhlar ro‘yxatini yuklashda xatolik yuz berdi");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGroups();
  }, []);

  const filteredGroups = useMemo(() => {
    return groups.filter((group) => {
      if (statusFilter !== "all" && group.status !== statusFilter) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const matchesName = group.name.toLowerCase().includes(query);
        const matchesSubject = group.subject?.name.toLowerCase().includes(query);
        const matchesRoom = group.room_number?.toLowerCase().includes(query);
        if (!matchesName && !matchesSubject && !matchesRoom) {
          return false;
        }
      }
      return true;
    });
  }, [groups, statusFilter, searchQuery]);

  const stats = useMemo(() => {
    const totalGroups = groups.length;
    const activeGroups = groups.filter((g) => g.status === "active").length;
    const totalStudents = groups.reduce((acc, g) => acc + (g.current_students || 0), 0);
    return { totalGroups, activeGroups, totalStudents };
  }, [groups]);

  if (isLoading && groups.length === 0) {
    return <LoadingState message="Guruhlar ro‘yxati yuklanmoqda..." />;
  }

  if (error && groups.length === 0) {
    return (
      <ErrorState
        title="Guruhlarni yuklashda xatolik"
        message={error}
        onRetry={fetchGroups}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Title and Refresh button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Mening guruhlarim
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Sizga biriktirilgan dars guruhlari, jadvallar va to‘liq talabalar bandligi
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchGroups}
            isLoading={isLoading}
            leftIcon={<RefreshCw className="w-4 h-4" />}
          >
            Yangilash
          </Button>
        </div>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                Jami guruhlar
              </p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{stats.totalGroups}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Layers className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                Faol guruhlar
              </p>
              <p className="text-2xl font-bold text-emerald-600 mt-1">{stats.activeGroups}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <BookOpen className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                Jami o‘quvchilar
              </p>
              <p className="text-2xl font-bold text-indigo-600 mt-1">{stats.totalStudents}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Users className="w-5 h-5" />
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
              placeholder="Guruh, fan yoki xona nomi bo‘yicha qidirish..."
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

      {/* Main Groups Table */}
      {filteredGroups.length === 0 ? (
        <EmptyState
          title="Guruhlar topilmadi"
          description={
            searchQuery || statusFilter !== "all"
              ? "Qidiruv parametrlariga mos keladigan guruhlar mavjud emas."
              : "Sizga hozircha hech qanday guruh biriktirilmagan."
          }
        />
      ) : (
        <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Guruh va Fan</TableHead>
                <TableHead>Bandlik</TableHead>
                <TableHead>Dars kunlari</TableHead>
                <TableHead>Vaqt va Xona</TableHead>
                <TableHead>Oylik to‘lov</TableHead>
                <TableHead>Holat</TableHead>
                <TableHead className="text-right">Amallar</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredGroups.map((group) => {
                const startTime = group.start_time ? group.start_time.slice(0, 5) : "";
                const endTime = group.end_time ? group.end_time.slice(0, 5) : "";

                return (
                  <TableRow key={group.id}>
                    <TableCell>
                      <div>
                        <div className="font-semibold text-slate-900">{group.name}</div>
                        <div className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                          <BookOpen className="w-3 h-3 text-slate-400" />
                          <span>{group.subject?.name || "Fan biriktirilmagan"}</span>
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
                      <div className="text-sm font-medium text-slate-700">
                        {formatDaysOfWeek(group.days_of_week)}
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="space-y-0.5">
                        <div className="text-xs font-medium text-slate-800 flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          <span>
                            {startTime} - {endTime}
                          </span>
                        </div>
                        <div className="text-xs text-slate-500 flex items-center gap-1">
                          <MapPin className="w-3.5 h-3.5 text-slate-400" />
                          <span>{group.room_number || "Xona ko‘rsatilmagan"}</span>
                        </div>
                      </div>
                    </TableCell>

                    <TableCell>
                      <span className="text-sm font-medium text-slate-800">
                        {formatPrice(group.monthly_price)}
                      </span>
                    </TableCell>

                    <TableCell>
                      <Badge
                        variant={group.status === "active" ? "success" : "neutral"}
                        size="sm"
                      >
                        {group.status === "active" ? "Faol" : "Nofaol"}
                      </Badge>
                    </TableCell>

                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        {onSelectGroupForStudents && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onSelectGroupForStudents(group)}
                            leftIcon={<Users className="w-3.5 h-3.5" />}
                          >
                            Talabalar
                          </Button>
                        )}
                        {onSelectGroupForAttendance && (
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => onSelectGroupForAttendance(group)}
                            leftIcon={<CalendarCheck className="w-3.5 h-3.5" />}
                          >
                            Davomat
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
};
