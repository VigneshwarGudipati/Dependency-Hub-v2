import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { SearchInput } from "@/components/common/SearchInput";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/common/States";
import { useMockData } from "@/hooks/useMockData";
import { mockService } from "@/services/mockService";
import { formatDateTime } from "@/utils/format";

export const Route = createFileRoute("/_shell/audit-logs")({
  head: () => ({
    meta: [
      { title: "Audit Logs — DepSentry" },
      {
        name: "description",
        content: "Immutable trail of logins, scans and configuration changes.",
      },
      { property: "og:title", content: "Audit Logs — DepSentry" },
      { property: "og:description", content: "Immutable trail of workspace activity." },
    ],
  }),
  component: AuditLogsPage,
});

function AuditLogsPage() {
  const { data, loading, error, reload } = useMockData(() => mockService.getAuditLogs());
  const [query, setQuery] = useState("");

  const filtered = useMemo(
    () =>
      (data ?? []).filter((log) =>
        `${log.action} ${log.actor} ${log.target} ${log.ip}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [data, query],
  );

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title="Audit logs"
        description="Every privileged action, retained for 400 days."
      />
      <div className="surface-card p-4">
        <SearchInput value={query} onChange={setQuery} placeholder="Search audit events…" />
      </div>

      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {loading ? <TableSkeleton /> : null}

      {!loading && !error ? (
        filtered.length === 0 ? (
          <EmptyState title="No audit events match that search" />
        ) : (
          <div className="surface-card overflow-x-auto p-1">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Target</th>
                  <th className="px-4 py-3">IP</th>
                  <th className="px-4 py-3">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((log) => (
                  <tr key={log.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDateTime(log.timestamp)}
                    </td>
                    <td className="px-4 py-3 font-medium">{log.action}</td>
                    <td className="px-4 py-3">{log.actor}</td>
                    <td className="px-4 py-3 text-muted-foreground">{log.target}</td>
                    <td className="px-4 py-3 font-mono text-xs">{log.ip}</td>
                    <td
                      className={`px-4 py-3 capitalize ${log.result === "success" ? "text-success" : "text-destructive"}`}
                    >
                      {log.result}
                    </td>
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
