import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "DepSentry — Launching your dependency workspace" },
      {
        name: "description",
        content: "Initialising the DepSentry dependency health workspace and security feeds.",
      },
      { property: "og:title", content: "DepSentry — Dependency Health Dashboard" },
      {
        property: "og:description",
        content: "Initialising the DepSentry dependency health workspace and security feeds.",
      },
    ],
  }),
  component: SplashScreen,
});

const bootMessages = [
  "Loading security advisories…",
  "Syncing registry metadata…",
  "Preparing workspace…",
];

function SplashScreen() {
  const navigate = useNavigate();
  const [progress, setProgress] = useState(8);
  const [message, setMessage] = useState(bootMessages[0]!);

  useEffect(() => {
    const tick = window.setInterval(() => {
      setProgress((prev) => {
        const next = Math.min(100, prev + 6);
        setMessage(bootMessages[Math.min(bootMessages.length - 1, Math.floor(next / 40))]!);
        return next;
      });
    }, 110);
    return () => window.clearInterval(tick);
  }, []);

  useEffect(() => {
    if (progress >= 100) {
      const timeout = window.setTimeout(() => navigate({ to: "/welcome" }), 400);
      return () => window.clearTimeout(timeout);
    }
    return undefined;
  }, [progress, navigate]);

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden brand-gradient px-6 text-navy-foreground">
      <div className="absolute inset-0 grid-backdrop opacity-40" aria-hidden />
      <motion.div
        initial={{ opacity: 0, scale: 0.94 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="relative w-full max-w-sm text-center"
      >
        <motion.span
          animate={{ scale: [1, 1.06, 1] }}
          transition={{ duration: 2.2, repeat: Infinity }}
          className="mx-auto grid size-20 place-items-center rounded-3xl bg-navy-foreground/12 backdrop-blur"
        >
          <ShieldCheck className="size-10" />
        </motion.span>
        <h1 className="mt-6 font-display text-3xl font-bold">DepSentry</h1>
        <p className="mt-2 text-sm text-navy-foreground/70">Software Dependency Health Dashboard</p>

        <div className="mt-10 h-1.5 w-full overflow-hidden rounded-full bg-navy-foreground/15">
          <motion.div
            className="h-full rounded-full bg-navy-foreground"
            animate={{ width: `${progress}%` }}
            transition={{ ease: "linear", duration: 0.12 }}
          />
        </div>
        <p className="mt-3 text-xs text-navy-foreground/60">{message}</p>

        <button
          type="button"
          onClick={() => navigate({ to: "/welcome" })}
          className="mt-8 text-xs font-semibold uppercase tracking-[0.16em] text-navy-foreground/70 underline-offset-4 hover:underline"
        >
          Skip intro
        </button>
      </motion.div>
    </div>
  );
}
