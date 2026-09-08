import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, API_ROUTES, getAccessToken } from "@/services/apiClient";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ReportType =
  "SECURITY_REPORT" | "PACKAGE_REPORT" | "EXECUTIVE_REPORT" | "COMPLIANCE_REPORT";

export type ReportFormat = "JSON" | "HTML" | "PDF" | "CSV" | "SARIF";

export type ReportStatus = "QUEUED" | "GENERATING" | "COMPLETED" | "FAILED" | "EXPIRED" | "DELETED";

export interface ScanSummary {
  id: string;
  project_id: string;
  artifact_id: string;
  status: string;
  scan_type: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  total_dependencies: number | null;
  vulnerable_dependencies: number | null;
}

export interface Report {
  id: string;
  project_id: string;
  scan_id: string;
  report_type: ReportType;
  status: ReportStatus;
  created_at: string;
  created_by: string;
  // present in detail response
  completed_at?: string | null;
  expires_at?: string | null;
}

export interface GenerateReportPayload {
  scan_id: string;
  report_type: ReportType;
  format: ReportFormat;
}

// ---------------------------------------------------------------------------
// Scans for a project
// ---------------------------------------------------------------------------

export function useProjectScans(projectId: string | null) {
  const token = getAccessToken();

  return useQuery<ScanSummary[]>({
    queryKey: ["scans", projectId],
    queryFn: async () => {
      if (!projectId) return [];
      const res = await apiClient.get(API_ROUTES.scans(projectId));
      return Array.isArray(res.data) ? res.data : [];
    },
    enabled: !!token && !!projectId,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Reports list for a project
// ---------------------------------------------------------------------------

export function useProjectReports(projectId: string | null) {
  const token = getAccessToken();

  return useQuery<Report[]>({
    queryKey: ["reports", projectId],
    queryFn: async () => {
      if (!projectId) return [];
      const res = await apiClient.get(API_ROUTES.projectReports(projectId));
      return Array.isArray(res.data) ? res.data : [];
    },
    enabled: !!token && !!projectId,
    staleTime: 10_000,
    // Poll every 5 s only while at least one report is actively generating.
    refetchInterval: (query) => {
      const data = query.state.data as Report[] | undefined;
      if (!data) return false;
      const hasActive = data.some((r) => r.status === "QUEUED" || r.status === "GENERATING");
      return hasActive ? 5_000 : false;
    },
  });
}

// ---------------------------------------------------------------------------
// Generate report mutation
// ---------------------------------------------------------------------------

export function useGenerateReport(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation<Report, Error, GenerateReportPayload>({
    mutationFn: async (payload) => {
      const res = await apiClient.post(API_ROUTES.projectReports(projectId), payload);
      return res.data as Report;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reports", projectId] });
    },
  });
}

// ---------------------------------------------------------------------------
// Retry report mutation
// ---------------------------------------------------------------------------

export function useRetryReport(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation<Report, Error, string>({
    mutationFn: async (reportId) => {
      const res = await apiClient.post(API_ROUTES.projectReportRetry(projectId, reportId));
      return res.data as Report;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reports", projectId] });
    },
  });
}

// ---------------------------------------------------------------------------
// Delete report mutation
// ---------------------------------------------------------------------------

export function useDeleteReport(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: async (reportId) => {
      await apiClient.delete(API_ROUTES.projectReport(projectId, reportId));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reports", projectId] });
    },
  });
}

// ---------------------------------------------------------------------------
// Download helper (browser-native flow, preserves server filename)
// ---------------------------------------------------------------------------

export async function downloadReport(projectId: string, reportId: string): Promise<void> {
  // Use apiClient so:
  //  - baseURL respects VITE_API_BASE_URL (no hardcoded "/api/v1")
  //  - the 401 auto-refresh interceptor fires automatically
  //  - auth token is attached by the request interceptor
  const response = await apiClient.get(API_ROUTES.projectReportDownload(projectId, reportId), {
    responseType: "blob",
  });

  // Axios surfaces Content-Disposition from response.headers (lowercased)
  const disposition: string = response.headers["content-disposition"] ?? "";
  const filenameMatch = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
  const filename = filenameMatch?.[1]?.replace(/['"]/g, "") ?? `report-${reportId}`;

  const objectUrl = URL.createObjectURL(response.data as Blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
}
