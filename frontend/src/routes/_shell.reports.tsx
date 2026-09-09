import { createFileRoute } from "@tanstack/react-router";
import { AlertCircle, Download, FileBarChart, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Pill } from "@/components/common/Badges";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProjects } from "@/hooks/useProjects";
import {
  downloadReport,
  useDeleteReport,
  useGenerateReport,
  useProjectReports,
  useProjectScans,
  useRetryReport,
  type Report,
  type ReportFormat,
  type ReportStatus,
  type ReportType,
} from "@/hooks/useReports";
import { useActiveProject } from "@/hooks/useActiveProject";
import { formatDateTime } from "@/utils/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_shell/reports")({
  head: () => ({
    meta: [
      { title: "Reports — Dependency Hub" },
      {
        name: "description",
        content:
          "Generate evidence packs from completed dependency scans — security, compliance, executive and package reports in multiple formats.",
      },
      { property: "og:title", content: "Reports — Dependency Hub" },
      {
        property: "og:description",
        content: "Security, compliance and health report exports.",
      },
    ],
  }),
  component: ReportsPage,
});

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<ReportStatus, string> = {
  QUEUED: "bg-info/10 text-info border-info/30",
  GENERATING: "bg-primary/10 text-primary border-primary/30",
  COMPLETED: "bg-success/10 text-success border-success/30",
  FAILED: "bg-destructive/10 text-destructive border-destructive/30",
  EXPIRED: "bg-muted text-muted-foreground border-border",
  DELETED: "bg-muted text-muted-foreground border-border",
};

const STATUS_LABEL: Record<ReportStatus, string> = {
  QUEUED: "Queued",
  GENERATING: "Generating…",
  COMPLETED: "Completed",
  FAILED: "Failed",
  EXPIRED: "Expired",
  DELETED: "Deleted",
};

function ReportStatusBadge({ status }: { status: ReportStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        STATUS_STYLES[status],
      )}
    >
      {status === "GENERATING" ? (
        <Loader2 className="size-3 animate-spin" />
      ) : (
        <span className="size-1.5 rounded-full bg-current" />
      )}
      {STATUS_LABEL[status]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Report type / format helpers
// ---------------------------------------------------------------------------

const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: "SECURITY_REPORT", label: "Security Report" },
  { value: "PACKAGE_REPORT", label: "Package Report" },
  { value: "EXECUTIVE_REPORT", label: "Executive Report" },
  { value: "COMPLIANCE_REPORT", label: "Compliance Report" },
];

const REPORT_FORMATS: { value: ReportFormat; label: string }[] = [
  { value: "JSON", label: "JSON" },
  { value: "HTML", label: "HTML" },
  { value: "PDF", label: "PDF" },
  { value: "CSV", label: "CSV" },
  { value: "SARIF", label: "SARIF" },
];

function reportTypeLabel(type: ReportType): string {
  return REPORT_TYPES.find((t) => t.value === type)?.label ?? type;
}

// ---------------------------------------------------------------------------
// Report history row actions
// ---------------------------------------------------------------------------

