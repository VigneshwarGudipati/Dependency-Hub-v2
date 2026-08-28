import { Link, createFileRoute, useParams } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { SeverityBadge, StatusBadge } from "@/components/common/Badges";
import { HealthRing } from "@/components/common/HealthRing";
import { PageHeader } from "@/components/common/PageHeader";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { useDependency } from "@/hooks/useDependencies";
import { formatCompact, formatDate } from "@/utils/format";

export const Route = createFileRoute("/_shell/packages/$packageId")({
  head: () => ({
    meta: [
      { title: "Package details — Dependency Hub" },
      {
        name: "description",
        content: "Version drift, license, maintenance signals and advisories for a single package.",
      },
      { property: "og:title", content: "Package details — Dependency Hub" },
      {
        property: "og:description",
        content: "Version drift, license and advisories for a package.",
      },
    ],
  }),
  component: PackageDetailsPage,
});

function PackageDetailsPage() {
  const { packageId } = useParams({ from: "/_shell/packages/$packageId" });
  const { data, isLoading: loading, error, refetch: reload } = useDependency(packageId);

  const errorMessage = error instanceof Error ? error.message : "Failed to load package details.";

  if (error) return <ErrorState message={errorMessage} onRetry={() => reload()} />;
  if (loading) return <CardSkeleton />;
  if (!data)
    return (
      <EmptyState
        title="Package not found"
        description={`No package matches "${packageId}".`}
        action={
          <Button asChild variant="outline">
            <Link to="/packages">Back to packages</Link>
          </Button>
        }
      />
    );

  return (
    <>
      <Link
        to="/packages"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Packages
      </Link>

      <PageHeader
        eyebrow={data.direct ? "Direct dependency" : "Transitive dependency"}
        title={data.name}
        description={data.description}
        actions={<StatusBadge status={data.status} />}
      />

      <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="surface-card flex flex-col items-center gap-4 p-6">
          <HealthRing score={data.healthScore || null} label="Package health" size={150} />
          {data.severity ? <SeverityBadge severity={data.severity} /> : null}
        </div>

        <div className="space-y-4">
          <div className="surface-card grid gap-4 p-5 sm:grid-cols-3">
            {[
              ["Installed Version", data.installedVersion || "N/A"],
              [
                "Latest Version",
                data.registryStatus === "PROVIDER_UNAVAILABLE" || data.registryStatus === "TIMEOUT"
                  ? "Unavailable"
                  : data.registryStatus === "NOT_FOUND"
                    ? "Not Found"
                    : data.latestVersion || "Unknown",
              ],
              [
                "Outdated",
                data.outdated === "TRUE"
                  ? "Outdated"
                  : data.outdated === "FALSE"
                    ? "Up to date"
                    : "Unknown",
              ],
              ["License", data.license || "Unknown"],
              ["Published", data.publishedAt ? formatDate(data.publishedAt) : "Unknown"],
              [
                "Registry",
                data.registryStatus === "PROVIDER_UNAVAILABLE" || data.registryStatus === "TIMEOUT"
                  ? "Unavailable"
                  : data.registrySource || "Unknown",
              ],
              ["Registry Status", data.registryStatus || "Unknown"],
              ["Advisory", data.cve ?? "None"],
              ["Repository", data.repository],
            ].map(([label, value]) => (
              <div key={label}>
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="mt-1 font-medium">{value}</p>
              </div>
            ))}
          </div>

          <div className="surface-card p-5">
            <h2 className="text-base font-semibold">Dependents</h2>
            <ul className="mt-3 flex flex-wrap gap-2">
              {data.dependents && data.dependents.length > 0 ? (
                data.dependents.map((dependent) => (
                  <li
                    key={dependent}
                    className="rounded-full bg-muted px-3 py-1 font-mono text-xs text-muted-foreground"
                  >
                    {dependent}
                  </li>
                ))
              ) : (
                <li className="text-sm text-muted-foreground">No dependents</li>
              )}
            </ul>
          </div>
        </div>
      </div>
    </>
  );
}
