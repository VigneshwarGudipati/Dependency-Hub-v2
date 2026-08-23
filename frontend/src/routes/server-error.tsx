import { Link, createFileRoute } from "@tanstack/react-router";
import { ServerCrash } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/server-error")({
  head: () => ({
    meta: [
      { title: "Server error (500) — Dependency Hub" },
      { name: "description", content: "Something went wrong on the Dependency Hub platform." },
      { property: "og:title", content: "Server error — Dependency Hub" },
      {
        property: "og:description",
        content: "Something went wrong on the Dependency Hub platform.",
      },
    ],
  }),
  component: ServerErrorPage,
});

function ServerErrorPage() {
  return (
    <div className="grid min-h-screen place-items-center px-6">
      <div className="max-w-md text-center">
        <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-destructive/10 text-destructive">
          <ServerCrash className="size-8" />
        </span>
        <p className="mt-6 font-display text-5xl font-bold">500</p>
        <h1 className="mt-2 text-xl font-semibold">Something broke on our side</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The scan service returned an unexpected error. Our team has been notified — try again in a
          moment.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button onClick={() => window.location.reload()}>Retry</Button>
          <Button asChild variant="outline">
            <Link to="/dashboard">Back to dashboard</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
