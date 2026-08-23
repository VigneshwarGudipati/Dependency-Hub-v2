import { Link, createFileRoute } from "@tanstack/react-router";
import { Boxes } from "lucide-react";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/common/Badges";
import { PageHeader } from "@/components/common/PageHeader";
import { SearchInput } from "@/components/common/SearchInput";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/common/States";
import { Button } from "@/components/ui/button";
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
import { useDependencies } from "@/hooks/useDependencies";
import { formatCompact } from "@/utils/format";

export const Route = createFileRoute("/_shell/packages/")({
  head: () => ({
    meta: [
      { title: "Packages — Dependency Hub" },
      {
        name: "description",
        content: "Inventory of every direct and transitive package with health and license data.",
      },
      { property: "og:title", content: "Packages — Dependency Hub" },
      {
        property: "og:description",
        content: "Every direct and transitive package in one inventory.",
      },
    ],
  }),
  component: PackagesPage,
});

function PackagesPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);

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
  } = useDependencies({
    page,
    pageSize: 25,
    query: debouncedQuery,
    status,
  });

  const handleStatusChange = (newStatus: string) => {
    setStatus(newStatus);
    setPage(1);
  };

  const errorMessage = error instanceof Error ? error.message : "Failed to load packages.";
  const items = data?.items ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Analysis"
        title="Package inventory"
        description="Every resolved package with version drift, licensing and maintenance signals."
      />

      <div className="surface-card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <SearchInput value={query} onChange={setQuery} placeholder="Search packages…" />
        <Select value={status} onValueChange={handleStatusChange}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="safe">Safe</SelectItem>
            <SelectItem value="outdated">Outdated</SelectItem>
            <SelectItem value="vulnerable">Vulnerable</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {error ? <ErrorState message={errorMessage} onRetry={() => reload()} /> : null}
      {loading ? <TableSkeleton /> : null}

      {!loading && !error ? (
        items.length === 0 ? (
          <EmptyState icon={Boxes} title="No packages match your filters" />
        ) : (
          <div className="surface-card overflow-x-auto p-1">
            <table className="w-full min-w-[820px] text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Package</th>
                  <th className="px-4 py-3">Installed</th>
                  <th className="px-4 py-3">Latest</th>
                  <th className="px-4 py-3">License</th>
                  <th className="px-4 py-3">Downloads</th>
                  <th className="px-4 py-3">Health</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((pkg) => (
                  <tr key={pkg.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium">{pkg.name}</td>
                    <td className="px-4 py-3 font-mono text-xs">{pkg.installedVersion}</td>
                    <td className="px-4 py-3 font-mono text-xs">{pkg.latestVersion || "N/A"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{pkg.license || "—"}</td>
                    <td className="px-4 py-3 tabular-nums">
                      {pkg.weeklyDownloads ? formatCompact(pkg.weeklyDownloads) : "N/A"}
                    </td>
                    <td className="px-4 py-3 tabular-nums">{pkg.healthScore || "N/A"}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={pkg.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button asChild size="sm" variant="outline">
                        <Link to="/packages/$packageId" params={{ packageId: pkg.id }}>
                          View
                        </Link>
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
    </>
  );
}
