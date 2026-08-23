import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/States";

export const Route = createFileRoute("/_shell/audit-logs")({
  head: () => ({
    meta: [
      { title: "Audit Logs — Dependency Hub" },
      {
        name: "description",
        content: "Immutable trail of logins, scans and configuration changes.",
      },
      { property: "og:title", content: "Audit Logs — Dependency Hub" },
      { property: "og:description", content: "Immutable trail of workspace activity." },
    ],
  }),
  component: AuditLogsPage,
});

function AuditLogsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Security"
        title="Audit logs"
        description="Every privileged action, retained for 400 days."
      />
      <div className="pt-8">
        <EmptyState
          title="Audit logs are planned for a future release."
          description="In a future update, this page will display an immutable trail of workspace activity backed by the backend."
        />
      </div>
    </>
  );
}
