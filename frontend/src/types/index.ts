export type Severity = "critical" | "high" | "medium" | "low";
export type PackageStatus = "safe" | "outdated" | "vulnerable";
export type UserRole = "Admin" | "Security Lead" | "Developer" | "Viewer";
export type UserStatus = "active" | "invited" | "suspended";

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface Repository {
  id: string;
  name: string;
  description: string;
  language: string;
  visibility: "private" | "public";
  branch: string;
  owner: string;
  healthScore: number;
  dependencies: number;
  vulnerabilities: number;
  outdated: number;
  lastScan: string;
  createdAt: string;
  status: "healthy" | "at-risk" | "critical";
}

export interface Vulnerability {
  id: string;
  cve: string;
  packageName: string;
  severity: Severity;
  source: string;
  cvss: number;
  title: string;
  description: string;
  recommendation: string;
  affectedVersions: string;
  patchedVersion: string;
  publishedAt: string;
  repository: string;
}

export interface DependencyPackage {
  id: string;
  name: string;
  installedVersion: string;
  latestVersion: string | null;
  status: PackageStatus;
  severity: Severity | null;
  cve: string | null;
  license: string;
  outdated: "TRUE" | "FALSE" | "UNKNOWN" | null;
  publishedAt: string | null;
  registrySource: string | null;
  registryStatus: string | null;
  weeklyDownloads: number;
  maintainers: number;
  lastPublished: string;
  size: string;
  description: string;
  recommendation: string;
  healthScore: number;
  dependents: string[];
  repository: string;
  direct: boolean;
}

export interface GraphNode {
  id: string;
  label: string;
  status: PackageStatus;
  x: number;
  y: number;
  depth: number;
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface ActivityItem {
  id: string;
  type: "scan" | "repo" | "user" | "vuln" | "report";
  message: string;
  actor: string;
  timestamp: string;
}

export interface AuditLog {
  id: string;
  category: "login" | "repository" | "scan" | "settings";
  action: string;
  actor: string;
  ip: string;
  target: string;
  result: "success" | "failed";
  timestamp: string;
}

export interface AppUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  team: string;
  lastActive: string;
  avatarColor: string;
}

export interface ReportItem {
  id: string;
  name: string;
  type: "Security" | "Compliance" | "Health" | "License";
  repository: string;
  createdAt: string;
  size: string;
  format: "PDF" | "CSV";
  status: "ready" | "generating" | "failed";
}

export interface SeriesPoint {
  label: string;
  value: number;
  secondary?: number;
}

export interface SystemMetric {
  id: string;
  label: string;
  value: number;
  unit: string;
  status: "operational" | "degraded" | "down";
  history: SeriesPoint[];
}

export interface DashboardSummary {
  healthScore: number | null;
  totalDependencies: number;
  safePackages: number;
  vulnerablePackages: number;
  outdatedPackages: number;
  scansThisWeek: number;
  meanTimeToPatch: string;
  trend: SeriesPoint[];
  severityBreakdown: SeriesPoint[];
  ecosystemBreakdown: SeriesPoint[];
  activity: ActivityItem[];
}

export interface ScanStep {
  id: string;
  label: string;
  detail: string;
}

export interface ScanResult {
  repository: string;
  healthScore: number;
  total: number;
  safe: number;
  outdated: number;
  vulnerable: number;
  packages: DependencyPackage[];
  recommendations: string[];
}
