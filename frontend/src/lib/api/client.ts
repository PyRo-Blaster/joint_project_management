import type { Envelope, ErrorBody, Meta } from "./types";

export const AUTH_EXPIRED_EVENT = "cmc:auth-expired";
const BASE = "/api";

/** Typed error carrying the backend envelope's error body plus the HTTP status. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly fields?: Record<string, string> | null;
  readonly requestId?: string | null;

  constructor(status: number, error: ErrorBody) {
    super(error.message);
    this.name = "ApiError";
    this.code = error.code;
    this.status = status;
    this.fields = error.fields;
    this.requestId = error.request_id;
  }
}

export interface ApiOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE" | "PUT";
  body?: unknown;
  /** Query params; arrays become repeated keys (matches FastAPI list query params). */
  params?: Record<string, string | number | boolean | Array<string | number> | null | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, params?: ApiOptions["params"]): string {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === null || value === undefined || value === "") continue;
      if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, String(v)));
      else url.searchParams.set(key, String(value));
    }
  }
  return url.pathname + url.search;
}

async function request<T>(path: string, options: ApiOptions): Promise<Envelope<T>> {
  const { method = "GET", body, params, signal } = options;
  const headers: Record<string, string> = { "X-Requested-With": "fetch" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(buildUrl(path, params), {
    method,
    headers,
    credentials: "same-origin",
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
  }

  let envelope: Envelope<T>;
  try {
    envelope = (await response.json()) as Envelope<T>;
  } catch {
    throw new ApiError(response.status, {
      code: "network_error",
      message: "The server returned an unreadable response.",
    });
  }

  if (!response.ok || !envelope.success) {
    throw new ApiError(
      response.status,
      envelope.error ?? { code: "error", message: "Request failed" },
    );
  }
  return envelope;
}

/** Unwraps `data`. Use for single-object and action endpoints. */
export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const envelope = await request<T>(path, options);
  return envelope.data as T;
}

/** Returns `{ data, meta }` for list endpoints that page. */
export async function apiList<T>(
  path: string,
  options: ApiOptions = {},
): Promise<{ data: T[]; meta: Meta }> {
  const envelope = await request<T[]>(path, options);
  return {
    data: (envelope.data ?? []) as T[],
    meta: envelope.meta ?? { total: 0, page: 1, limit: 0 },
  };
}
