import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/useAuth";
import { Loader2 } from "lucide-react";

export const Route = createFileRoute("/_shell/settings")({
  head: () => ({
    meta: [
      { title: "Settings — DepSentry" },
      {
        name: "description",
        content: "Profile, notification, scanning and integration preferences.",
      },
      { property: "og:title", content: "Settings — DepSentry" },
      { property: "og:description", content: "Profile, notification and scanning preferences." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const { data: user, isLoading } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (user) {
      setName(user.full_name || user.username || "");
      setEmail(user.email || "");
    }
  }, [user]);

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Settings"
        description="Tune how DepSentry scans, alerts and integrates with your toolchain."
      />

      <Tabs defaultValue="profile" className="surface-card p-5">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="scanning">Scanning</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-5 max-w-lg space-y-4">
          <div className="space-y-2">
            <Label htmlFor="settings-name">Full name</Label>
            <Input
              id="settings-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="settings-email">Work email</Label>
            <Input
              id="settings-email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <Button disabled onClick={() => toast.success("Profile saved")}>
            Save changes (Deferred)
          </Button>
        </TabsContent>

        <TabsContent value="notifications" className="mt-5 max-w-lg space-y-4">
          {[
            ["Critical CVE alerts", "Email me the moment a critical advisory lands."],
            ["Weekly digest", "A Monday summary of health movement and new findings."],
            ["Scan failures", "Notify me when a scheduled scan cannot complete."],
          ].map(([title, body], index) => (
            <label
              key={title}
              className="flex items-start justify-between gap-4 rounded-xl border border-border p-4"
            >
              <span>
                <span className="block text-sm font-medium">{title}</span>
                <span className="block text-sm text-muted-foreground">{body}</span>
              </span>
              <Switch defaultChecked={index !== 2} />
            </label>
          ))}
        </TabsContent>

        <TabsContent value="scanning" className="mt-5 max-w-lg space-y-4">
          {[
            [
              "Enable automated scanning",
              "Trigger a full resolution whenever a new manifest is uploaded via API.",
            ],
            ["Include dev dependencies", "Resolve devDependencies alongside production packages."],
            [
              "Alert on critical severity",
              "Flag repositories and raise alerts when a critical CVE is introduced.",
            ],
          ].map(([title, body], index) => (
            <label
              key={title}
              className="flex items-start justify-between gap-4 rounded-xl border border-border p-4"
            >
              <span>
                <span className="block text-sm font-medium">{title}</span>
                <span className="block text-sm text-muted-foreground">{body}</span>
              </span>
              <Switch defaultChecked={index === 0} />
            </label>
          ))}
        </TabsContent>
      </Tabs>
    </>
  );
}
