import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import { api, ApiError } from "@/lib/api/client";
import type {
  AcceptInviteRequest,
  AuditEventOut,
  ItemListParams,
  ItemOut,
  ItemPatch,
  LoginRequest,
  UpdateCreate,
  UpdateOut,
  UserOut,
  VocabTermOut,
} from "@/lib/api/types";
import { queryKeys } from "@/lib/query-keys";

export function applyApiFieldErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
) {
  if (!(error instanceof ApiError) || !error.fields) return false;
  for (const [field, message] of Object.entries(error.fields)) {
    setError(field as Path<T>, { type: "server", message });
  }
  return true;
}

export function toastApiError(error: unknown, fallback = "Something went wrong") {
  if (error instanceof ApiError) {
    const rid = error.requestId ? ` (${error.requestId})` : "";
    toast.error(`${error.message}${rid}`);
    return;
  }
  toast.error(fallback);
}

export function useMeQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: async ({ signal }) => (await api.get<UserOut>("/auth/me", undefined, signal)).data,
    enabled,
    retry: false,
  });
}

export function useLoginMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: LoginRequest) => (await api.post<UserOut>("/auth/login", body)).data,
    onSuccess: (user) => {
      qc.setQueryData(queryKeys.me, user);
      toast.success("Signed in");
    },
  });
}

export function useLogoutMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.post<null>("/auth/logout");
    },
    onSuccess: () => {
      qc.setQueryData(queryKeys.me, null);
      qc.clear();
      toast.success("Signed out");
    },
  });
}

export function useAcceptInviteMutation() {
  return useMutation({
    mutationFn: async (body: AcceptInviteRequest) =>
      (await api.post<UserOut>("/auth/accept-invite", body)).data,
    onSuccess: () => toast.success("Account created — please sign in"),
  });
}

export function useItemsQuery(params: ItemListParams) {
  return useQuery({
    queryKey: queryKeys.items(params),
    queryFn: async ({ signal }) => {
      const result = await api.get<ItemOut[]>("/items", params as never, signal);
      return result;
    },
  });
}

export function useItemQuery(id: number | null) {
  return useQuery({
    queryKey: queryKeys.item(id ?? 0),
    queryFn: async ({ signal }) => (await api.get<ItemOut>(`/items/${id}`, undefined, signal)).data,
    enabled: id != null && id > 0,
  });
}

export function usePatchItemMutation(itemId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ItemPatch) =>
      (await api.patch<ItemOut>(`/items/${itemId}`, body)).data,
    onSuccess: (item) => {
      qc.setQueryData(queryKeys.item(itemId), item);
      void qc.invalidateQueries({ queryKey: ["items"] });
      toast.success("Item saved");
    },
  });
}

export function useItemUpdatesQuery(itemId: number | null) {
  return useQuery({
    queryKey: queryKeys.itemUpdates(itemId ?? 0),
    queryFn: async ({ signal }) =>
      (await api.get<UpdateOut[]>(`/items/${itemId}/updates`, undefined, signal)).data,
    enabled: itemId != null && itemId > 0,
  });
}

export function useCreateUpdateMutation(itemId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: UpdateCreate) =>
      (await api.post<UpdateOut>(`/items/${itemId}/updates`, body)).data,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.itemUpdates(itemId) });
      void qc.invalidateQueries({ queryKey: queryKeys.item(itemId) });
      void qc.invalidateQueries({ queryKey: ["items"] });
      void qc.invalidateQueries({ queryKey: queryKeys.itemHistory(itemId) });
      toast.success("Update posted");
    },
  });
}

export function useItemHistoryQuery(itemId: number | null) {
  return useQuery({
    queryKey: queryKeys.itemHistory(itemId ?? 0),
    queryFn: async ({ signal }) =>
      (await api.get<AuditEventOut[]>(`/items/${itemId}/history`, undefined, signal)).data,
    enabled: itemId != null && itemId > 0,
  });
}

export function useVocabQuery() {
  return useQuery({
    queryKey: queryKeys.vocab(),
    queryFn: async ({ signal }) =>
      (await api.get<VocabTermOut[]>("/vocab", undefined, signal)).data,
  });
}

export function useUsersQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.users,
    queryFn: async ({ signal }) => {
      try {
        return (await api.get<UserOut[]>("/users", undefined, signal)).data;
      } catch (error) {
        if (error instanceof ApiError && (error.status === 403 || error.status === 401)) {
          return [] as UserOut[];
        }
        throw error;
      }
    },
    enabled,
    retry: false,
  });
}
