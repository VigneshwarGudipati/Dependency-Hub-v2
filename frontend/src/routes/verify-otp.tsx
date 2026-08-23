import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/button";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";

export const Route = createFileRoute("/verify-otp")({
  head: () => ({
    meta: [
      { title: "Verify your identity — Dependency Hub" },
      {
        name: "description",
        content: "Enter the 6-digit code we sent to verify your Dependency Hub account.",
      },
      { property: "og:title", content: "Verify your identity — Dependency Hub" },
      { property: "og:description", content: "Enter the 6-digit verification code." },
    ],
  }),
  component: VerifyOtpPage,
});

function VerifyOtpPage() {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(42);

  useEffect(() => {
    if (seconds <= 0) return undefined;
    const timer = window.setTimeout(() => setSeconds((prev) => prev - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [seconds]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (code.length !== 6) {
      setError("Enter all six digits of the verification code.");
      return;
    }
    setError(null);
    setLoading(true);
    window.setTimeout(() => {
      setLoading(false);
      toast.success("Identity verified");
      navigate({ to: "/dashboard" });
    }, 900);
  };

  return (
    <AuthLayout
      title="Two-step verification"
      subtitle="We sent a 6-digit code to your email. It expires in 10 minutes."
      footer={
        <span>
          Wrong address?{" "}
          <Link to="/register" className="font-semibold text-primary hover:underline">
            Change email
          </Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="flex justify-center">
          <InputOTP maxLength={6} value={code} onChange={setCode}>
            <InputOTPGroup>
              {[0, 1, 2, 3, 4, 5].map((index) => (
                <InputOTPSlot key={index} index={index} className="size-12 text-lg" />
              ))}
            </InputOTPGroup>
          </InputOTP>
        </div>

        {error ? (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-center text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <Button type="submit" className="w-full" size="lg" disabled={loading}>
          {loading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <ShieldCheck className="size-4" />
          )}
          {loading ? "Verifying…" : "Verify and continue"}
        </Button>

        <div className="text-center text-sm text-muted-foreground">
          {seconds > 0 ? (
            <span>Resend code in {seconds}s</span>
          ) : (
            <button
              type="button"
              onClick={() => {
                setSeconds(42);
                toast.info("A new code is on its way.");
              }}
              className="font-semibold text-primary hover:underline"
            >
              Resend verification code
            </button>
          )}
        </div>
      </form>
    </AuthLayout>
  );
}
