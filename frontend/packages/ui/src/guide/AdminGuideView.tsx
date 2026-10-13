import type { CurrentUser } from "../api/types";
import { GuideView } from "./GuideView";
import { adminTopics } from "./adminTopics";

export function AdminGuideView({
  currentUser,
  onNavigate,
}: {
  currentUser: CurrentUser;
  portal?: "admin";
  onNavigate?: (tab: string) => void;
}) {
  return (
    <GuideView
      currentUser={currentUser}
      portal="admin"
      topics={adminTopics}
      onNavigate={onNavigate}
    />
  );
}
