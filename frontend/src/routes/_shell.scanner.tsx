import { Link, createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Loader2, Play, RotateCcw, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { StatusBadge } from "@/components/common/Badges";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { repositories, samplePackageJson, scanSteps } from "@/data/mockData";
import { mockService } from "@/services/mockService";
import { cn } from "@/lib/utils";
import type { ScanResult } from "@/types";

export const Route = createFileRoute("/_shell/scanner")({
  head: () => ({
    meta: [
      { title: "Dependency Scanner — DepSentry" },
      {
        name: "description",
        content: "Paste or upload a manifest and scan it for outdated and vulnerable packages.",
      },
      { property: "og:title", content: "Dependency Scanner — DepSentry" },
      {
        property: "og:description",
        content: "Scan a manifest for outdated and vulnerable packages.",
      },
    ],
  }),
  component: ScannerPage,
});

function ScannerPage() {
  const [manifest, setManifest] = useState(samplePackageJson);
  const [repository, setRepository] = useState(repositories[0]?.name ?? "payments-api");
  const [running, setRunning] = useState(false);
  const [stepIndex, setStepIndex] = useState(-1);
  const [result, setResult] = useState<ScanResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!running) return undefined;
    if (stepIndex >= scanSteps.length) return undefined;
    const timer = window.setTimeout(() => setStepIndex((prev) => prev + 1), 700);
    return () => window.clearTimeout(timer);
  }, [running, stepIndex]);

  const startScan = async () => {
    if (manifest.trim().length < 10) {
      toast.error("Add a manifest before scanning.");
      return;
    }
    setResult(null);
    setRunning(true);
    setStepIndex(0);
    const scan = await mockService.runScan(repository);
    window.setTimeout(() => {
      setResult(scan);
      setRunning(false);
      toast.success("Scan complete", {
        description: `${scan.vulnerable} vulnerable of ${scan.total} packages.`,
      });
    }, scanSteps.length * 700);
  };

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    void file.text().then((text) => {
      setManifest(text);
      toast.info(`${file.name} loaded`);
    });
  };

  return (
    <>
      <PageHeader
        eyebrow="Analysis"
        title="Dependency scanner"
        description="Upload or paste a manifest, then resolve the tree against live advisory data."
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
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-base font-semibold">Manifest input</h2>
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
          </div>

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
            <p className="mt-2 text-xs text-muted-foreground">
              Drag and drop package.json, requirements.txt or go.mod anywhere in this box.
            </p>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Select value={repository} onValueChange={setRepository}>
              <SelectTrigger className="w-56">
                <SelectValue placeholder="Repository" />
              </SelectTrigger>
              <SelectContent>
                {repositories.map((repo) => (
                  <SelectItem key={repo.id} value={repo.name}>
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
            className="space-y-4"
          >
            <div className="grid gap-4 sm:grid-cols-4">
              {[
                ["Health score", result.healthScore, "text-primary"],
                ["Safe", result.safe, "text-success"],
                ["Outdated", result.outdated, "text-warning"],
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
                <Button asChild size="sm" variant="outline">
                  <Link to="/graph">View dependency graph</Link>
                </Button>
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="py-2">Package</th>
                      <th className="py-2">Installed</th>
                      <th className="py-2">Latest</th>
                      <th className="py-2">Advisory</th>
                      <th className="py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {result.packages.map((pkg) => (
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
                        <td className="py-2.5 font-mono text-xs">{pkg.latestVersion}</td>
                        <td className="py-2.5 font-mono text-xs text-muted-foreground">
                          {pkg.cve ?? "—"}
                        </td>
                        <td className="py-2.5">
                          <StatusBadge status={pkg.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="surface-card p-5">
              <h2 className="text-base font-semibold">Recommended actions</h2>
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                {result.recommendations.map((item) => (
                  <li key={item} className="flex gap-2">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </motion.section>
        ) : null}
      </AnimatePresence>
    </>
  );
}
