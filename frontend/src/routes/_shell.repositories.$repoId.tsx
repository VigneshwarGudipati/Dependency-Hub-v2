import { useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useParams } from "@tanstack/react-router";
import { ArrowLeft, Download, GitBranch, ScanSearch, ShieldAlert, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { SeverityBadge, StatusBadge } from "@/components/common/Badges";
import { HealthRing } from "@/components/common/HealthRing";
import { PageHeader } from "@/components/common/PageHeader";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/common/States";
import { TrendAreaChart } from "@/components/charts/Charts";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { dashboardSummary } from "@/data/mockData";
import { useDependencies } from "@/hooks/useDependencies";
import { useProject } from "@/hooks/useProject";
import { useVulnerabilities } from "@/hooks/useVulnerabilities";
import { API_ROUTES, apiClient } from "@/services/apiClient";
import { downloadFile, formatDate, formatNumber, timeAgo, toCsv } from "@/utils/format";

export const Route = createFileRoute("/_shell/repositories/$repoId")({
  head: () => ({
    meta: [
      { title: "Repository details — DepSentry" },
      {
        name: "description",
        content: "Dependency inventory, vulnerabilities and scan history for a single repository.",
      },
      { property: "og:title", content: "Repository details — DepSentry" },
      {
        property: "og:description",
        content: "Dependency inventory, vulnerabilities and scan history.",
      },
    ],
  }),
  component: RepositoryDetailsPage,
});

function RepositoryDetailsPage() {
  const queryClient = useQueryClient();
  const { repoId } = useParams({ from: "/_shell/repositories/$repoId" });
  // useProject is SSR-safe (enabled: !!token) and consistent with React Query
  const repoQuery = useProject(repoId);
  const packagesQuery = useDependencies({ projectId: repoId });
  const vulnQuery = useVulnerabilities({ projectId: repoId });

  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUploadManifest = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const artifactRes = await apiClient.post(
        `${API_ROUTES.repository(repoId)}/artifacts`,
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
        },
      );

      await apiClient.post(API_ROUTES.scan(repoId), {
        artifact_id: artifactRes.data.id,
        scan_type: "FULL",
        configuration: {},
      });

      toast.success("Scan queued successfully!");
      // Invalidate and refetch all related queries
      queryClient.invalidateQueries({ queryKey: ["project", repoId] });
      packagesQuery.refetch();
      vulnQuery.refetch();
      queryClient.invalidateQueries({ queryKey: ["dependencies"] });
      queryClient.invalidateQueries({ queryKey: ["vulnerabilities"] });
    } catch (error) {
      console.error(error);
      toast.error("Failed to upload manifest");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  if (repoQuery.isError) {
    return (
      <ErrorState
        message={
          repoQuery.error instanceof Error ? repoQuery.error.message : "Failed to load repository."
        }
        onRetry={() => repoQuery.refetch()}
      />
    );
  }

  if (repoQuery.isLoading) {
    return (
      <>
        <CardSkeleton />
        <CardSkeleton />
      </>
    );
  }

  const repo = repoQuery.data;
  if (!repo) {
    return (
      <EmptyState
        title="Repository not found"
        description={`No repository matches "${repoId}".`}
        action={
          <Button asChild variant="outline">
            <Link to="/repositories">Back to repositories</Link>
          </Button>
        }
      />
    );
  }

  const repoPackages = packagesQuery.data?.items ?? [];
  const repoVulns = vulnQuery.data?.items ?? [];

  return (
    <>
      <Link
        to="/repositories"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Repositories
      </Link>

      <PageHeader
        eyebrow={`${repo.owner || "Unknown Owner"} · ${repo.visibility || "Unknown"}`}
        title={repo.name}
        description={repo.description}
        actions={
          <>
            <Button
              variant="outline"
              onClick={() =>
                downloadFile(
                  `${repo.name}-dependencies.csv`,
                  toCsv(
                    repoPackages.map((pkg) => ({
                      package: pkg.name,
                      installed: pkg.installedVersion,
                      latest: pkg.latestVersion || "N/A",
                      status: pkg.status,
                    })),
                  ),
                  "text/csv",
                )
              }
            >
              <Download className="size-4" /> Export SBOM
            </Button>
            <input
              type="file"
              className="hidden"
              ref={fileInputRef}
              onChange={handleUploadManifest}
              accept=".json,.txt"
            />
            <Button
              variant="secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              <Upload className="size-4" /> {uploading ? "Uploading..." : "Upload Manifest"}
            </Button>
            <Button asChild>
              <Link to="/scanner">
                <ScanSearch className="size-4" /> Rescan
              </Link>
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="surface-card flex flex-col items-center gap-4 p-6">
          <HealthRing score={repo.healthScore} label="Repository health" size={150} />
          <dl className="w-full space-y-2 text-sm">
            {[
              ["Language", repo.language],
              ["Branch", repo.branch],
              ["Dependencies", formatNumber(repo.dependencies)],
              ["Outdated", String(repo.outdated)],
              ["Vulnerabilities", String(repo.vulnerabilities)],
              ["Created", formatDate(repo.createdAt)],
              ["Last scan", timeAgo(repo.lastScan)],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-3">
                <dt className="text-muted-foreground">{label}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="surface-card p-5">
          <h2 className="text-base font-semibold">Health over time</h2>
          <p className="text-sm text-muted-foreground">
            Score and open findings recorded on each scheduled scan.
          </p>
          <div className="mt-4">
            <TrendAreaChart data={dashboardSummary.trend} height={280} />
          </div>
        </div>
      </div>

      <Tabs defaultValue="dependencies" className="surface-card p-5">
        <TabsList>
          <TabsTrigger value="dependencies">Dependencies</TabsTrigger>
          <TabsTrigger value="vulnerabilities">Vulnerabilities</TabsTrigger>
          <TabsTrigger value="history">Scan history</TabsTrigger>
        </TabsList>

        <TabsContent value="dependencies" className="mt-4">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="py-2">Package</th>
                  <th className="py-2">Installed</th>
                  <th className="py-2">Latest</th>
                  <th className="py-2">License</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {repoPackages.map((pkg) => (
                  <tr key={pkg.id} className="hover:bg-muted/50">
                    <td className="py-2.5 font-medium">
                      <Link
                        to="/packages/$packageId"
                        params={{ packageId: pkg.id }}
                        className="hover:text-primary"
                      >
                        {pkg.name}
                      </Link>
                    </td>
                    <td className="py-2.5 font-mono text-xs">{pkg.installedVersion}</td>
                    <td className="py-2.5 font-mono text-xs">{pkg.latestVersion || "N/A"}</td>
                    <td className="py-2.5 text-muted-foreground">{pkg.license || "—"}</td>
                    <td className="py-2.5">
                      <StatusBadge status={pkg.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="vulnerabilities" className="mt-4 space-y-3">
          {repoVulns.length === 0 ? (
            <EmptyState icon={ShieldAlert} title="No known vulnerabilities" />
          ) : (
            repoVulns.map((vuln) => (
              <div key={vuln.id} className="rounded-xl border border-border p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-semibold">{vuln.cve}</span>
                  <SeverityBadge severity={vuln.severity} />
                  <span className="text-xs text-muted-foreground">CVSS {vuln.cvss}</span>
                </div>
                <p className="mt-2 text-sm font-medium">{vuln.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">{vuln.recommendation}</p>
              </div>
            ))
          )}
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          <ul className="space-y-3">
            {dashboardSummary.trend
              .slice(-6)
              .reverse()
              .map((point, index) => (
                <li
                  key={point.label}
                  className="flex items-center justify-between rounded-xl border border-border px-4 py-3 text-sm"
                >
                  <span className="inline-flex items-center gap-2">
                    <GitBranch className="size-4 text-muted-foreground" />
                    Scheduled scan · {point.label}
                  </span>
                  <span className="text-muted-foreground">
                    Score {point.value} · {point.secondary ?? 0} findings
                    {index === 0 ? " · latest" : ""}
                  </span>
                </li>
              ))}
          </ul>
        </TabsContent>
      </Tabs>
    </>
  );
}
