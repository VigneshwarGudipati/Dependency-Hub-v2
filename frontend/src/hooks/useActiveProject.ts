import { useEffect, useState } from "react";
import { useProjects } from "./useProjects";

const ACTIVE_PROJECT_KEY = "dh_active_project_id";

export function useActiveProject() {
  const { data: projects, isLoading, error } = useProjects();
  const [activeProjectId, setActiveProjectIdState] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return window.localStorage.getItem(ACTIVE_PROJECT_KEY);
    }
    return null;
  });

  const setActiveProject = (id: string) => {
    setActiveProjectIdState(id);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ACTIVE_PROJECT_KEY, id);
    }
  };

  useEffect(() => {
    if (!isLoading && projects && projects.length > 0) {
      // Validate that the stored project exists in the current project list
      const isValid = activeProjectId && projects.some((p) => p.id === activeProjectId);
      
      if (!isValid) {
        // Fallback to first available project ONLY when no active valid project exists
        const firstId = projects[0].id;
        setActiveProjectIdState(firstId);
        if (typeof window !== "undefined") {
          window.localStorage.setItem(ACTIVE_PROJECT_KEY, firstId);
        }
      }
    } else if (!isLoading && projects && projects.length === 0) {
      setActiveProjectIdState(null);
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(ACTIVE_PROJECT_KEY);
      }
    }
  }, [projects, isLoading, activeProjectId]);

  const activeProject = projects?.find((p) => p.id === activeProjectId) || null;

  return {
    activeProjectId,
    activeProject,
    setActiveProject,
    projects,
    isLoading,
    error,
  };
}
