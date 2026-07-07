import axios from "axios";
import { getToken, clearAuth, isPublicPath } from "@/lib/auth";
import type {
  CalendarEventsResponse,
  CommitmentDetailResponse,
  CommitmentListResponse,
  DailyBriefListResponse,
  DailyBriefRun,
  JobApplicationDetailResponse,
  JobApplicationListResponse,
  ReviewQueueResponse,
} from "@/lib/types";

const client = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

// Attach the JWT (from localStorage) as a Bearer header on every request. A
// header is sent cross-site with no cookie or proxy, so Vercel <-> Cloud Run
// works directly.
client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    // Redirect on 401 — but never on public paths (landing "/", /login, /privacy,
    // /terms, OAuth callback). Otherwise the logged-out /auth/me probe would hard
    // redirect the marketing landing straight to /login.
    if (error.response?.status === 401 && typeof window !== "undefined") {
      const path = window.location.pathname;
      if (!isPublicPath(path)) {
        clearAuth();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export const api = {
  signup: (body: { firstname?: string; lastname?: string; email: string; password: string }) =>
    client.post("/auth/signup", body).then((r) => r.data),
  login: (body: { email: string; password: string }) =>
    client.post("/auth/login", body).then((r) => r.data),
  googleLogin: (body: { email: string; name?: string; avatar_url?: string }) =>
    client.post("/auth/google-login", body).then((r) => r.data),
  logout: () => client.post("/auth/logout").then((r) => r.data),
  getMe: () => client.get("/auth/me").then((r) => r.data),

    getStats: (params?: string) =>
    client.get(`/api/stats${params ? `?${params}` : ""}`).then((r) => r.data),
  getCommitments: (params?: string): Promise<CommitmentListResponse> =>
    client.get(`/api/commitments${params ? `?${params}` : ""}`).then((r) => r.data),
  getCommitment: (id: string): Promise<CommitmentDetailResponse> =>
    client.get(`/api/commitments/${id}`).then((r) => r.data),
  reorderCommitments: (order: { id: string; priority: number }[]) =>
    client.patch("/api/commitments/reorder", { order }).then((r) => r.data),
  updateCommitment: (id: string, body: Record<string, unknown>) =>
    client.patch(`/api/commitments/${id}`, body).then((r) => r.data),
  mergeCommitment: (id: string, targetCommitmentId: string) =>
    client.post(`/api/commitments/${id}/merge`, {
      target_commitment_id: targetCommitmentId,
    }).then((r) => r.data),
  searchCommitments: (params: string): Promise<CommitmentListResponse> =>
    client.get(`/api/commitments/search?${params}`).then((r) => r.data),

  getReviewQueue: (params?: string): Promise<ReviewQueueResponse> =>
    client.get(`/api/review-queue${params ? `?${params}` : ""}`).then((r) => r.data),
  reviewAction: (id: string, body: Record<string, unknown>) =>
    client.patch(`/api/review-queue/${id}`, body).then((r) => r.data),

  getTimeline: (params?: string) =>
    client.get(`/api/timeline${params ? `?${params}` : ""}`).then((r) => r.data),
  getPersons: (params?: string) =>
    client.get(`/api/persons${params ? `?${params}` : ""}`).then((r) => r.data),
  getAccounts: () => client.get("/api/accounts").then((r) => r.data),
  disconnectAccount: (id: string) => client.delete(`/api/accounts/${id}`).then((r) => r.data),
  deleteUser: () => client.delete("/auth/me").then((r) => r.data),
  getChartData: (params?: string) =>
    client.get(`/api/stats/chart${params ? `?${params}` : ""}`).then((r) => r.data),
  getWeeklyDigest: (params?: string) =>
    client.get(`/api/digest/weekly${params ? `?${params}` : ""}`).then((r) => r.data),
  getDailyBriefs: (params?: string): Promise<DailyBriefListResponse> =>
    client.get(`/api/daily-briefs${params ? `?${params}` : ""}`).then((r) => r.data),
  getLatestDailyBrief: (params: string): Promise<{ run: DailyBriefRun | null }> =>
    client.get(`/api/daily-briefs/latest?${params}`).then((r) => r.data),
  getDailyBrief: (id: string): Promise<{ run: DailyBriefRun }> =>
    client.get(`/api/daily-briefs/${id}`).then((r) => r.data),
  generateDailyBrief: (body: { brief_type: "morning" | "night"; account_id?: string | null; brief_date?: string }) =>
    client.post("/api/daily-briefs/generate", body).then((r) => r.data),
  getBriefDeliveryPreferences: () =>
    client.get("/api/brief-delivery/preferences").then((r) => r.data),
  updateBriefDeliveryPreferences: (body: Record<string, unknown>) =>
    client.put("/api/brief-delivery/preferences", body).then((r) => r.data),
  getBriefDeliveryRuns: () =>
    client.get("/api/brief-delivery/runs").then((r) => r.data),
  sendBriefNow: (body: { brief_type: "morning" | "night"; brief_date?: string; force?: boolean }) =>
    client.post("/api/brief-delivery/send-now", body).then((r) => r.data),
  getJobApplications: (params?: string): Promise<JobApplicationListResponse> =>
    client.get(`/api/job-applications${params ? `?${params}` : ""}`).then((r) => r.data),
  getJobApplication: (id: string): Promise<JobApplicationDetailResponse> =>
    client.get(`/api/job-applications/${id}`).then((r) => r.data),
  updateJobApplication: (id: string, body: Record<string, unknown>) =>
    client.patch(`/api/job-applications/${id}`, body).then((r) => r.data),
  deleteJobApplication: (id: string) =>
    client.delete(`/api/job-applications/${id}`).then((r) => r.data),
  
  sendEmail: (body: { to: string; subject: string; body: string; thread_id?: string; in_reply_to?: string; account_email: string }) =>
    client.post("/api/email/send", body).then((r) => r.data),
  startGmailWatch: (email: string) =>
    client.post(`/gmail/watch/start?email_address=${email}`).then((r) => r.data),
  getCalendarEvents: (params?: string): Promise<CalendarEventsResponse> =>
    client.get(`/api/calendar/events${params ? `?${params}` : ""}`).then((r) => r.data),
  syncCalendar: (params?: string) =>
    client.post(`/api/calendar/sync${params ? `?${params}` : ""}`).then((r) => r.data),
  createCalendarEvent: (commitmentId: string, dueDate?: string) =>
    client
      .post(
        `/api/commitments/${commitmentId}/calendar-event`,
        dueDate ? { due_date: dueDate } : {},
      )
      .then((r) => r.data),
  deleteCalendarEvent: (commitmentId: string) =>
    client.delete(`/api/commitments/${commitmentId}/calendar-event`).then((r) => r.data),
};
