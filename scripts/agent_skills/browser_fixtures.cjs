// Only synthetic identities/rosters. Intercepts every API request without a live fallback.
const ids = Object.fromEntries(['admin', 'teacher', 'subject', 'group', 'student', 'parent', 'campaign'].map((name, index) => [name, `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`]));
const now = '2026-10-13T09:00:00Z';
const user = { id: ids.admin, username: 'namuna_admin', first_name: 'Namuna', last_name: 'Administrator', phone: null,
  role: 'admin', status: 'active', permissions: [], telegram_connected: true, telegram_id: null };
const teacher = { ...user, id: ids.teacher, username: 'namuna_teacher', last_name: 'Ustoz', role: 'teacher', permissions: [], created_at: now };
const subject = { id: ids.subject, name: 'English', description: 'Namuna kurs', is_active: true, active_groups: 1, total_groups: 1, created_at: now };
const group = { id: ids.group, name: 'English A', subject_id: ids.subject, teacher_id: ids.teacher, subject,
  teacher, monthly_price: '500000.00', max_students: 15, current_students: 1, status: 'active', days_of_week: [1, 3, 5],
  start_time: '09:00:00', end_time: '10:30:00', room_number: '101', created_at: now, updated_at: now };
const link = { connected: true, deep_link: null, expires_at: null, expired: false };
const parent = { id: ids.parent, first_name: 'Namuna', last_name: 'Ota-ona', phone: '+998900000000',
  telegram_connected: true, telegram_link: link, created_at: now };
const student = { id: ids.student, first_name: 'Namuna', last_name: 'O‘quvchi', phone: null, age: 12, school_grade: '6',
  import_notes: [], status: 'active', group_id: ids.group, parent_id: ids.parent, telegram_connected: true,
  telegram_link: link, parent, created_at: now, group: { ...group, subject_name: 'English', teacher_name: 'Namuna Ustoz' },
  attendance_stats: { month: '2026-10', present_count: 1, late_count: 1, absent_count: 1, attended_count: 2, total_lessons: 3 } };
const zero = { pending: 0, delivered: 0, failed: 0, skipped: 0, cancelled: 0 };
const audience = { scope: 'groups', kind: 'both', group_ids: [ids.group], parent_ids: [], student_ids: [] };
const campaign = { id: ids.campaign, title: 'Dars haqida eslatma', body: 'English A: navbatdagi dars soat 09:00 da boshlanadi.', author_name: 'Namuna Administrator',
  created_at: now, cancelled_at: null, audience, status: 'queued', counts: { ...zero, pending: 1, delivered: 1, failed: 1 }, total: 3 };
const deliveries = ['delivered', 'pending', 'failed'].map((status, index) => ({ id: `delivery-${index}`, kind: 'parent', name: `Namuna ota-ona ${index + 1}`,
  group_names: ['English A'], status, attempts: status === 'pending' ? 0 : 1, last_error: status === 'failed' ? 'Bot bilan aloqa vaqtincha uzildi' : null,
  delivered_at: status === 'delivered' ? now : null, available_at: now, retried_at: null }));
const recipient = { id: ids.parent, kind: 'parent', name: 'Namuna Ota-ona', group_names: ['English A'], student_names: ['Namuna O‘quvchi'], connected: true, connection_reason: null };
const pageOf = (items, url) => ({ items, total: items.length, page: 1, page_size: Number(url.searchParams.get('page_size') || 10) });

