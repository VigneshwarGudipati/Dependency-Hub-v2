import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden brand-gradient p-12 text-navy-foreground lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 grid-backdrop opacity-40" aria-hidden />
        <Link to="/" className="relative flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-navy-foreground/15">
            <ShieldCheck className="size-5" />
          </span>
          <span className="font-display text-lg font-bold">Dependency Hub</span>
        </Link>
        <div className="relative max-w-md space-y-5">
          <h2 className="font-display text-4xl font-bold leading-tight">
            Continuous visibility into every dependency you ship.
          </h2>
          <p className="text-sm text-navy-foreground/75">
            Scan manifests, map transitive risk, and remediate CVEs before they reach production.
          </p>
          <dl className="grid grid-cols-3 gap-4 border-t border-navy-foreground/15 pt-5">
            {[
              ["1.5k+", "Packages tracked"],
              ["36", "Open findings"],
              ["3.4d", "Mean time to patch"],
            ].map(([value, label]) => (
              <div key={label}>
                <dt className="font-display text-2xl font-bold">{value}</dt>
                <dd className="text-xs text-navy-foreground/70">{label}</dd>
              </div>
            ))}
          </dl>
        </div>
        <p className="relative text-xs text-navy-foreground/60">
          SOC 2 Type II · ISO 27001 · Frontend demo with mock data
        </p>
      </div>

      <div className="flex items-center justify-center px-5 py-12 sm:px-10">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="w-full max-w-md"
        >
          <Link to="/" className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground">
              <ShieldCheck className="size-5" />
            </span>
            <span className="font-display text-base font-bold">Dependency Hub</span>
          </Link>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          <div className="mt-8">{children}</div>
          {footer ? <div className="mt-6 text-sm text-muted-foreground">{footer}</div> : null}
        </motion.div>
      </div>
    </div>
  );
}
