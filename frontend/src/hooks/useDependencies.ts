import { useQuery } from "@tanstack/react-query";
import { apiClient, API_ROUTES, getAccessToken } from "@/services/apiClient";
import type { DependencyPackage, PaginatedResponse } from "@/types";

interface UseDependenciesParams {
  page?: number;
  pageSize?: number;
  query?: string;
  status?: string;
  projectId?: string;
}

export function useDependencies(params: UseDependenciesParams) {
  const token = getAccessToken();

  return useQuery({
    queryKey: ["dependencies", params],
    queryFn: async (): Promise<PaginatedResponse<DependencyPackage>> => {
      const { page = 1, pageSize = 25, query, status, projectId } = params;

      const searchParams = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      });

      if (query) searchParams.append("query", query);
      if (status && status !== "all") searchParams.append("status", status);
      if (projectId) searchParams.append("project_id", projectId);

      const response = await apiClient.get(`${API_ROUTES.packages}?${searchParams.toString()}`);
      return response.data;
    },
    enabled: !!token,
  });
}

export function useDependency(id: string) {
  const token = getAccessToken();

  return useQuery({
    queryKey: ["dependency", id],
    queryFn: async (): Promise<DependencyPackage> => {
      const response = await apiClient.get(API_ROUTES.package(id));
      return response.data;
    },
    enabled: !!token && !!id,
  });
}
