import { createFileRoute } from "@tanstack/react-router";
import { UserPlus } from "lucide-react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { SearchInput } from "@/components/common/SearchInput";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { API_ROUTES, apiClient } from "@/services/apiClient";
import { timeAgo } from "@/utils/format";
import { toast } from "sonner";

export const Route = createFileRoute("/_shell/users")({
  head: () => ({
    meta: [
      { title: "User Management — Dependency Hub" },
      {
        name: "description",
        content: "Manage teammates, roles and access to the Dependency Hub workspace.",
      },
      { property: "og:title", content: "User Management — Dependency Hub" },
      { property: "og:description", content: "Manage teammates, roles and workspace access." },
    ],
  }),
  component: UsersPage,
});

function UsersPage() {
  const {
    data,
    isLoading: loading,
    error,
    refetch: reload,
  } = useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const res = await apiClient.get(API_ROUTES.users);
      return res.data;
    },
  });
  const [query, setQuery] = useState("");

  const filtered = useMemo(
    () =>
      (data ?? []).filter((user) =>
        `${user.name} ${user.email} ${user.role} ${user.team}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [data, query],
  );

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="User management"
        description="Role-based access across security, engineering and compliance teams."
        actions={
          <Button onClick={() => toast.success("Invitation sent", { description: "Demo only." })}>
            <UserPlus className="size-4" /> Invite user
          </Button>
        }
      />

      <div className="surface-card p-4">
        <SearchInput value={query} onChange={setQuery} placeholder="Search people…" />
      </div>

      {error ? (
        <ErrorState
          message={error instanceof Error ? error.message : String(error)}
          onRetry={() => reload()}
        />
      ) : null}
      {loading ? <TableSkeleton /> : null}

      {!loading && !error ? (
        filtered.length === 0 ? (
          <EmptyState title="No teammates match that search" />
        ) : (
          <div className="surface-card overflow-x-auto p-1">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Team</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Last active</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((user) => (
                  <tr key={user.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span
                          className="grid size-9 shrink-0 place-items-center rounded-full text-xs font-bold text-navy-foreground"
                          style={{ backgroundColor: user.avatarColor }}
                        >
                          {user.name
                            .split(" ")
                            .map((part) => part[0])
                            .join("")}
                        </span>
                        <div className="min-w-0">
                          <p className="truncate font-medium">{user.name}</p>
                          <p className="truncate text-xs text-muted-foreground">{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">{user.role}</td>
                    <td className="px-4 py-3 text-muted-foreground">{user.team}</td>
                    <td className="px-4 py-3 capitalize">{user.status}</td>
                    <td className="px-4 py-3 text-muted-foreground">{timeAgo(user.lastActive)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : null}
    </>
  );
}
