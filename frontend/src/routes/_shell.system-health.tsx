import { createFileRoute } from "@tanstack/react-router";
import { MetricLineChart } from "@/components/charts/Charts";
import { PageHeader } from "@/components/common/PageHeader";
import { CardSkeleton, ErrorState } from "@/components/common/States";
import { useMockData } from "@/hooks/useMockData";
import { mockService } from "@/services/mockService";

export const Route = createFileRoute("/_shell/system-health")({
  head: () => ({
    meta: [
      { title: "System Health — DepSentry" },
      { name: "description", content: "Platform uptime, scan queue latency and service status." },
      { property: "og:title", content: "System Health — DepSentry" },
      { property: "og:description", content: "Platform uptime, latency and service status." },
    ],
  }),
  component: SystemHealthPage,
});

const statusTone: Record<string, string> = {
  operational: "bg-success/10 text-success",
  degraded: "bg-warning/15 text-warning",
  down: "bg-destructive/10 text-destructive",
};

function SystemHealthPage() {
  const { data, loading, error, reload } = useMockData(() => mockService.getSystemMetrics());

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <CardSkeleton />;

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="System health"
        description="Live telemetry for the scanning platform and advisory ingestion pipeline."
      />
      <div className="grid gap-4 md:grid-cols-2">
        {data.map((metric) => (
          <section key={metric.id} className="surface-card p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">{metric.label}</h2>
                <p className="mt-1 font-display text-2xl font-bold">
                  {metric.value}
                  <span className="ml-1 text-sm text-muted-foreground">{metric.unit}</span>
                </p>
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${statusTone[metric.status]}`}
              >
                {metric.status}
              </span>
            </div>
            <div className="mt-4">
              <MetricLineChart data={metric.history} />
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
