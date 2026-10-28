export type Role =
  "owner" | "admin" | "manager" | "telecaller" | "field_executive";
export interface User {
  id: string;
  name: string;
  phone: string;
  role: Role;
  active: boolean;
  org_id: string | null;
  totp_enabled: boolean;
  created_at: string;
}
export interface Organization {
  id: string;
  name: string;
  active: boolean;
  settings: WorkspaceSettings;
  created_at: string;
  users?: number;
  leads?: number;
}
export interface Workplace {
  name: string;
  latitude: number;
  longitude: number;
  accuracy: number;
  radius: number;
  timezone: string;
}
export interface WorkspaceSettings {
  industry?: string;
  company_profile?: import("./estate-types").CompanyProfile;
  brand_name?: string;
  logo_id?: string;
  workplace?: Workplace;
  pharma_enabled?: boolean;
  weekdays?: number[];
  daily_hours?: string;
}
export interface Session {
  access_token: string;
  user: User;
  role: Role;
  organization: Organization | null;
  support: boolean;
  support_until?: string;
  acting_as?: {
    administrator: { id: string; name: string };
    until: string;
  };
  challenge_required?: boolean;
  challenge?: string;
}
export interface Lead {
  id: string;
  name: string;
  phone: string;
  city: string;
  state: string;
  source: string;
  status: string;
  stage: string;
  owner_id: string | null;
  owner_name: string;
  dnd: boolean;
  notes: string;
  category: string;
  interests: string[];
  custom: Record<string, unknown>;
  details: Record<string, unknown>;
  created_at: string;
  last_contact: string | null;
  follow_up: string | null;
  lost_reason: string;
  reported_by: string | null;
  score: { value: number; band: string; factors: Record<string, number> };
}
export interface Task {
  field_handoff_id?: string | null;
  id: string;
  title: string;
  description: string;
  lead_id: string | null;
  owner_id: string;
  creator_id: string;
  due_at: string;
  state: string;
  kind: string;
  priority: string;
  completed_at: string | null;
}
export interface FileItem {
  id: string;
  name: string;
  mime: string;
  size: number;
  created_at: string;
  phone_call_id: string | null;
  lead_id: string | null;
  author_id: string;
}
export interface PhoneCall {
  id: string;
  lead_id: string;
  lead_name: string;
  user_id: string;
  user_name: string;
  phone: string;
  direction: string;
  result: string;
  duration: number;
  started_at: string;
  recording_state: string;
  recordings: FileItem[];
}
export interface Note {
  id: string;
  text: string;
  author_id: string;
  created_at: string;
}
export interface ManualCall {
  id: string;
  outcome: string;
  notes: string;
  user_id: string;
  duration: number;
  order_value: string;
  created_at: string;
  phone_call_id: string | null;
}
export interface Audit {
  id: string;
  actor_id: string | null;
  entity: string;
  action: string;
  summary: string;
  created_at: string;
  details: Record<string, unknown>;
}
export interface Assignment {
  id: string;
  owner_id: string;
  previous_id: string | null;
  actor_id: string;
  source: string;
  created_at: string;
}
export interface History {
  pagination: { page: number; size: number; totals: Record<string, number> };
  notes: Note[];
  manual_calls: ManualCall[];
  phone_calls: PhoneCall[];
  files: FileItem[];
  tasks: Task[];
  assignments: Assignment[];
  activity: Audit[];
  people: Record<string, string>;
}
export interface Definition {
  id: string;
  kind: "field" | "category" | "stage";
  key: string;
  label: string;
  config: {
    type?: string;
    required?: boolean;
    options?: string[];
    color?: string;
    closed?: boolean;
    won?: boolean;
  };
  active: boolean;
  position: number;
}
export interface Attendance {
  id: string;
  user_id: string;
  day: string;
  checked_in: string;
  checked_out: string | null;
  auto_closed: boolean;
  cutoff: string;
  location: { accuracy: number; distance_m: number };
}
export interface Submission {
  id: string;
  user_id: string;
  day?: string;
  hours?: string;
  category?: string;
  description?: string;
  source?: string;
  starts_on?: string;
  ends_on?: string;
  kind?: string;
  reason?: string;
  state: string;
  review_note: string;
  reviewer_id: string | null;
}
export interface SavedView {
  id: string;
  name: string;
  kind: string;
  filters: Record<string, string>;
}
export interface Automation {
  id: string;
  name: string;
  trigger: string;
  conditions: Record<string, string>;
  action: string;
  config: Record<string, unknown>;
  enabled: boolean;
}
export interface AutomationRun {
  id: string;
  rule_id: string;
  state: string;
  error: string;
  created_at: string;
}
export interface Integration {
  id?: string;
  provider: string;
  state: string;
  configured: boolean;
  enabled?: boolean;
  last_sync?: string;
  last_error?: string;
}
export interface SyncRun {
  id: string;
  state: string;
  imported: number;
  duplicates: number;
  invalid: number;
  error: string;
  created_at: string;
}
export interface ImportResult {
  accepted: number;
  imported: number;
  duplicates: number;
  invalid: number;
  blank_rows: number;
  skipped: number;
  errors: { row: number; column: string; message: string }[];
  preview: Partial<Lead>[];
  import_id?: string;
  replayed?: boolean;
  owner?: string;
}
export interface PayRow {
  user_id: string;
  name: string;
  active: boolean;
  hourly_rate: string;
  daily_target: string;
  approved_hours: string;
  pending_hours: string;
  approved_leave_days: number;
  target_hours: string;
  estimated_pay: string;
  working_days: number;
  pay_basis: "work" | "office_calls";
  call_hourly_rate: string;
  office_hours: string;
  approved_office_hours: string;
  pending_office_hours: string;
  call_hours: string;
  non_call_office_hours: string;
  base_paid_hours: string;
  call_paid_hours: string;
  base_pay: string;
  call_pay: string;
  office_seconds: string;
  approved_office_seconds: string;
  pending_office_seconds: string;
  call_seconds: string;
  calls_during_office_seconds: string;
  calls_outside_office_seconds: string;
  non_call_office_seconds: string;
  declared_call_seconds: string;
  answered_call_records: number;
  open_attendance: number;
  daily: {
    day: string;
    office_seconds: string;
    approved_office_seconds: string;
    pending_office_seconds: string;
    call_seconds: string;
    calls_during_office_seconds: string;
    calls_outside_office_seconds: string;
    non_call_office_seconds: string;
    approved_work_hours: string;
    pending_work_hours: string;
  }[];
}
export interface Analytics {
  metrics: {
    leads: number;
    prior_leads: number;
    assigned: number;
    unassigned: number;
    converted: number;
    conversion_rate: number;
    calls: number;
    observed_seconds: number;
    declared_seconds: number;
    talk_seconds: number;
    average_call_seconds: number;
    missed_rate: number;
    order_value: string;
    average_order_value: string;
    overdue: number;
    upcoming: number;
    stale: number;
  };
  statuses: Record<string, number>;
  sources: Record<string, number>;
  outcomes: Record<string, number>;
  hourly: { hour: number; calls: number }[];
  leaderboard: {
    user_id: string;
    name: string;
    calls: number;
    minutes: number;
    order_value: string;
  }[];
  cities: {
    city: string;
    leads: number;
    converted: number;
    order_value: string;
  }[];
  latest: Lead[];
  definitions: string;
  timezone: string;
  from_date: string;
  to_date: string;
}
export interface DashboardData extends Analytics {
  metrics: Analytics["metrics"] & {
    visible_leads: number;
    active_leads: number;
    actionable_overdue: number;
    needs_first_contact: number;
  };
  trend: { key: string; label: string; leads: number; calls: number }[];
  pipeline: { key: string; label: string; count: number }[];
  call_results: Record<string, number>;
  priority: { lead: Lead; reason: "overdue" | "due_today" | "first_contact" }[];
  priority_total: number;
  period_days: number;
}
export interface PublicConfig {
  brand: string;
  email: string;
  phone: string;
  business_text: string;
  contact_configured: boolean;
}
export interface Directory {
  id: string;
  name: string;
  role: string;
}
