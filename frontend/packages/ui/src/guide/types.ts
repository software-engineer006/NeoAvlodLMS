import type { CurrentUser, PortalType } from "../api/types";
import { hasPermission, type PermissionKey } from "../navigation/permissions";
import type { GuideScene } from "./scenes/types";

export interface GuideStep {
  title: string;
  text: string;
}
export interface GuideTopic {
  id: string;
  title: string;
  section: string;
  summary: string;
  permission?: PermissionKey;
  requiresAll?: PermissionKey[];
  superadminOnly?: boolean;
  scene: GuideScene;
  previewAlt: string;
  steps: GuideStep[];
  tips: string[];
  destination?: string;
}
export function canReadGuide(user: CurrentUser, portal: PortalType): boolean {
  return (
    user.status === "active" &&
    (portal === "admin"
      ? user.role === "admin" || user.role === "superadmin"
      : user.role === "teacher")
  );
}
export function visibleGuideTopics(
  user: CurrentUser,
  portal: PortalType,
  topics: GuideTopic[],
): GuideTopic[] {
  if (!canReadGuide(user, portal)) return [];
  return topics.filter(
    (topic) =>
      (!topic.superadminOnly || user.role === "superadmin") &&
      (!topic.permission || hasPermission(user, topic.permission)) &&
      (topic.requiresAll ?? []).every((permission) =>
        hasPermission(user, permission),
      ),
  );
}
export function guideSearch(value: string): string {
  return value
    .toLocaleLowerCase("uz-UZ")
    .replace(/[‘’ʻʼ`]/g, "'")
    .normalize("NFKC")
    .trim();
}
