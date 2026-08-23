import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/common/PageHeader";
import { CardSkeleton, ErrorState } from "@/components/common/States";
import { useQuery } from "@tanstack/react-query";
import { BASE_URL } from "@/services/apiClient";
import { Activity, Database, Server } from "lucide-react";

export const Route = createFileRoute("/_shell/system-health")({
  head: () => ({
    meta: [
      { title: "System Health — Dependency Hub" },
      { name: "description", content: "Platform uptime, scan queue latency and service status." },
      { property: "og:title", content: "System Health — Dependency Hub" },
      { property: "og:description", content: "Platform uptime, latency and service status." },
    ],
  }),
  component: SystemHealthPage,
});

function SystemHealthPage() {
  const getRootUrl = (path: string) => BASE_URL.replace("/api/v1", "") + path;

  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
  } = useQuery({
    queryKey: ["health", "api"],
    queryFn: () => fetch(getRootUrl("/health")).then((res) => res.json()),
  });

  const { data: db, isLoading: dbLoading } = useQuery({
    queryKey: ["health", "db"],
    queryFn: () => fetch(getRootUrl("/health/database")).then((res) => res.json()),
  });

  const { data: ready, isLoading: readyLoading } = useQuery({
    queryKey: ["health", "ready"],
    queryFn: () => fetch(getRootUrl("/ready")).then((res) => res.json()),
  });

  if (healthError)
    return <ErrorState message={String(healthError)} onRetry={() => window.location.reload()} />;
  if (healthLoading || dbLoading || readyLoading) return <CardSkeleton />;

  const metrics = [
    {
      id: "api",
      label: "API Server",
      status: health?.status === "ok" ? "operational" : "down",
      icon: Server,
    },
    {
      id: "db",
      label: "PostgreSQL Database",
      status: db?.status === "healthy" ? "operational" : "down",
      icon: Database,
    },
    {
      id: "ready",
      label: "System Readiness",
      status: ready?.status === "ok" ? "operational" : "degraded",
      icon: Activity,
    },
  ];

  const statusTone: Record<string, string> = {
    operational: "bg-success/10 text-success",
    degraded: "bg-warning/15 text-warning",
    down: "bg-destructive/10 text-destructive",
  };

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="System health"
        description="Live telemetry for the backend API and database."
      />
      <div className="grid gap-4 md:grid-cols-3 mt-4">
        {metrics.map((metric) => (
          <section key={metric.id} className="surface-card p-5 flex flex-col justify-between h-32">
            <div className="flex items-center gap-3 mb-2">
              <span
                className={`grid size-10 place-items-center rounded-xl ${statusTone[metric.status]}`}
              >
                <metric.icon className="size-5" />
              </span>
              <h2 className="text-base font-semibold">{metric.label}</h2>
            </div>
            <div className="mt-auto">
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${statusTone[metric.status]}`}
              >
                {metric.status}
              </span>
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
