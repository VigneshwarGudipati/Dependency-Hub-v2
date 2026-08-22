import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Loader2, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { API_ROUTES, apiClient } from "@/services/apiClient";

export const Route = createFileRoute("/_shell/repositories/new")({
  head: () => ({
    meta: [
      { title: "Connect a repository — DepSentry" },
      {
        name: "description",
        content:
          "Connect a repository so DepSentry can scan its dependency manifest on every push.",
      },
      { property: "og:title", content: "Connect a repository — DepSentry" },
      { property: "og:description", content: "Scan a new repository's dependency manifest." },
    ],
  }),
  component: CreateRepositoryPage,
});

const languages = ["TypeScript", "JavaScript", "Python", "Go", "Java", "Rust"];

function CreateRepositoryPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    description: "",
    language: "TypeScript",
    visibility: "PRIVATE" as "PRIVATE" | "ORGANIZATION",
    branch: "main",
    url: "",
  });
  const [errors, setErrors] = useState<{
    name?: string;
    description?: string;
    branch?: string;
  }>({});
  const [saving, setSaving] = useState(false);

  const update = (key: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const nextErrors: { name?: string; description?: string; branch?: string } = {};
    if (!/^[a-z0-9-]{3,}$/i.test(form.name))
      nextErrors.name = "Use at least 3 characters — letters, numbers and hyphens only.";
    if (form.description.trim().length < 10)
      nextErrors.description = "Add a short description (10+ characters).";
    if (!form.branch.trim()) nextErrors.branch = "A default branch is required.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSaving(true);
    try {
      const res = await apiClient.post(API_ROUTES.repositories, {
        name: form.name,
        description: form.description,
        language: form.language,
        visibility: form.visibility,
        branch: form.branch,
        url: form.url,
      });
      const created = res.data;
      toast.success("Repository connected", {
        description: `${created.name} is queued for a scan.`,
      });
      navigate({ to: "/repositories" });
    } catch (error: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const err = error as any;
      toast.error("Failed to connect repository", {
        description: err.response?.data?.error?.message || err.message,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Repositories"
        title="Connect a repository"
        description="DepSentry parses the manifest, resolves the tree and scores health after every push."
      />

      <form onSubmit={handleSubmit} className="grid gap-4 lg:grid-cols-3">
        <div className="surface-card space-y-5 p-6 lg:col-span-2">
          <div className="space-y-2">
            <Label htmlFor="name">Repository name</Label>
            <Input
              id="name"
              value={form.name}
              onChange={(event) => update("name", event.target.value)}
              placeholder="payments-api"
            />
            {errors.name ? <p className="text-xs text-destructive">{errors.name}</p> : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="url">Git remote URL</Label>
            <Input
              id="url"
              value={form.url}
              onChange={(event) => update("url", event.target.value)}
              placeholder="https://github.com/acme/payments-api.git"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              rows={4}
              value={form.description}
              onChange={(event) => update("description", event.target.value)}
              placeholder="What does this service do?"
            />
            {errors.description ? (
              <p className="text-xs text-destructive">{errors.description}</p>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>Primary language</Label>
              <Select value={form.language} onValueChange={(value) => update("language", value)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {languages.map((language) => (
                    <SelectItem key={language} value={language}>
                      {language}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Visibility</Label>
              <Select
                value={form.visibility}
                onValueChange={(value) => update("visibility", value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="PRIVATE">Private</SelectItem>
                  <SelectItem value="ORGANIZATION">Organization</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="branch">Default branch</Label>
              <Input
                id="branch"
                value={form.branch}
                onChange={(event) => update("branch", event.target.value)}
              />
              {errors.branch ? <p className="text-xs text-destructive">{errors.branch}</p> : null}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 pt-2">
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
              {saving ? "Connecting…" : "Connect repository"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => navigate({ to: "/repositories" })}>
              Cancel
            </Button>
          </div>
        </div>

        <aside className="surface-card h-fit space-y-4 p-6">
          <h2 className="text-sm font-semibold">What happens next</h2>
          <ol className="space-y-3 text-sm text-muted-foreground">
            {[
              "We clone metadata and read the dependency manifest.",
              "The transitive tree is resolved and matched against advisory feeds.",
              "A health score and remediation plan are published to your dashboard.",
            ].map((step, index) => (
              <li key={step} className="flex gap-3">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                  {index + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </aside>
      </form>
    </>
  );
}
