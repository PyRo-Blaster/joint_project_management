/** Hand-maintained DTOs mirroring backend pydantic schemas / OpenAPI. */

export type Org = "gensci" | "yarrow";
export type OwnerOrg = "gensci" | "yarrow" | "joint";
export type Role = "admin" | "member";
export type Kind = "action" | "note";
export type Status = "open" | "in_progress" | "blocked" | "on_hold" | "completed" | "cancelled";
export type Priority = "p1" | "p2" | "p3";

export interface Meta {
  total: number;
  page: number;
  limit: number;
}

export interface ErrorBody {
  code: string;
  message: string;
  fields?: Record<string, string> | null;
  request_id?: string | null;
}

export interface Envelope<T> {
  success: boolean;
  data: T | null;
  error: ErrorBody | null;
  meta: Meta | null;
}

export interface UserOut {
  id: number;
  email: string;
  name: string;
  org: string;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface ItemOut {
  id: number;
  program_id: number;
  entry_no: number;
  kind: string;
  title: string;
  details: string;
  group: string;
  category: string | null;
  owner_org: string;
  assignee_id: number | null;
  status: string | null;
  priority: string | null;
  raised_on: string;
  source: string | null;
  due_on: string | null;
  completed_on: string | null;
  notes_risks: string;
  file_path: string;
  created_by: number;
  created_at: string;
  updated_by: number;
  updated_at: string;
  deleted_at: string | null;
  last_update_on: string | null;
}

export interface ItemCreate {
  kind?: Kind;
  title: string;
  details?: string;
  group: string;
  category?: string | null;
  owner_org: OwnerOrg;
  assignee_id?: number | null;
  status?: Status | null;
  priority?: Priority | null;
  raised_on?: string | null;
  source?: string | null;
  due_on?: string | null;
  notes_risks?: string;
  file_path?: string;
}

export interface ItemPatch {
  title?: string | null;
  details?: string | null;
  group?: string | null;
  category?: string | null;
  owner_org?: OwnerOrg | null;
  assignee_id?: number | null;
  status?: Status | null;
  priority?: Priority | null;
  raised_on?: string | null;
  source?: string | null;
  due_on?: string | null;
  notes_risks?: string | null;
  file_path?: string | null;
}

export interface UpdateOut {
  id: number;
  item_id: number;
  author_id: number;
  author_name: string;
  author_org: string;
  body: string;
  occurred_on: string;
  created_at: string;
  edited_at: string | null;
}

export interface UpdateCreate {
  body: string;
  occurred_on?: string | null;
}

export interface AuditEventOut {
  id: number;
  program_id: number | null;
  entity_type: string;
  entity_id: number;
  action: string;
  actor_id: number;
  actor_name: string;
  actor_org: string;
  occurred_at: string;
  changes: Record<string, unknown>;
  summary: string;
}

export interface VocabTermOut {
  id: number;
  program_id: number;
  field: string;
  value: string;
  is_active: boolean;
  sort_order: number;
}

export interface ItemListParams {
  status?: string[];
  priority?: string[];
  group?: string[];
  category?: string[];
  owner_org?: string[];
  kind?: string;
  assignee_id?: number;
  due_before?: string;
  due_after?: string;
  q?: string;
  sort?: string;
  direction?: "asc" | "desc";
  page?: number;
  limit?: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AcceptInviteRequest {
  token: string;
  name: string;
  password: string;
}
