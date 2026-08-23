import { createFileRoute } from "@tanstack/react-router";
import { FileBarChart } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/States";

export const Route = createFileRoute("/_shell/reports")({
  head: () => ({
    meta: [
      { title: "Reports — Dependency Hub" },
      {
        name: "description",
        content: "Generate and download security, compliance and health reports.",
      },
      { property: "og:title", content: "Reports — Dependency Hub" },
      { property: "og:description", content: "Security, compliance and health report exports." },
    ],
  }),
  component: ReportsPage,
});

function ReportsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Security"
        title="Reports"
        description="Evidence packs for auditors, executives and engineering leads."
      />
      <div className="pt-8">
        <EmptyState
          icon={FileBarChart}
          title="Report generation is planned for a future release."
          description="In a future update, this page will allow you to generate and download security, compliance, and health reports."
        />
      </div>
    </>
  );
}
