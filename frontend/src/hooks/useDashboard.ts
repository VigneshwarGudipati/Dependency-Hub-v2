import { useQuery } from "@tanstack/react-query";
import { apiClient, API_ROUTES, getAccessToken } from "@/services/apiClient";
import type { DashboardSummary } from "@/types";

export function useDashboardSummary() {
  const token = getAccessToken();

  return useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: async (): Promise<DashboardSummary> => {
      const response = await apiClient.get(API_ROUTES.dashboard);
      return response.data;
    },
    enabled: !!token,
  });
}
