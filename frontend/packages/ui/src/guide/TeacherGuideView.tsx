import type { CurrentUser } from "../api/types";
import { GuideView } from "./GuideView";
import { teacherTopics } from "./teacherTopics";

export function TeacherGuideView({
  currentUser,
  onNavigate,
}: {
  currentUser: CurrentUser;
  onNavigate?: (tab: string) => void;
}) {
  return (
    <GuideView
      currentUser={currentUser}
      portal="teacher"
      topics={teacherTopics}
      onNavigate={onNavigate}
    />
  );
}
