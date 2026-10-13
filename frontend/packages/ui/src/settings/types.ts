export interface BotSettingsItem {
  configured: boolean;
  bot_username: string | null;
  version: number;
  active_version: number;
  last_error: string | null;
  reload_in_progress: boolean;
  bot_id?: number | null;
  worker_ready?: boolean;
  reconnect_required?: number;
}

export interface BotTokenUpdateInput {
  token: string;
}
