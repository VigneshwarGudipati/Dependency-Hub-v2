import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient, API_ROUTES, getAccessToken, clearTokens } from "@/services/apiClient";
import { useNavigate } from "@tanstack/react-router";

export interface OrganizationInfo {
  id: string;
  name: string;
  slug: string;
}

export interface User {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  is_active: boolean;
  organization?: OrganizationInfo;
  role?: string;
}

export function useAuth() {
  const navigate = useNavigate();
  const token = getAccessToken();

  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async (): Promise<User> => {
      const response = await apiClient.get(API_ROUTES.me);
      return response.data;
    },
    enabled: !!token,
    retry: false,
    staleTime: 60_000,
  });

  // Side effects must be in useEffect — never in the render body.
  // Calling navigate() or clearTokens() directly during render violates
  // Rules of Hooks and causes navigation storms during hydration.
  useEffect(() => {
    if (query.isError) {
      clearTokens();
      navigate({ to: "/login", replace: true });
    }
  }, [query.isError, navigate]);

  return query;
}
