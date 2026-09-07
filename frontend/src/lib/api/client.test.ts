import { ApiError, apiFetch, apiList, AUTH_EXPIRED_EVENT } from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => vi.restoreAllMocks());

test("apiFetch unwraps data and sends the CSRF header on mutations", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(jsonResponse({ success: true, data: { id: 1 }, error: null, meta: null }));

  const data = await apiFetch<{ id: number }>("/items/1", {
    method: "PATCH",
    body: { title: "x" },
  });
  expect(data).toEqual({ id: 1 });

  const [, init] = fetchMock.mock.calls[0];
  const headers = new Headers(init?.headers);
  expect(headers.get("X-Requested-With")).toBe("fetch");
  expect(headers.get("Content-Type")).toBe("application/json");
  expect(init?.body).toBe(JSON.stringify({ title: "x" }));
});

test("apiFetch throws a typed ApiError on success:false", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse(
      {
        success: false,
        data: null,
        error: { code: "validation_error", message: "Invalid", fields: { title: "required" } },
        meta: null,
      },
      422,
    ),
  );
  await expect(apiFetch("/items", { method: "POST", body: {} })).rejects.toMatchObject({
    code: "validation_error",
    status: 422,
    fields: { title: "required" },
  });
});

test("a 401 dispatches the auth-expired event and throws", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse(
      { success: false, data: null, error: { code: "unauthenticated", message: "x" }, meta: null },
      401,
    ),
  );
  const onExpire = vi.fn();
  window.addEventListener(AUTH_EXPIRED_EVENT, onExpire);
  await expect(apiFetch("/auth/me")).rejects.toBeInstanceOf(ApiError);
  expect(onExpire).toHaveBeenCalledOnce();
  window.removeEventListener(AUTH_EXPIRED_EVENT, onExpire);
});

test("apiList returns data and meta together", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse({
      success: true,
      data: [{ id: 1 }],
      error: null,
      meta: { total: 1, page: 1, limit: 50 },
    }),
  );
  const { data, meta } = await apiList<{ id: number }>("/items");
  expect(data).toHaveLength(1);
  expect(meta.total).toBe(1);
});
