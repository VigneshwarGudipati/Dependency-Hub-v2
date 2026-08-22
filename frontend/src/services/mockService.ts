import {
  activity,
  auditLogs,
  dashboardSummary,
  graphEdges,
  graphNodes,
  packages,
  reports,
  repositories,
  scanRecommendations,
  systemMetrics,
  users,
  vulnerabilities,
} from "@/data/mockData";
import type {
  ActivityItem,
  AppUser,
  AuditLog,
  DashboardSummary,
  DependencyPackage,
  GraphEdge,
  GraphNode,
  ReportItem,
  Repository,
  ScanResult,
  SystemMetric,
  Vulnerability,
} from "@/types";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Simulates a network round trip so loading states are exercised. */
async function resolve<T>(payload: T, ms = 600): Promise<T> {
  await delay(ms);
  return payload;
}

let createdRepositories: Repository[] = [];

export const mockService = {
  getDashboard: (): Promise<DashboardSummary> => resolve(dashboardSummary, 700),
  getActivity: (): Promise<ActivityItem[]> => resolve(activity, 400),
  getRepositories: (): Promise<Repository[]> =>
    resolve([...createdRepositories, ...repositories], 650),
  getRepository: async (id: string): Promise<Repository | undefined> => {
    const all = [...createdRepositories, ...repositories];
    return resolve(
      all.find((repo) => repo.id === id || repo.name === id),
      500,
    );
  },
  createRepository: async (
    input: Pick<Repository, "name" | "description" | "language" | "visibility" | "branch">,
  ): Promise<Repository> => {
    await delay(900);
    const created: Repository = {
      ...input,
      id: `repo-${Math.random().toString(36).slice(2, 8)}`,
      owner: "Platform Team",
      healthScore: 90,
      dependencies: 0,
      vulnerabilities: 0,
      outdated: 0,
      lastScan: new Date().toISOString(),
      createdAt: new Date().toISOString(),
      status: "healthy",
    };
    createdRepositories = [created, ...createdRepositories];
    return created;
  },
  getPackages: (): Promise<DependencyPackage[]> => resolve(packages, 600),
  getPackage: (id: string): Promise<DependencyPackage | undefined> =>
    resolve(
      packages.find((pkg) => pkg.id === id || pkg.name === id),
      450,
    ),
  getVulnerabilities: (): Promise<Vulnerability[]> => resolve(vulnerabilities, 650),
  getGraph: (): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> =>
    resolve({ nodes: graphNodes, edges: graphEdges }, 700),
  getReports: (): Promise<ReportItem[]> => resolve(reports, 550),
  getUsers: (): Promise<AppUser[]> => resolve(users, 550),
  getSystemMetrics: (): Promise<SystemMetric[]> => resolve(systemMetrics, 600),
  getAuditLogs: (): Promise<AuditLog[]> => resolve(auditLogs, 600),
  runScan: async (repository: string): Promise<ScanResult> => {
    await delay(400);
    const safe = packages.filter((p) => p.status === "safe").length;
    const outdated = packages.filter((p) => p.status === "outdated").length;
    const vulnerable = packages.filter((p) => p.status === "vulnerable").length;
    return {
      repository,
      healthScore: Math.round(
        packages.reduce((sum, p) => sum + p.healthScore, 0) / packages.length,
      ),
      total: packages.length,
      safe,
      outdated,
      vulnerable,
      packages,
      recommendations: scanRecommendations,
    };
  },
};