async function installFixtures(page, state) {
  const unexpected = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (!path.startsWith('/api/')) return route.continue();
    const method = route.request().method();
    let body;
    if (path.endsWith('/me')) {
      if (state.loggedIn === false) return route.fulfill({ status: 401, json: { detail: 'Synthetic login required' } });
      body = state.user ?? user;
    } else if (path.endsWith('/login')) body = { challenge_id: ids.admin, expires_at: new Date(Date.now() + 180000).toISOString() };
    else if (path.endsWith('/confirm')) { state.loggedIn = true; body = state.user ?? user; }
    else if (path.endsWith('/health') || path.endsWith('/ready')) body = { status: 'ok', database: 'ok' };
    else if (path.endsWith('/dashboard/stats')) {
      const who = state.user ?? user;
      const perms = who.permissions;
      const full = who.role === 'superadmin';
      body = { groups_count: full || perms.includes('groups:read') ? 1 : null, students_count: full || perms.includes('students:read') ? 1 : null,
        staff_count: full || perms.includes('staff:manage') ? 2 : null, staff_breakdown: full || perms.includes('staff:manage') ? { teachers: 1, admins: 1, superadmins: 0 } : null };
    } else if (path.endsWith('/lookups/group-options')) body = { subjects: [subject], teachers: [teacher], rooms: [{ id: ids.group, name: '101', is_active: true }] };
    else if (path.endsWith('/lookups/student-groups')) body = pageOf([group], url);
    else if (path.endsWith('/settings/bot')) body = { configured: true, bot_username: 'namuna_bot', version: 7, active_version: 7, last_error: null,
      worker_ready: true, reload_in_progress: false, reconnect_required: 0 };
    else if (path.endsWith('/messages/groups')) body = [{ id: ids.group, name: 'English A', students: 1 }];
    else if (path.endsWith('/messages/recipients')) body = pageOf([url.searchParams.get('kind') === 'student' ? { ...recipient, id: ids.student, kind: 'student', name: 'Namuna O‘quvchi', student_names: [] } : recipient], url);
    else if (path.endsWith('/messages/preview')) {
      const draft = route.request().postDataJSON();
      body = { digest: 'a'.repeat(64), message: `NeoAvlod LMS\n\n${draft.title}\n\n${draft.body}`, bot_configured: true,
        total: 2, eligible: 2, unlinked: 0, duplicates: 0, parents: 1, students: 1, sample: [recipient] };
    } else if (path.endsWith('/messages')) body = method === 'GET' ? { ...pageOf([campaign], url), summary: campaign.counts } : { campaign, recipients: deliveries, total: 3, page: 1, page_size: 25 };
    else if (path.includes('/messages/')) body = { campaign, recipients: deliveries, total: 3, page: 1, page_size: 25 };
    else if (path.endsWith('/changes')) body = pageOf([{ id: 'change', student_name: 'Namuna O‘quvchi', actor_name: 'Namuna Administrator', actor_role: 'admin',
      action: 'correct', old_status: 'absent', new_status: 'present', old_note: null, new_note: 'Tekshirildi', reason: 'Jurnal solishtirildi', changed_at: now }], url);
    else if (path.includes('attendance-history') || path.endsWith('/attendance/history')) {
      const month = url.searchParams.get('month') || '2026-10';
      const dates = ['05', '07', '09'].map((day) => `${month}-${day}`);
      body = { group_id: ids.group, group_name: 'English A', month, dates,
        records: ['present', 'late', 'absent'].map((status, index) => ({ attendance_id: `record-${index}`, student_id: ids.student,
          student_name: 'Namuna O‘quvchi', date: dates[index], status, note: null })),
        students_summary: [{ student_id: ids.student, student_name: 'Namuna O‘quvchi', ...student.attendance_stats }],
        summary: { total_lessons: 3, total_records: 3, present_count: 1, late_count: 1, absent_count: 1 } };
    } else if (path.includes('/groups/') && path.includes('/attendance')) {
      const payload = method === 'POST' ? route.request().postDataJSON() : null;
      const day = url.searchParams.get('date') || payload?.date || '2026-10-12';
      const end = new Date(`${day}T18:59:59Z`); end.setUTCDate(end.getUTCDate() + 2);
      body = { group_id: ids.group, date: day, finalized: Boolean(state.finalized),
        finalized_at: state.finalized ? now : null, can_edit: true, edit_deadline: state.user?.role === 'teacher' ? end.toISOString() : null, edit_disabled_reason: null,
        items: [{ student_id: ids.student, student_first_name: 'Namuna', student_last_name: 'O‘quvchi',
          status: payload?.items?.[0]?.status || 'present', note: payload?.items?.[0]?.note || (state.finalized ? 'Tekshirildi' : null), marked_at: now }] };
    } else if (path.endsWith('/pending')) body = [];
    else if (path.endsWith('/attendance/groups')) body = [{ id: ids.group, name: 'English A', teacher_id: ids.teacher, teacher_name: 'Namuna Ustoz' }];
    else if (path.endsWith('/admin/attendance')) body = pageOf([], url);
    else if (path.endsWith('/subjects')) body = pageOf([subject], url);
    else if (path.endsWith('/staff')) body = pageOf([teacher], url);
    else if (path.includes('/staff/')) body = { ...teacher, telegram_link: link };
    else if (path.endsWith('/groups')) body = path.includes('/teacher/') ? [group] : pageOf([group], url);
    else if (path.endsWith('/students')) body = path.includes('/teacher/') ? [{ ...student, group_name: 'English A' }] : pageOf([student], url);
    else if (path.includes('/students/')) body = path.includes('/teacher/') ? { ...student, group_name: 'English A', subject_name: 'English', teacher_name: 'Namuna Ustoz', days_of_week: group.days_of_week,
      start_time: group.start_time, end_time: group.end_time, room_number: '101', monthly_price: group.monthly_price } : student;
    else if (path.includes('/groups/')) body = group;
    else { unexpected.push(`${method} ${path}`); return route.fulfill({ status: 403, json: { detail: 'Synthetic endpoint is not enabled' } }); }
    await route.fulfill({ json: body });
  });
  return unexpected;
}
module.exports = { ids, user, teacher, subject, group, student, parent, campaign, installFixtures };
