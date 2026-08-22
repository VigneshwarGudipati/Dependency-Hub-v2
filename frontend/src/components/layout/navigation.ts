import {
  Activity,
  BarChart3,
  Boxes,
  FileBarChart,
  FolderGit2,
  LayoutDashboard,
  ScanSearch,
  ScrollText,
  Settings,
  ShieldAlert,
  Share2,
  Users,
} from "lucide-react";

export interface NavItem {
  label: string;
  to: string;
  icon: typeof Activity;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    title: "Overview",
    items: [
      { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
      { label: "Repositories", to: "/repositories", icon: FolderGit2 },
    ],
  },
  {
    title: "Analysis",
    items: [
      { label: "Dependency Scanner", to: "/scanner", icon: ScanSearch },
      { label: "Dependency Graph", to: "/graph", icon: Share2 },
      { label: "Health Analysis", to: "/health-analysis", icon: BarChart3 },
      { label: "Packages", to: "/packages", icon: Boxes },
    ],
  },
  {
    title: "Security",
    items: [
      { label: "Vulnerabilities", to: "/vulnerabilities", icon: ShieldAlert },
      { label: "Reports", to: "/reports", icon: FileBarChart },
      { label: "Audit Logs", to: "/audit-logs", icon: ScrollText },
    ],
  },
  {
    title: "Administration",
    items: [
      { label: "User Management", to: "/users", icon: Users },
      { label: "System Health", to: "/system-health", icon: Activity },
      { label: "Settings", to: "/settings", icon: Settings },
    ],
  },
];
