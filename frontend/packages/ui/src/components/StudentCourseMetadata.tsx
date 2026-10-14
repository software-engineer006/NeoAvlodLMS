/** Presentation-only course metadata shared by both portals. */
export interface CourseMetadata {
  level?: string | null;
  mygov_status?: string | null;
  notes?: string | null;
}
export function StudentCourseMetadata({ level, mygov_status, notes }: CourseMetadata) {
  if (!level && !mygov_status && !notes) return null;
  return <dl className="space-y-1 rounded-lg bg-slate-50 p-3 text-xs">
    {[["Daraja", level], ["MyGov holati", mygov_status], ["Kurs izohi", notes]].map(([label, value]) => value &&
      <div key={label} className="min-w-0"><dt className="font-semibold text-slate-600">{label}</dt>
        <dd className="whitespace-pre-wrap break-words">{value}</dd></div>)}
  </dl>;
}
