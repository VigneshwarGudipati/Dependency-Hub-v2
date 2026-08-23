import { createFileRoute } from "@tanstack/react-router";
import { Activity, Boxes, ShieldCheck, Timer } from "lucide-react";
import { BreakdownPieChart, TrendAreaChart } from "@/components/charts/Charts";
import { HealthRing } from "@/components/common/HealthRing";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { CardSkeleton, ErrorState } from "@/components/common/States";
import { useDashboardSummary } from "@/hooks/useDashboard";
import { formatCompact } from "@/utils/format";

export const Route = createFileRoute("/_shell/health-analysis")({
  head: () => ({
    meta: [
      { title: "Dependency Health Analysis — Dependency Hub" },
      {
        name: "description",
        content:
          "Composite health scoring, freshness and maintenance signals across the portfolio.",
      },
      { property: "og:title", content: "Dependency Health Analysis — Dependency Hub" },
      { property: "og:description", content: "Composite health scoring across your portfolio." },
    ],
  }),
  component: HealthAnalysisPage,
});

function HealthAnalysisPage() {
  const { data, isLoading: loading, error, refetch: reload } = useDashboardSummary();

  const errorMessage = error instanceof Error ? error.message : "Failed to load health analysis.";

  if (error) return <ErrorState message={errorMessage} onRetry={() => reload()} />;
  if (loading || !data) return <CardSkeleton />;

  return (
    <>
      <PageHeader
        eyebrow="Analysis"
        title="Dependency health analysis"
        description="How freshness, maintenance and security combine into your composite score."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          index={0}
          label="Composite score"
          value={data.healthScore !== null ? data.healthScore : "N/A"}
          icon={Activity}
        />
        <StatCard
          index={1}
          label="Tracked packages"
          value={formatCompact(data.totalDependencies)}
          icon={Boxes}
        />
        <StatCard
          index={2}
          label="Outdated"
          value={data.outdatedPackages ?? 0}
          icon={Timer}
          tone="warning"
        />
        <StatCard
          index={3}
          label="Safe"
          value={formatCompact(data.safePackages)}
          icon={ShieldCheck}
          tone="success"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="surface-card p-5 lg:col-span-2">
          <h2 className="text-base font-semibold">Score trajectory</h2>
          <div className="mt-4">
            <TrendAreaChart data={data.trend} height={300} />
          </div>
        </section>
        <section className="surface-card flex items-center justify-center p-5">
          <HealthRing score={data.healthScore} label="Current score" />
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="surface-card p-5">
          <h2 className="text-base font-semibold">Ecosystem distribution</h2>
          <div className="mt-4">
            <BreakdownPieChart data={data.ecosystemBreakdown} />
          </div>
        </section>
        <section className="surface-card p-5">
          <h2 className="text-base font-semibold">Scoring model</h2>
          <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
            {[
              ["Security (45%)", "Open advisories weighted by CVSS and exploit maturity."],
              ["Freshness (25%)", "Version drift against the latest published release."],
              ["Maintenance (20%)", "Release cadence, maintainer count and issue response."],
              ["Licensing (10%)", "Compatibility of licenses with your distribution model."],
            ].map(([title, body]) => (
              <li key={title} className="rounded-xl border border-border p-4">
                <p className="font-semibold text-foreground">{title}</p>
                <p className="mt-1">{body}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