function ReportRowActions({ report }: { report: Report }) {
  const deleteMutation = useDeleteReport(report.project_id);
  const retryMutation = useRetryReport(report.project_id);
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadReport(report.project_id, report.id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Download failed.";
      toast.error("Download error", { description: msg });
    } finally {
      setDownloading(false);
    }
  };

  const handleRetry = async () => {
    try {
      await retryMutation.mutateAsync(report.id);
      toast.success("Report re-queued", {
        description: "Polling will resume automatically.",
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Retry failed.";
      toast.error("Retry failed", { description: msg });
    }
  };

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(report.id);
      toast.success("Report deleted");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Delete failed.";
      toast.error("Delete failed", { description: msg });
    }
  };

  return (
    <div className="flex items-center justify-end gap-2">
      {report.status === "COMPLETED" && (
        <Button
          size="sm"
          variant="outline"
          onClick={handleDownload}
          disabled={downloading}
          aria-label="Download report"
        >
          {downloading ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Download className="size-3.5" />
          )}
          Download
        </Button>
      )}

      {report.status === "EXPIRED" && (
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <AlertCircle className="size-3.5" />
          Artifact expired
        </span>
      )}

      {report.status === "FAILED" && (
        <Button
          size="sm"
          variant="outline"
          onClick={handleRetry}
          disabled={retryMutation.isPending}
          aria-label="Retry report"
        >
          {retryMutation.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <RefreshCw className="size-3.5" />
          )}
          Retry
        </Button>
      )}

      <Button
        size="sm"
        variant="ghost"
        onClick={handleDelete}
        disabled={deleteMutation.isPending}
        className="text-muted-foreground hover:text-destructive"
        aria-label="Delete report"
      >
        {deleteMutation.isPending ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Trash2 className="size-3.5" />
        )}
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function ReportsPage() {
  const { activeProjectId, setActiveProject, isLoading: isProjectLoading, activeProject } = useActiveProject();
  const [selectedScanId, setSelectedScanId] = useState<string>("");
  const [reportType, setReportType] = useState<ReportType>("SECURITY_REPORT");
  const [reportFormat, setReportFormat] = useState<ReportFormat>("PDF");

  const projectsQuery = useProjects();
  const scansQuery = useProjectScans(activeProjectId || null);
  const reportsQuery = useProjectReports(activeProjectId || null);

  const generateMutation = useGenerateReport(activeProjectId || "");

  const projects = projectsQuery.data ?? [];
  const allScans = scansQuery.data ?? [];
  const completedScans = allScans.filter((s) => s.status === "COMPLETED");
  const reports = reportsQuery.data ?? [];

  const canGenerate = !!activeProjectId && !!selectedScanId && !generateMutation.isPending;

  const handleProjectChange = (id: string) => {
    setActiveProject(id);
    setSelectedScanId(""); // reset scan when project changes
  };

  const handleGenerate = async () => {
    if (!canGenerate) return;

    try {
      await generateMutation.mutateAsync({
        scan_id: selectedScanId,
        report_type: reportType,
        format: reportFormat,
      });
      toast.success("Report queued", {
        description: "It will appear in the history below once generated.",
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to generate report.";
      toast.error("Generation failed", { description: msg });
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title="Reports"
        description="Generate evidence packs from completed dependency scans — share with auditors, executives, and engineering teams."
      />

      {/* ------------------------------------------------------------------ */}
      {/* Generate Report card                                                */}
      {/* ------------------------------------------------------------------ */}
      <section className="surface-card p-5">
        <h2 className="text-base font-semibold">Generate report</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Select a repository and a completed scan, choose a report type and format, then generate.
        </p>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Repository */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Repository
            </label>
            {projectsQuery.isLoading ? (
              <div className="shimmer h-9 rounded-md bg-muted" />
            ) : projects.length === 0 ? (
              <p className="text-sm text-muted-foreground">No repositories found.</p>
            ) : (
              <Select value={activeProjectId || ""} onValueChange={handleProjectChange}>
                <SelectTrigger id="report-repository-select">
                  <SelectValue placeholder="Select repository…" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((repo) => (
                    <SelectItem key={repo.id} value={repo.id}>
                      {repo.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Scan */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Scan
            </label>
            {scansQuery.isLoading && activeProjectId ? (
              <div className="shimmer h-9 rounded-md bg-muted" />
            ) : (
              <Select
                value={selectedScanId}
                onValueChange={setSelectedScanId}
                disabled={!activeProjectId || completedScans.length === 0}
              >
                <SelectTrigger id="report-scan-select">
                  <SelectValue
                    placeholder={
                      !activeProjectId
                        ? "Select repository first"
                        : completedScans.length === 0
                          ? "No completed scans"
                          : "Select scan…"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {completedScans.map((scan) => (
                    <SelectItem key={scan.id} value={scan.id}>
                      <span className="flex flex-col">
                        <span>{formatDateTime(scan.completed_at ?? scan.created_at)}</span>
                        {(scan.total_dependencies !== null ||
                          scan.vulnerable_dependencies !== null) && (
                          <span className="text-xs text-muted-foreground">
                            {scan.total_dependencies ?? "?"} deps ·{" "}
                            {scan.vulnerable_dependencies ?? "?"} vulnerable
                          </span>
                        )}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Report type */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Report type
            </label>
            <Select value={reportType} onValueChange={(v) => setReportType(v as ReportType)}>
              <SelectTrigger id="report-type-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {REPORT_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Format */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Format
            </label>
            <Select value={reportFormat} onValueChange={(v) => setReportFormat(v as ReportFormat)}>
              <SelectTrigger id="report-format-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {REPORT_FORMATS.map((f) => (
                  <SelectItem key={f.value} value={f.value}>
                    {f.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <Button id="generate-report-button" onClick={handleGenerate} disabled={!canGenerate}>
            {generateMutation.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <FileBarChart className="size-4" />
            )}
            {generateMutation.isPending ? "Queuing…" : "Generate report"}
          </Button>
          {!activeProjectId && (
            <p className="text-xs text-muted-foreground">Select a repository to continue.</p>
          )}
          {activeProjectId &&
            !selectedScanId &&
            completedScans.length === 0 &&
            !scansQuery.isLoading && (
              <p className="text-xs text-muted-foreground">
                No completed scans available — run a scan first.
              </p>
            )}
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Report history                                                       */}
      {/* ------------------------------------------------------------------ */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">
            Report history
            {activeProjectId
              ? ` · ${projects.find((p) => p.id === activeProjectId)?.name ?? ""}`
              : ""}
          </h2>
          {reportsQuery.isFetching && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> Refreshing…
            </span>
          )}
        </div>

        {!activeProjectId ? (
          <EmptyState
            icon={FileBarChart}
            title="Select a repository"
            description="Choose a repository above to view its generated reports."
          />
        ) : reportsQuery.isError ? (
          <ErrorState
            message={
              reportsQuery.error instanceof Error
                ? reportsQuery.error.message
                : "Failed to load reports."
            }
            onRetry={() => reportsQuery.refetch()}
          />
        ) : reportsQuery.isLoading ? (
          <TableSkeleton rows={4} />
        ) : reports.length === 0 ? (
          <EmptyState
            icon={FileBarChart}
            title="No reports yet"
            description="Generate your first report using the form above."
          />
        ) : (
          <div className="surface-card overflow-x-auto p-1">
            <table className="w-full min-w-[680px] text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Report type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {reports.map((report) => (
                  <tr key={report.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium">
                      <div className="flex items-center gap-2">
                        {reportTypeLabel(report.report_type)}
                        <Pill tone="muted">{report.report_type.replace(/_/g, " ")}</Pill>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <ReportStatusBadge status={report.status} />
                    </td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums">
                      {formatDateTime(report.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <ReportRowActions report={report} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
