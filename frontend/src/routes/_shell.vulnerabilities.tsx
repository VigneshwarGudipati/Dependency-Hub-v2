import { useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { AlertOctagon, Download, ShieldAlert, ShieldCheck, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { SeverityBadge } from "@/components/common/Badges";
import { PageHeader } from "@/components/common/PageHeader";
import { SearchInput } from "@/components/common/SearchInput";
import { StatCard } from "@/components/common/StatCard";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/common/States";
import { SeverityBarChart } from "@/components/charts/Charts";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { useVulnerabilities } from "@/hooks/useVulnerabilities";
import { downloadFile, formatDate, toCsv } from "@/utils/format";
import type { Severity, Vulnerability } from "@/types";

export const Route = createFileRoute("/_shell/vulnerabilities")({
  head: () => ({
    meta: [
      { title: "Vulnerabilities — DepSentry" },
      {
        name: "description",
        content: "Severity-ranked CVE findings with CVSS scores and patched-version guidance.",
      },
      { property: "og:title", content: "Vulnerabilities — DepSentry" },
      {
        property: "og:description",
        content: "Severity-ranked CVE findings across your portfolio.",
      },
    ],
  }),
  component: VulnerabilitiesPage,
});

function VulnerabilitiesPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [severity, setSeverity] = useState("all");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Vulnerability | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
      setPage(1); // Reset page on query change
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const {
    data,
    isLoading: loading,
    error,
    refetch: reload,
  } = useVulnerabilities({
    page,
    pageSize: 25,
    query: debouncedQuery,
    severity,
  });

  const handleSeverityChange = (newSeverity: string) => {
    setSeverity(newSeverity);
    setPage(1);
  };

  const errorMessage = error instanceof Error ? error.message : "Failed to load vulnerabilities.";
  const list = data?.items ?? [];
  const counts = useMemo(() => {
    const base: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    list.forEach((item) => {
      // Safely increment only if severity is a known key
      if (item.severity in base) {
        base[item.severity as Severity] += 1;
      }
    });
    return base;
  }, [list]);

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title="Vulnerability dashboard"
        description="Every open advisory affecting your dependency footprint, ranked by exploitability."
        actions={
          <Button
            variant="outline"
            onClick={() =>
              downloadFile(
                "depsentry-vulnerabilities.csv",
                toCsv(
                  list.map((item) => ({
                    cve: item.cve,
                    package: item.packageName,
                    severity: item.severity,
                    cvss: item.cvss,
                    repository: item.repository,
                    patched: item.patchedVersion,
                  })),
                ),
                "text/csv",
              )
            }
          >
            <Download className="size-4" /> Export CSV
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          index={0}
          label="Critical"
          value={counts.critical}
          icon={AlertOctagon}
          tone="destructive"
        />
        <StatCard
          index={1}
          label="High"
          value={counts.high}
          icon={ShieldAlert}
          tone="destructive"
        />
        <StatCard
          index={2}
          label="Medium"
          value={counts.medium}
          icon={TriangleAlert}
          tone="warning"
        />
        <StatCard index={3} label="Low" value={counts.low} icon={ShieldCheck} tone="success" />
      </div>

      <section className="surface-card p-5">
        <h2 className="text-base font-semibold">Findings by severity</h2>
        <div className="mt-4">
          <SeverityBarChart
            data={(["critical", "high", "medium", "low"] as const).map((key) => ({
              label: key[0]!.toUpperCase() + key.slice(1),
              value: counts[key],
            }))}
          />
        </div>
      </section>

      <div className="surface-card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <SearchInput value={query} onChange={setQuery} placeholder="Search CVE or package…" />
        <Select value={severity} onValueChange={handleSeverityChange}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All severities</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {error ? <ErrorState message={errorMessage} onRetry={() => reload()} /> : null}
      {loading ? <TableSkeleton /> : null}

      {!loading && !error ? (
        list.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title="No matching advisories"
            description="Nothing matches this filter — that's usually good news."
          />
        ) : (
          <div className="surface-card overflow-x-auto p-1">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">CVE</th>
                  <th className="px-4 py-3">Package</th>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">CVSS</th>
                  <th className="px-4 py-3">Repository</th>
                  <th className="px-4 py-3">Published</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.map((item) => (
                  <tr key={item.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3 font-mono text-xs font-semibold">{item.cve}</td>
                    <td className="px-4 py-3 font-medium">{item.packageName}</td>
                    <td className="px-4 py-3">
                      <SeverityBadge severity={item.severity as Severity} />
                    </td>
                    <td className="px-4 py-3 tabular-nums">{item.cvss || "N/A"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{item.repository}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {item.publishedAt && item.publishedAt !== "N/A"
                        ? formatDate(item.publishedAt)
                        : "N/A"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button size="sm" variant="outline" onClick={() => setSelected(item)}>
                        Details
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : null}

      {!loading && !error && data && data.total_pages > 1 && (
        <div className="mt-4">
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className={page === 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                />
              </PaginationItem>
              <PaginationItem>
                <div className="px-4 text-sm font-medium">
                  Page {page} of {data.total_pages}
                </div>
              </PaginationItem>
              <PaginationItem>
                <PaginationNext
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  className={
                    page === data.total_pages ? "pointer-events-none opacity-50" : "cursor-pointer"
                  }
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      )}

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-w-lg">
          {selected ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm">{selected.cve}</span>
                  <SeverityBadge severity={selected.severity as Severity} />
                </DialogTitle>
                <DialogDescription>{selected.title || selected.cve}</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 text-sm">
                <p className="text-muted-foreground">{selected.description}</p>
                <dl className="grid grid-cols-2 gap-3 rounded-xl border border-border p-4">
                  {[
                    ["Package", selected.packageName],
                    ["CVSS", selected.cvss ? String(selected.cvss) : "N/A"],
                    ["Source", selected.source === "NVD" ? "Fixture / Test Data" : selected.source],
                    ["Affected", selected.affectedVersions || "N/A"],
                    ["Patched in", selected.patchedVersion || "N/A"],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt className="text-xs text-muted-foreground">{label}</dt>
                      <dd className="font-medium">{value}</dd>
                    </div>
                  ))}
                </dl>
                <div className="rounded-xl bg-success/10 p-4 text-success">
                  <p className="text-xs font-semibold uppercase tracking-wide">Recommendation</p>
                  <p className="mt-1 text-sm">{selected.recommendation || "N/A"}</p>
                </div>
                <Button asChild variant="outline" className="w-full">
                  <Link to="/packages">Review affected packages</Link>
                </Button>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
