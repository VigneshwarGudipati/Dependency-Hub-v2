import { useQuery } from "@tanstack/react-query";
import { apiClient, API_ROUTES, getAccessToken } from "@/services/apiClient";
import type { PaginatedResponse, Vulnerability } from "@/types";

interface UseVulnerabilitiesParams {
  page?: number;
  pageSize?: number;
  query?: string;
  severity?: string;
  projectId?: string;
}

export function useVulnerabilities(params: UseVulnerabilitiesParams) {
  const token = getAccessToken();

  return useQuery({
    queryKey: ["vulnerabilities", params],
    queryFn: async (): Promise<PaginatedResponse<Vulnerability>> => {
      const { page = 1, pageSize = 25, query, severity, projectId } = params;

      const searchParams = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      });

      if (query) searchParams.append("query", query);
      if (severity && severity !== "all") searchParams.append("severity", severity);
      if (projectId) searchParams.append("project_id", projectId);

      const response = await apiClient.get(
        `${API_ROUTES.vulnerabilities}?${searchParams.toString()}`,
      );
      return response.data;
    },
    enabled: !!token,
  });
}
