import { Link, createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  Activity,
  Boxes,
  Download,
  FileBarChart,
  FolderGit2,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Timer,
} from "lucide-react";
import { BreakdownPieChart, SeverityBarChart, TrendAreaChart } from "@/components/charts/Charts";
import { HealthRing } from "@/components/common/HealthRing";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { CardSkeleton, ErrorState, StatSkeletonGrid } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { useDashboardSummary } from "@/hooks/useDashboard";
import { downloadFile, formatCompact, timeAgo, toCsv } from "@/utils/format";

export const Route = createFileRoute("/_shell/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — DepSentry Dependency Health" },
      {
        name: "description",
        content:
          "Portfolio-wide dependency health score, vulnerability breakdown and scan activity.",
      },
      { property: "og:title", content: "Dashboard — DepSentry" },
      {
        property: "og:description",
        content: "Portfolio-wide dependency health score and vulnerability breakdown.",
      },
    ],
  }),
  component: DashboardPage,
});

const activityTone: Record<string, string> = {
  scan: "bg-primary/10 text-primary",
  repo: "bg-info/10 text-info",
  user: "bg-muted text-muted-foreground",
  vuln: "bg-destructive/10 text-destructive",
  report: "bg-success/10 text-success",
};

function DashboardPage() {
  const { data, isLoading: loading, error, refetch: reload } = useDashboardSummary();

  const errorMessage = error instanceof Error ? error.message : "Failed to load dashboard data.";

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title="Dependency health dashboard"
        description="A single view of open-source risk across every repository in your organisation."
        actions={
          <>
            <Button
              variant="outline"
              onClick={() =>
                data &&
                downloadFile(
                  "depsentry-summary.csv",
                  toCsv(data.severityBreakdown.map((p) => ({ severity: p.label, count: p.value }))),
                  "text/csv",
                )
              }
            >
              <Download className="size-4" /> Export
            </Button>
            <Button asChild>
              <Link to="/scanner">
                <ScanSearch className="size-4" /> New scan
              </Link>
            </Button>
          </>
        }
      />

      {error ? <ErrorState message={errorMessage} onRetry={() => reload()} /> : null}
      {loading || !data ? (
        <>
          <StatSkeletonGrid />
          <div className="grid gap-4 lg:grid-cols-3">
            <CardSkeleton className="lg:col-span-2" />
            <CardSkeleton />
          </div>
        </>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              index={0}
              label="Total dependencies"
              value={formatCompact(data.totalDependencies)}
              icon={Boxes}
              delta={4}
              hint="vs last month"
            />
            <StatCard
              index={1}
              label="Safe packages"
              value={formatCompact(data.safePackages)}
              icon={ShieldCheck}
              tone="success"
              delta={6}
              hint="patched this cycle"
            />
            <StatCard
              index={2}
              label="Vulnerable packages"
              value={data.vulnerablePackages}
              icon={ShieldAlert}
              tone="destructive"
              delta={-12}
              hint="open findings"
            />
            <StatCard
              index={3}
              label="Mean time to patch"
              value={data.meanTimeToPatch}
              icon={Timer}
              tone="warning"
              hint={`${data.scansThisWeek} scans this week`}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
              className="surface-card p-5 lg:col-span-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold">Health trend</h2>
                  <p className="text-sm text-muted-foreground">
                    Composite health score against open findings, last 12 weeks.
                  </p>
                </div>
              </div>
              <div className="mt-4">
                <TrendAreaChart data={data.trend} />
              </div>
            </motion.section>

            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.05 }}
              className="surface-card flex flex-col items-center justify-center gap-4 p-5"
            >
              <HealthRing score={data.healthScore} label="Portfolio health" />
              <p className="text-center text-sm text-muted-foreground">
                {data.outdatedPackages ?? 0} packages are behind their latest release.
              </p>
              <Button asChild variant="outline" size="sm">
                <Link to="/health-analysis">
                  <Activity className="size-4" /> Health analysis
                </Link>
              </Button>
            </motion.section>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <section className="surface-card p-5">
              <h2 className="text-base font-semibold">Severity distribution</h2>
              <div className="mt-4">
                <SeverityBarChart data={data.severityBreakdown} />
              </div>
            </section>
            <section className="surface-card p-5">
              <h2 className="text-base font-semibold">Ecosystem mix</h2>
              <div className="mt-4">
                <BreakdownPieChart data={data.ecosystemBreakdown} />
              </div>
            </section>
            <section className="surface-card p-5">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-base font-semibold">Recent activity</h2>
                <Link
                  to="/audit-logs"
                  className="text-xs font-semibold text-primary hover:underline"
                >
                  View all
                </Link>
              </div>
              <ul className="mt-4 space-y-3">
                {data.activity && data.activity.length > 0 ? (
                  data.activity.slice(0, 6).map((item) => (
                    <li key={item.id} className="flex gap-3">
                      <span
                        className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg ${activityTone[item.type]}`}
                      >
                        <FileBarChart className="size-4" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm leading-snug">{item.message}</p>
                        <p className="text-xs text-muted-foreground">
                          {item.actor} · {timeAgo(item.timestamp)}
                        </p>
                      </div>
                    </li>
                  ))
                ) : (
                  <li className="flex items-center justify-center py-6 text-sm text-muted-foreground">
                    No recent activity
                  </li>
                )}
              </ul>
            </section>
          </div>

          <section className="surface-card flex flex-wrap items-center justify-between gap-4 p-5">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
                <FolderGit2 className="size-5" />
              </span>
              <div>
                <h2 className="text-sm font-semibold">Monitor another repository</h2>
                <p className="text-sm text-muted-foreground">
                  Connect a repo and DepSentry scans every push automatically.
                </p>
              </div>
            </div>
            <Button asChild variant="outline">
              <Link to="/repositories/new">Add repository</Link>
            </Button>
          </section>
        </>
      )}
    </>
  );
}
