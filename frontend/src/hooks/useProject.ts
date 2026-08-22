import { useQuery } from "@tanstack/react-query";
import { apiClient, API_ROUTES, getAccessToken } from "@/services/apiClient";
import type { Repository } from "@/types";

export function useProject(id: string) {
  const token = getAccessToken();

  return useQuery({
    queryKey: ["project", id],
    queryFn: async (): Promise<Repository> => {
      const response = await apiClient.get(API_ROUTES.repository(id));
      return response.data;
    },
    // Only fires client-side; SSR returns null token -> disabled.
    enabled: !!token && !!id,
    staleTime: 60_000,
    retry: false,
  });
}
