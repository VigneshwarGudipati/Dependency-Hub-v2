import { createFileRoute, redirect } from "@tanstack/react-router";
import { AppLayout } from "@/components/layout/AppLayout";
import { getAccessToken } from "@/services/apiClient";

export const Route = createFileRoute("/_shell")({
  beforeLoad: () => {
    // Protect the entire shell subtree. If no access token exists in localStorage,
    // redirect to login immediately — prevents infinite skeleton states for
    // unauthenticated users hitting any protected route directly.
    if (!getAccessToken()) {
      throw redirect({ to: "/login", replace: true });
    }
  },
  component: AppLayout,
});
