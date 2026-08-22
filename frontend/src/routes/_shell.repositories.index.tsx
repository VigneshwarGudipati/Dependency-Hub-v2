import { Link, createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { FolderGit2, GitBranch, Plus, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";
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
import { useProjects } from "@/hooks/useProjects";
import { cn } from "@/lib/utils";
import { formatNumber, timeAgo } from "@/utils/format";

export const Route = createFileRoute("/_shell/repositories/")({
  head: () => ({
    meta: [
      { title: "Repositories — DepSentry" },
      {
        name: "description",
        content: "Browse every monitored repository with health score, findings and last scan.",
      },
      { property: "og:title", content: "Repositories — DepSentry" },
      {
        property: "og:description",
        content: "Every monitored repository with health score, findings and last scan.",
      },
    ],
  }),
  component: RepositoriesPage,
});

const statusTone: Record<string, string> = {
  healthy: "bg-success/10 text-success border-success/30",
  "at-risk": "bg-warning/15 text-warning border-warning/35",
  critical: "bg-destructive/10 text-destructive border-destructive/30",
};

function RepositoriesPage() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [language, setLanguage] = useState("all");

  const { data, isLoading: loading, error, refetch: reload } = useProjects();

  const languages = useMemo(
    // Filter out null/undefined language values before building the unique list
    () => Array.from(new Set((data ?? []).map((repo) => repo.language).filter(Boolean))),
    [data],
  );

  const filtered = useMemo(
    () =>
      (data ?? []).filter((repo) => {
        const matchesQuery = `${repo.name} ${repo.description} ${repo.owner}`
          .toLowerCase()
          .includes(query.toLowerCase());
        const matchesStatus = status === "all" || repo.status === status;
        const matchesLanguage = language === "all" || repo.language === language;
        return matchesQuery && matchesStatus && matchesLanguage;
      }),
    [data, query, status, language],
  );

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title="Repositories"
        description="Every connected codebase, ranked by dependency risk."
        actions={
          <Button asChild>
            <Link to="/repositories/new">
              <Plus className="size-4" /> New repository
            </Link>
          </Button>
        }
      />

      <div className="surface-card flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <SearchInput value={query} onChange={setQuery} placeholder="Search repositories…" />
        <div className="flex flex-1 flex-wrap gap-3 sm:justify-end">
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="healthy">Healthy</SelectItem>
              <SelectItem value="at-risk">At risk</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
            </SelectContent>
          </Select>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Language" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All languages</SelectItem>
              {languages.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {error ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Failed to load repositories."}
          onRetry={() => reload()}
        />
      ) : null}
      {loading ? <TableSkeleton /> : null}

      {!loading && !error && filtered.length === 0 ? (
        <EmptyState
          icon={FolderGit2}
          title="No repositories match your filters"
          description="Try clearing the search term or switching the status filter."
          action={
            <Button
              variant="outline"
              onClick={() => {
                setQuery("");
                setStatus("all");
                setLanguage("all");
              }}
            >
              Reset filters
            </Button>
          }
        />
      ) : null}

      {!loading && !error && filtered.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((repo, index) => (
            <motion.article
              key={repo.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.04 }}
              className="surface-card flex flex-col p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <Link
                    to="/repositories/$repoId"
                    params={{ repoId: repo.id }}
                    className="truncate font-display text-base font-semibold hover:text-primary"
                  >
                    {repo.name}
                  </Link>
                  <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                    {repo.description}
                  </p>
                </div>
                <span
                  className={cn(
                    "shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize",
                    statusTone[repo.status],
                  )}
                >
                  {repo.status.replace("-", " ")}
                </span>
              </div>

              <dl className="mt-4 grid grid-cols-3 gap-2 border-y border-border py-3 text-center">
                <div>
                  <dt className="text-xs text-muted-foreground">Health</dt>
                  <dd className="font-display text-lg font-bold">{repo.healthScore}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Deps</dt>
                  <dd className="font-display text-lg font-bold">
                    {formatNumber(repo.dependencies)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">CVEs</dt>
                  <dd className="font-display text-lg font-bold text-destructive">
                    {repo.vulnerabilities}
                  </dd>
                </div>
              </dl>

              <div className="mt-3 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  <GitBranch className="size-3.5" /> {repo.branch}
                </span>
                <span>Scanned {timeAgo(repo.lastScan)}</span>
              </div>

              <div className="mt-4 flex gap-2">
                <Button asChild size="sm" variant="outline" className="flex-1">
                  <Link to="/repositories/$repoId" params={{ repoId: repo.id }}>
                    Details
                  </Link>
                </Button>
                <Button asChild size="sm" className="flex-1">
                  <Link to="/scanner">
                    <ShieldAlert className="size-4" /> Scan
                  </Link>
                </Button>
              </div>
            </motion.article>
          ))}
        </div>
      ) : null}
    </>
  );
}
