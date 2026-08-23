import { Link, createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/password-reset-success")({
  head: () => ({
    meta: [
      { title: "Password reset complete — Dependency Hub" },
      { name: "description", content: "Your Dependency Hub password was reset successfully." },
      { property: "og:title", content: "Password reset complete — Dependency Hub" },
      { property: "og:description", content: "Your password was reset successfully." },
    ],
  }),
  component: ResetSuccessPage,
});

function ResetSuccessPage() {
  return (
    <AuthLayout
      title="You're all set"
      subtitle="Your password has been updated across every Dependency Hub session."
    >
      <div className="space-y-6 text-center">
        <motion.span
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 220, damping: 16 }}
          className="mx-auto grid size-16 place-items-center rounded-2xl bg-success/12 text-success"
        >
          <CheckCircle2 className="size-8" />
        </motion.span>
        <p className="text-sm text-muted-foreground">
          For your safety we signed out all other devices. Sign in again to continue monitoring
          dependency health.
        </p>
        <Button asChild size="lg" className="w-full">
          <Link to="/login">Back to sign in</Link>
        </Button>
      </div>
    </AuthLayout>
  );
}
