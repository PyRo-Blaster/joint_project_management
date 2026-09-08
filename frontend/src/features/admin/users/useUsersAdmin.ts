import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { InvitationCreatedOut, InvitationOut, ResetLinkOut, UserOut } from "@/lib/api/types";
import type { Org, Role } from "@/lib/constants";
import { qk } from "@/lib/query";

export function useUsersList() {
  return useQuery({ queryKey: qk.users.admin(), queryFn: () => apiFetch<UserOut[]>("/users") });
}

export function useInvitations() {
  return useQuery({
    queryKey: qk.invitations.list(),
    queryFn: () => apiFetch<InvitationOut[]>("/invitations"),
  });
}

export function usePatchUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<{ org: Org; role: Role; is_active: boolean; name: string }>;
    }) => apiFetch<UserOut>(`/users/${id}`, { method: "PATCH", body: patch }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.users.admin() }),
  });
}

export function useCreateInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; org: Org; role: Role }) =>
      apiFetch<InvitationCreatedOut>("/invitations", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.invitations.list() }),
  });
}

export function useRevokeInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<InvitationOut>(`/invitations/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.invitations.list() }),
  });
}

export function useResetLink() {
  return useMutation({
    mutationFn: (userId: number) =>
      apiFetch<ResetLinkOut>(`/users/${userId}/reset-link`, { method: "POST" }),
  });
}
