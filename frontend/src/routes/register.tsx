import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { Check, Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { apiClient, API_ROUTES, setTokens } from "@/services/apiClient";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create your DepSentry account" },
      {
        name: "description",
        content: "Create a DepSentry account to start scanning dependencies for vulnerabilities.",
      },
      { property: "og:title", content: "Create your DepSentry account" },
      { property: "og:description", content: "Start scanning dependencies for vulnerabilities." },
    ],
  }),
  component: RegisterPage,
});

function strengthOf(password: string) {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;
  return score;
}

function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", company: "", email: "", password: "" });
  const [accepted, setAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const score = strengthOf(form.password);
  const labels = ["Too weak", "Weak", "Fair", "Strong", "Excellent"];

  const update = (key: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!form.name || !form.email.includes("@") || score < 2) {
      setError("Complete every field and choose a stronger password.");
      return;
    }
    if (!accepted) {
      setError("Accept the terms of service to continue.");
      return;
    }
    try {
      const resp = await apiClient.post(API_ROUTES.register, {
        name: form.name,
        company: form.company,
        email: form.email,
        password: form.password,
      });
      setTokens(resp.data.access_token, resp.data.refresh_token);
      toast.success("Account created", { description: "Welcome to DepSentry." });
      navigate({ to: "/dashboard" });
    } catch (error: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const err = error as any;
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.error?.message ||
        "Registration failed or network error.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start monitoring dependency risk across every repository."
      footer={
        <span>
          Already registered?{" "}
          <Link to="/login" className="font-semibold text-primary hover:underline">
            Sign in
          </Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="name">Full name</Label>
            <Input
              id="name"
              value={form.name}
              onChange={(event) => update("name", event.target.value)}
              placeholder="Priya Raman"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="company">Company</Label>
            <Input
              id="company"
              value={form.company}
              onChange={(event) => update("company", event.target.value)}
              placeholder="Acme Corp"
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Work email</Label>
          <Input
            id="email"
            type="email"
            value={form.email}
            onChange={(event) => update("email", event.target.value)}
            placeholder="you@company.com"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            value={form.password}
            onChange={(event) => update("password", event.target.value)}
            placeholder="At least 8 characters"
          />
          <div className="flex items-center gap-2">
            <div className="flex flex-1 gap-1">
              {[0, 1, 2, 3].map((index) => (
                <span
                  key={index}
                  className={cn(
                    "h-1.5 flex-1 rounded-full transition-colors",
                    index < score
                      ? score <= 1
                        ? "bg-destructive"
                        : score === 2
                          ? "bg-warning"
                          : "bg-success"
                      : "bg-muted",
                  )}
                />
              ))}
            </div>
            <span className="text-xs text-muted-foreground">{labels[score]}</span>
          </div>
        </div>

        <label className="flex items-start gap-2 text-sm text-muted-foreground">
          <Checkbox
            checked={accepted}
            onCheckedChange={(value) => setAccepted(value === true)}
            className="mt-0.5"
          />
          I agree to the terms of service and data processing addendum.
        </label>

        {error ? (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <Button type="submit" className="w-full" size="lg" disabled={loading}>
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
          {loading ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthLayout>
  );
}
