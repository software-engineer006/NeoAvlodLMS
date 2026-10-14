import type { RoleType } from "../api/types";

export type AuditValue = null | boolean | number | string | AuditValue[] | { [key: string]: AuditValue };
export interface LogActor {
  id: string;
  name: string;
  username: string | null;
  role: RoleType;
}
export interface LogEvent {
  id: string;
  at: string;
  day: string;
  actor: LogActor | null;
  action: string;
  entity: { type: string | null; id: string | null; name: string | null };
  changes: Record<string, { before: AuditValue; after: AuditValue }>;
  private_changed: string[];
  details: Record<string, AuditValue>;
  source: string;
  request_id: string | null;
}
export interface LogPage {
  items: LogEvent[];
  actors: LogActor[];
  actions: string[];
  total: number;
  next_cursor: string | null;
  page_size: number;
}
export interface LogDay { day: string; count: number }
