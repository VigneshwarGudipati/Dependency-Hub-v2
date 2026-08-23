import { Link, createFileRoute } from "@tanstack/react-router";
import { Lock } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/forbidden")({
  head: () => ({
    meta: [
      { title: "Access denied (403) — Dependency Hub" },
      {
        name: "description",
        content: "You don't have permission to view this Dependency Hub resource.",
      },
      { property: "og:title", content: "Access denied — Dependency Hub" },
      { property: "og:description", content: "You don't have permission to view this resource." },
    ],
  }),
  component: ForbiddenPage,
});

function ForbiddenPage() {
  return (
    <div className="grid min-h-screen place-items-center px-6">
      <div className="max-w-md text-center">
        <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-warning/15 text-warning">
          <Lock className="size-8" />
        </span>
        <p className="mt-6 font-display text-5xl font-bold">403</p>
        <h1 className="mt-2 text-xl font-semibold">Access denied</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Your role doesn't include permission for this workspace area. Ask an administrator to
          grant access.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button asChild>
            <Link to="/dashboard">Back to dashboard</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/settings">Review access</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
