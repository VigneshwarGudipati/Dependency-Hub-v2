import { Link, createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { GitBranch, LineChart, ScanSearch, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/welcome")({
  head: () => ({
    meta: [
      { title: "Welcome to DepSentry — Dependency Risk Control" },
      {
        name: "description",
        content:
          "See how DepSentry scans manifests, scores dependency health and prioritises CVE remediation.",
      },
      { property: "og:title", content: "Welcome to DepSentry" },
      {
        property: "og:description",
        content: "Scan manifests, score dependency health and prioritise CVE remediation.",
      },
    ],
  }),
  component: WelcomeScreen,
});

const features = [
  {
    icon: ScanSearch,
    title: "Manifest scanning",
    body: "Parse package.json, resolve the full tree and flag risky versions in seconds.",
  },
  {
    icon: ShieldCheck,
    title: "CVE intelligence",
    body: "Severity-ranked advisories with CVSS scoring and patched-version guidance.",
  },
  {
    icon: GitBranch,
    title: "Transitive graph",
    body: "Interactive dependency graph with zoom, pan and colour-coded risk states.",
  },
  {
    icon: LineChart,
    title: "Executive reporting",
    body: "Health trends, compliance evidence packs and CSV or PDF exports.",
  },
];

function WelcomeScreen() {
  return (
    <div className="min-h-screen bg-background">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-xl brand-gradient text-navy-foreground">
            <ShieldCheck className="size-5" />
          </span>
          <span className="font-display text-base font-bold">DepSentry</span>
        </div>
        <Button asChild variant="ghost" size="sm">
          <Link to="/login">Sign in</Link>
        </Button>
      </header>

      <section className="relative overflow-hidden">
        <div className="absolute inset-0 grid-backdrop opacity-30" aria-hidden />
        <div className="relative mx-auto max-w-6xl px-5 pb-16 pt-10 sm:px-8 sm:pt-16">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="max-w-3xl"
          >
            <span className="inline-flex items-center rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-primary">
              Supply-chain security, operationalised
            </span>
            <h1 className="mt-5 font-display text-4xl font-bold leading-[1.08] sm:text-6xl">
              Know the health of every dependency you ship.
            </h1>
            <p className="mt-5 max-w-xl text-base text-muted-foreground">
              DepSentry continuously scores your open-source footprint, surfaces exploitable CVEs
              and gives engineering leaders a defensible remediation plan.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link to="/register">Create an account</Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/dashboard">Explore the dashboard</Link>
              </Button>
            </div>
          </motion.div>

          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feature, index) => (
              <motion.article
                key={feature.title}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: 0.1 + index * 0.06 }}
                className="surface-card p-5"
              >
                <span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
                  <feature.icon className="size-5" />
                </span>
                <h2 className="mt-4 text-sm font-semibold">{feature.title}</h2>
                <p className="mt-2 text-sm text-muted-foreground">{feature.body}</p>
              </motion.article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
