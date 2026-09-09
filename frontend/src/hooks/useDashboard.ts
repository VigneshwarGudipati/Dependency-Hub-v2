import { useQuery } from "@tanstack/react-query";
import { apiClient, API_ROUTES, getAccessToken } from "@/services/apiClient";
import type { DashboardSummary } from "@/types";

export function useDashboardSummary(projectId: string | null) {
  const token = getAccessToken();

  return useQuery({
    queryKey: ["dashboard-summary", projectId],
    queryFn: async (): Promise<DashboardSummary> => {
      if (!projectId) throw new Error("Project ID is required");
      const response = await apiClient.get(API_ROUTES.dashboard(projectId));
      return response.data;
    },
    enabled: !!token && !!projectId,
  });
}
