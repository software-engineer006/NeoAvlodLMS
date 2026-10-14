export interface SceneField {
  label: string;
  value?: string;
  placeholder?: string;
  type?: "text" | "password" | "date" | "time";
  options?: string[];
}
export interface SceneRegion {
  title?: string;
  fields?: SceneField[];
  buttons?: string[];
  note?: string;
  badges?: string[];
  stats?: { label: string; value: string }[];
  table?: { columns: string[]; rows: string[][] };
}
export interface GuideScene {
  title: string;
  subtitle?: string;
  regions: SceneRegion[];
}
