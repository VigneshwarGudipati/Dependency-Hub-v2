import axios from "axios";

/**
 * API-ready axios instance. Set VITE_API_BASE_URL to point at the FastAPI backend.
 */
export const apiClient = axios.create({
  baseURL: import.meta.env["VITE_API_BASE_URL"] ?? "/api",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

// --- Token helpers ---

const TOKEN_KEY = "dh_token";
const REFRESH_KEY = "dh_refresh_token";

export function setTokens(access: string, refresh: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

// --- Request interceptor: attach access token ---

apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = getAccessToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- Response interceptor: auto-refresh on 401 ---

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((prom) => {
    if (token) prom.resolve(token);
    else prom.reject(error);
  });
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Only attempt refresh for 401 errors, not on auth endpoints themselves
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/login") &&
      !originalRequest.url?.includes("/auth/register") &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        clearTokens();
        isRefreshing = false;
        return Promise.reject(error);
      }

      try {
        const resp = await apiClient.post("/auth/refresh", {
          refresh_token: refreshToken,
        });
        const { access_token, refresh_token: newRefresh } = resp.data;
        setTokens(access_token, newRefresh);
        processQueue(null, access_token);
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearTokens();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

export const API_ROUTES = {
  login: "/auth/login",
  register: "/auth/register",
  refresh: "/auth/refresh",
  logout: "/auth/logout",
  me: "/auth/me",
  verifyOtp: "/auth/verify-otp",
  forgotPassword: "/auth/forgot-password",
  dashboard: "/dashboard/summary",
  repositories: "/projects",
  repository: (id: string) => `/projects/${id}`,
  scan: (id: string) => `/projects/${id}/scans`,
  graph: (id: string) => `/projects/${id}/graph`,
  vulnerabilities: "/vulnerabilities",
  packages: "/dependencies",
  package: (id: string) => `/dependencies/${id}`,
  reports: "/reports",
  users: "/members",
  systemHealth: "/system/health",
  auditLogs: "/audit-logs",
} as const;
