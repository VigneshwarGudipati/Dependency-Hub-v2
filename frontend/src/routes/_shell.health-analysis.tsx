import { createFileRoute, Link } from "@tanstack/react-router";
import { FolderGit2 } from "lucide-react";
import { BreakdownPieChart, SeverityBarChart, TrendAreaChart } from "@/components/charts/Charts";
import { PageHeader } from "@/components/common/PageHeader";
import { CardSkeleton, ErrorState, EmptyState } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { useDashboardSummary } from "@/hooks/useDashboard";
import { useActiveProject } from "@/hooks/useActiveProject";

export const Route = createFileRoute("/_shell/health-analysis")({
  head: () => ({
    meta: [
      { title: "Health Analysis — Dependency Hub" },
      {
        name: "description",
        content: "Deep dive into your dependency risk with interactive severity and timeline charts.",
      },
    ],
  }),
  component: HealthAnalysisPage,
});

function HealthAnalysisPage() {
  const { activeProjectId, activeProject, isLoading: isProjectLoading } = useActiveProject();
  const { data, isLoading: loading, error, refetch: reload } = useDashboardSummary(activeProjectId);

  const errorMessage = error instanceof Error ? error.message : "Failed to load health analysis.";

  if (!isProjectLoading && !activeProject) {
    return (
      <EmptyState
        icon={FolderGit2}
        title="No active project"
        description="Select or create a project to view its health analysis."
        action={
          <Button asChild>
            <Link to="/repositories/new">Add repository</Link>
          </Button>
        }
      />
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Analysis"
        title="Health analysis"
        description="Deep dive into vulnerability severity distribution and patching trends over time."
      />

      {error ? <ErrorState message={errorMessage} onRetry={() => reload()} /> : null}

      {loading || isProjectLoading || !data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <CardSkeleton className="h-[400px]" />
          <CardSkeleton className="h-[400px]" />
          <CardSkeleton className="h-[400px] lg:col-span-2" />
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="surface-card flex flex-col p-5">
            <h2 className="mb-4 text-base font-semibold">Severity breakdown</h2>
            <div className="flex-1">
              <SeverityBarChart data={data.severityBreakdown} />
            </div>
          </section>

          <section className="surface-card flex flex-col p-5">
            <h2 className="mb-4 text-base font-semibold">Vulnerability distribution</h2>
            <div className="flex-1">
              <BreakdownPieChart data={data.severityBreakdown} />
            </div>
          </section>

          <section className="surface-card flex flex-col p-5 lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold">Risk trend (90 days)</h2>
              <span className="text-xs text-muted-foreground">Mock data</span>
            </div>
            <div className="h-[350px]">
              <TrendAreaChart data={data.historicalTrend} />
            </div>
          </section>
        </div>
      )}
    </>
  );
}
