import { CSRF_HEADER, CSRF_VALUE, SESSION_EXPIRED_EVENT } from "@/lib/constants";
import type { Envelope, Meta } from "@/lib/api/types";

export class ApiError extends Error {
  code: string;
  fields: Record<string, string> | null;
  requestId: string | null;
  status: number;

  constructor(
    message: string,
    opts: {
      code: string;
      fields?: Record<string, string> | null;
      requestId?: string | null;
      status: number;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.code = opts.code;
    this.fields = opts.fields ?? null;
    this.requestId = opts.requestId ?? null;
    this.status = opts.status;
  }
}

export type ApiResult<T> = { data: T; meta: Meta | null };

type RequestOptions = {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null | Array<string | number>>;
  signal?: AbortSignal;
};

function buildQuery(
  query?: RequestOptions["query"],
): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, String(item));
    } else {
      params.append(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (method !== "GET" && method !== "HEAD") {
    headers[CSRF_HEADER] = CSRF_VALUE;
  }
  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(`/api${path}${buildQuery(options.query)}`, {
    method,
    headers,
    body,
    credentials: "include",
    signal: options.signal,
  });

  let envelope: Envelope<T> | null = null;
  const text = await response.text();
  if (text) {
    try {
      envelope = JSON.parse(text) as Envelope<T>;
    } catch {
      envelope = null;
    }
  }

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
  }

  if (!envelope) {
    throw new ApiError(text || response.statusText || "Request failed", {
      code: "http_error",
      status: response.status,
    });
  }

  if (!response.ok || !envelope.success) {
    const err = envelope.error;
    throw new ApiError(err?.message ?? "Request failed", {
      code: err?.code ?? "http_error",
      fields: err?.fields ?? null,
      requestId: err?.request_id ?? null,
      status: response.status,
    });
  }

  return { data: envelope.data as T, meta: envelope.meta };
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"], signal?: AbortSignal) =>
    request<T>(path, { method: "GET", query, signal }),
  post: <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
    request<T>(path, { method: "POST", body, query }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
