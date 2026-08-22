import { useQuery } from "@tanstack/react-query";
import { apiClient, API_ROUTES, getAccessToken } from "@/services/apiClient";
import type { Repository } from "@/types";

interface UseProjectsParams {
  search?: string;
  status?: string;
  language?: string;
}

export function useProjects(params: UseProjectsParams = {}) {
  const token = getAccessToken();

  return useQuery({
    queryKey: ["projects", params],
    queryFn: async (): Promise<Repository[]> => {
      const searchParams = new URLSearchParams();
      if (params.search) searchParams.append("search", params.search);
      if (params.status && params.status !== "all") searchParams.append("status", params.status);
      if (params.language && params.language !== "all")
        searchParams.append("language", params.language);

      const qs = searchParams.toString();
      const response = await apiClient.get(
        qs ? `${API_ROUTES.repositories}?${qs}` : API_ROUTES.repositories,
      );
      // Backend returns an array of projects
      return Array.isArray(response.data) ? response.data : [];
    },
    // Only fires client-side after login; SSR returns null token -> query is disabled.
    enabled: !!token,
    staleTime: 60_000,
  });
}
