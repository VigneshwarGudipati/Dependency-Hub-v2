import { Link } from "@tanstack/react-router";
import { Bell, Menu, Moon, Plus, Search, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/hooks/useAuth";

export function AppTopbar({ onOpenNav }: { onOpenNav: () => void }) {
  const { theme, toggle } = useTheme();
  const { data: user } = useAuth();

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur">
      <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 sm:px-6">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          className="grid size-9 place-items-center rounded-lg border border-border lg:hidden"
        >
          <Menu className="size-4" />
        </button>
        <div className="relative hidden min-w-0 md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search repositories, packages or CVEs…"
            aria-label="Global search"
            className="max-w-md pl-9"
          />
        </div>
        <div className="md:hidden" />
        <div className="flex shrink-0 items-center gap-2">
          <Button asChild size="sm" className="hidden sm:inline-flex">
            <Link to="/repositories/new">
              <Plus className="size-4" /> New repository
            </Link>
          </Button>
          <button
            type="button"
            onClick={toggle}
            aria-label="Toggle theme"
            className="grid size-9 place-items-center rounded-lg border border-border hover:bg-muted"
          >
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
          <Link
            to="/audit-logs"
            aria-label="Notifications (Deferred)"
            className="relative grid size-9 place-items-center rounded-lg border border-border hover:bg-muted"
          >
            <Bell className="size-4" />
          </Link>
          <Link
            to="/settings"
            className="flex items-center gap-2 rounded-lg border border-border py-1 pl-1 pr-3 hover:bg-muted"
          >
            <span className="grid size-7 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
              {user?.full_name
                ? user.full_name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .substring(0, 2)
                    .toUpperCase()
                : (user?.username?.substring(0, 2).toUpperCase() ?? "U")}
            </span>
            <span className="hidden text-sm font-medium sm:block">
              {user?.full_name ?? user?.username ?? "User"}
            </span>
          </Link>
        </div>
      </div>
    </header>
  );
}
