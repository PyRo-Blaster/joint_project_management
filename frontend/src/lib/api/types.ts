import type { components } from "./schema";

type S = components["schemas"];

// DTOs — generated, always in sync with the backend pydantic models.
export type ItemOut = S["ItemOut"];
export type ItemBrief = S["ItemBrief"];
export type ItemCreate = S["ItemCreate"];
export type ItemPatch = S["ItemPatch"];
export type UserOut = S["UserOut"];
export type UserBrief = S["UserBrief"];
export type UpdateOut = S["UpdateOut"];
export type UpdateCreate = S["UpdateCreate"];
export type UpdatePatch = S["UpdatePatch"];
export type AuditEventOut = S["AuditEventOut"];
export type DashboardSummary = S["DashboardSummary"];
export type VocabTermOut = S["VocabTermOut"];
export type ImportPreviewOut = S["ImportPreviewOut"];
export type ImportCommitOut = S["ImportCommitOut"];
export type InvitationOut = S["InvitationOut"];
export type InvitationCreatedOut = S["InvitationCreatedOut"];
export type ResetLinkOut = S["ResetLinkOut"];

// Envelope — hand-written; the backend wraps every response in this shape.
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
