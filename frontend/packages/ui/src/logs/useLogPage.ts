import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { LogPage } from "./types";

export interface LogFilters { day: string; actor_id: string; action: string; outcome: string; entity: string }
export function useLogPage(allowed: boolean, userId: string, filters: LogFilters, cursor: string, revision: number) {
  const { day, actor_id, action, outcome, entity } = filters;
  const key = JSON.stringify([userId, day, actor_id, action, outcome, entity, cursor, revision]);
  const [state, setState] = useState<{ key: string; data: LogPage | null; error: string | null }>({ key: "", data: null, error: null });
  useEffect(() => {
    if (!allowed || !day) return;
    const controller = new AbortController();
    setState({ key, data: null, error: null });
    apiClient.get<LogPage>("/api/v1/admin/logs", { signal: controller.signal,
      params: { day, actor_id: actor_id || undefined, action: action || undefined,
        outcome: outcome || undefined, entity: entity || undefined, cursor: cursor || undefined },
    }).then((data) => { if (!controller.signal.aborted) setState({ key, data, error: null }); })
      .catch((error: unknown) => { if (!controller.signal.aborted) setState({ key, data: null,
        error: error instanceof Error ? error.message : "Loglarni yuklab bo‘lmadi" }); });
    return () => controller.abort();
  }, [allowed, key, day, actor_id, action, outcome, entity, cursor]);
  const current = state.key === key ? state : { data: null, error: null };
  return { ...current, loading: allowed && Boolean(day) && !current.data && !current.error };
}
