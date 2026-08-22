import { createFileRoute } from "@tanstack/react-router";
import { Download, FileBarChart } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { useMockData } from "@/hooks/useMockData";
import { mockService } from "@/services/mockService";
import { downloadFile, formatDate, toCsv } from "@/utils/format";

export const Route = createFileRoute("/_shell/reports")({
  head: () => ({
    meta: [
      { title: "Reports — DepSentry" },
      {
        name: "description",
        content: "Generate and download security, compliance and health reports.",
      },
      { property: "og:title", content: "Reports — DepSentry" },
      { property: "og:description", content: "Security, compliance and health report exports." },
    ],
  }),
  component: ReportsPage,
});

function ReportsPage() {
  const { data, loading, error, reload } = useMockData(() => mockService.getReports());
  const reports = data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title="Reports"
        description="Evidence packs for auditors, executives and engineering leads."
        actions={
          <Button
            variant="outline"
            onClick={() =>
              downloadFile(
                "depsentry-reports.csv",
                toCsv(
                  reports.map((report) => ({
                    name: report.name,
                    type: report.type,
                    repository: report.repository,
                    created: report.createdAt,
                  })),
                ),
                "text/csv",
              )
            }
          >
            <Download className="size-4" /> Export index
          </Button>
        }
      />

      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {loading ? <TableSkeleton /> : null}

      {!loading && !error ? (
        reports.length === 0 ? (
          <EmptyState icon={FileBarChart} title="No reports yet" />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {reports.map((report) => (
              <article key={report.id} className="surface-card flex flex-col p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-sm font-semibold">{report.name}</h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {report.type} · {report.repository}
                    </p>
                  </div>
                  <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium capitalize text-muted-foreground">
                    {report.status}
                  </span>
                </div>
                <p className="mt-4 text-xs text-muted-foreground">
                  {formatDate(report.createdAt)} · {report.format} · {report.size}
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-4"
                  disabled={report.status !== "ready"}
                  onClick={() =>
                    downloadFile(
                      `${report.name}.csv`,
                      toCsv([
                        {
                          report: report.name,
                          type: report.type,
                          repository: report.repository,
                          generated: report.createdAt,
                        },
                      ]),
                      "text/csv",
                    )
                  }
                >
                  <Download className="size-4" /> Download
                </Button>
              </article>
            ))}
          </div>
        )
      ) : null}
    </>
  );
}
