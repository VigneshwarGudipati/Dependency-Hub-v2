import { Link, createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Loader2, Play, RotateCcw, Upload, FileBarChart, GitBranch, FileCode2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { API_ROUTES, apiClient } from "@/services/apiClient";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import type { Repository } from "@/types";

export const Route = createFileRoute("/_shell/scanner")({
  head: () => ({
    meta: [
      { title: "Dependency Scanner — Dependency Hub" },
      {
        name: "description",
        content: "Scan your repository or manual manifest for outdated and vulnerable packages.",
      },
    ],
  }),
  component: ScannerPage,
});

const samplePackageJson = `{
  "name": "my-project",
  "version": "1.0.0",
  "dependencies": {}
}`;

const getScanSteps = (mode: "repository" | "manual") => [
  { 
    id: "read", 
    label: mode === "repository" ? "Acquiring repository" : "Uploading artifact", 
    detail: mode === "repository" ? "Cloning repository and discovering manifest" : "Sending manifest to API" 
  },
  { id: "queue", label: "Queueing scan", detail: "Creating full dependency scan" },
  { id: "process", label: "Processing", detail: "Waiting for backend resolution" },
];

function ScannerPage() {
  const [scanMode, setScanMode] = useState<"repository" | "manual">("repository");
  const [manifest, setManifest] = useState(samplePackageJson);
  const [repositoryId, setRepositoryId] = useState("");
  const [running, setRunning] = useState(false);
  const [stepIndex, setStepIndex] = useState(-1);
  const [result, setResult] = useState<{ vulnerable: number; total: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: repositories } = useQuery<Repository[]>({
    queryKey: ["repositories"],
    queryFn: async () => {
      const res = await apiClient.get(API_ROUTES.repositories);
      return res.data;
    },
  });

  useEffect(() => {
    if (repositories?.length && !repositoryId) {
      setRepositoryId(repositories[0].id);
    }
  }, [repositories, repositoryId]);

  const startScan = async () => {
    if (scanMode === "manual" && manifest.trim().length < 10) {
      toast.error("Add a manifest before scanning.");
      return;
    }
    if (!repositoryId) {
      toast.error("Select a repository first.");
      return;
    }

    setResult(null);
    setRunning(true);
    setStepIndex(0);

    try {
      let scanId;

      if (scanMode === "manual") {
        // Step 1: Upload artifact
        const blob = new Blob([manifest], { type: "application/json" });
        const file = new File([blob], "package.json", { type: "application/json" });
        const formData = new FormData();
        formData.append("file", file);

        const artifactRes = await apiClient.post(API_ROUTES.artifacts(repositoryId), formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const artifactId = artifactRes.data.id;
        setStepIndex(1);

        // Step 2: Create Scan
        const scanRes = await apiClient.post(API_ROUTES.scan(repositoryId), {
          artifact_id: artifactId,
          scan_type: "FULL",
        });
        scanId = scanRes.data.id;
      } else {
        // Repository mode
        // Wait, "Acquiring repository" happens IN Step 1 but since the backend does it all in one API call, we just wait for POST /scans to return.
        const scanRes = await apiClient.post(API_ROUTES.scan(repositoryId), {
          scan_type: "FULL",
        });
        scanId = scanRes.data.id;
        setStepIndex(1);
      }
      
      setStepIndex(2);

      // Step 3: Poll
      let completed = false;
      let finalScan: Record<string, unknown> | null = null;
      while (!completed) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const statusRes = await apiClient.get(API_ROUTES.scanStatus(repositoryId, scanId));
        if (statusRes.data.status === "COMPLETED" || statusRes.data.status === "FAILED") {
          completed = true;
          finalScan = statusRes.data;
        }
      }

      if (finalScan?.status === "FAILED") {
        throw new Error(String(finalScan.error_message) || "Scan failed.");
      }

      setStepIndex(3);
      setResult({
        total: Number(finalScan?.total_dependencies || 0),
        vulnerable: Number(finalScan?.vulnerable_dependencies || 0),
      });
      toast.success("Scan complete", {
        description: `${finalScan?.vulnerable_dependencies} vulnerable of ${finalScan?.total_dependencies} packages.`,
      });
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : err && typeof err === 'object' && 'response' in err ? String((err as any).response?.data?.detail || (err as any).message) : String(err);
      toast.error("Scan error", { description: errorMsg || "Failed to complete scan." });
    } finally {
      setRunning(false);
    }
  };

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    void file.text().then((text) => {
      setManifest(text);
      toast.info(`${file.name} loaded`);
    });
  };

  const scanSteps = getScanSteps(scanMode);

  return (
    <>
      <PageHeader
        eyebrow="Analysis"
        title="Dependency scanner"
        description="Scan your repository or manual manifest for outdated and vulnerable packages."
        actions={
          <Button
            variant="outline"
            onClick={() => {
              setManifest(samplePackageJson);
              setResult(null);
              setStepIndex(-1);
            }}
          >
            <RotateCcw className="size-4" /> Reset
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section className="surface-card p-5">
          <div className="mb-6 flex space-x-1 rounded-lg bg-muted p-1">
            <button
              onClick={() => setScanMode("repository")}
              className={cn(
                "flex flex-1 items-center justify-center space-x-2 rounded-md px-3 py-2 text-sm font-medium transition-all",
                scanMode === "repository"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-background/50"
              )}
            >
              <GitBranch className="size-4" />
              <span>Repository Scan</span>
            </button>
            <button
              onClick={() => setScanMode("manual")}
              className={cn(
                "flex flex-1 items-center justify-center space-x-2 rounded-md px-3 py-2 text-sm font-medium transition-all",
                scanMode === "manual"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-background/50"
              )}
            >
              <FileCode2 className="size-4" />
              <span>Manual Manifest</span>
            </button>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-base font-semibold">
              {scanMode === "repository" ? "Select Repository" : "Manifest input"}
            </h2>
            {scanMode === "manual" && (
              <div className="flex items-center gap-2">
                <input
                  ref={fileRef}
                  type="file"
                  accept=".json,.txt,.lock"
                  className="hidden"
                  onChange={(event) => handleFile(event.target.files?.[0])}
                />
                <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
                  <Upload className="size-4" /> Upload file
                </Button>
              </div>
            )}
          </div>

          {scanMode === "manual" && (
            <div
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                handleFile(event.dataTransfer.files?.[0]);
              }}
              className="mt-4"
            >
              <Textarea
                value={manifest}
                onChange={(event) => setManifest(event.target.value)}
                rows={16}
                spellCheck={false}
                aria-label="Dependency manifest"
                className="font-mono text-xs"
              />
            </div>
          )}

          {scanMode === "repository" && (
            <div className="mt-4 rounded-md border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
              <p>
                In Repository Scan mode, Dependency Hub will securely acquire the selected repository, 
                discover the root manifest (e.g. package.json or requirements.txt), and generate a fresh 
                scan artifact directly from the actual source.
              </p>
            </div>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <Select value={repositoryId} onValueChange={setRepositoryId}>
              <SelectTrigger className="w-56">
                <SelectValue placeholder="Repository" />
              </SelectTrigger>
              <SelectContent>
                {repositories?.map((repo) => (
                  <SelectItem key={repo.id} value={repo.id}>
                    {repo.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={startScan} disabled={running}>
              {running ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              {running ? "Scanning…" : "Run scan"}
            </Button>
          </div>
        </section>

        <aside className="surface-card h-fit p-5">
          <h2 className="text-base font-semibold">Scan pipeline</h2>
          <ol className="mt-4 space-y-4">
            {scanSteps.map((step, index) => {
              const done = stepIndex > index || (!!result && !running);
              const active = running && stepIndex === index;
              return (
                <li key={step.id} className="flex gap-3">
                  <span
                    className={cn(
                      "grid size-7 shrink-0 place-items-center rounded-full border text-xs font-bold",
                      done
                        ? "border-success/40 bg-success/10 text-success"
                        : active
                          ? "border-primary/40 bg-primary/10 text-primary"
                          : "border-border text-muted-foreground",
                    )}
                  >
                    {done ? (
                      <CheckCircle2 className="size-4" />
                    ) : active ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      index + 1
                    )}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{step.label}</p>
                    <p className="text-xs text-muted-foreground">{step.detail}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </aside>
      </div>

      <AnimatePresence>
        {result ? (
          <motion.section
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-4 mt-4"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                ["Total packages", result.total, "text-primary"],
                ["Vulnerable", result.vulnerable, "text-destructive"],
              ].map(([label, value, tone]) => (
                <div key={String(label)} className="surface-card p-5">
                  <p className="text-sm text-muted-foreground">{label}</p>
                  <p className={cn("mt-2 font-display text-3xl font-bold", String(tone))}>
                    {value}
                  </p>
                </div>
              ))}
            </div>

            <div className="surface-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-base font-semibold">Resolved packages</h2>
              </div>
              <div className="mt-4">
                <EmptyState
                  icon={FileBarChart}
                  title="Package details available in repository"
                  description="The scan is complete. Navigate to the repository Packages tab to view detailed dependency and vulnerability reports."
                />
              </div>
            </div>
          </motion.section>
        ) : null}
      </AnimatePresence>
    </>
  );
}
