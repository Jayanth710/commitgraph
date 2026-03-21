import axios from "axios";
import { getToken, clearAuth } from "@/lib/auth";

const client = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  timeout: 10000,
});

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
    if (error.response?.status === 401 && typeof window !== "undefined") {
      clearAuth();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export const api = {
  // Auth
  signup: (body: { firstname?: string; lastname?: string; email: string; password: string }) =>
    client.post("/auth/signup", body).then((r) => r.data),
  login: (body: { email: string; password: string }) =>
    client.post("/auth/login", body).then((r) => r.data),
  googleLogin: (body: { email: string; name?: string; avatar_url?: string }) =>
    client.post("/auth/google-login", body).then((r) => r.data),
  getMe: () => client.get("/auth/me").then((r) => r.data),

  // Dashboard
  getStats: () => client.get("/api/stats").then((r) => r.data),
  getCommitments: (params?: string) => client.get(`/api/commitments${params ? `?${params}` : ""}`).then((r) => r.data),
  getCommitment: (id: string) => client.get(`/api/commitments/${id}`).then((r) => r.data),
  reorderCommitments: (order: { id: string; priority: number }[]) =>
    client.patch("/api/commitments/reorder", { order }).then((r) => r.data),
  updateCommitment: (id: string, body: any) => client.patch(`/api/commitments/${id}`, body).then((r) => r.data),
  searchCommitments: (params: string) => client.get(`/api/commitments/search?${params}`).then((r) => r.data),
  getReviewQueue: () => client.get("/api/review-queue").then((r) => r.data),
  reviewAction: (id: string, action: string) => client.patch(`/api/review-queue/${id}`, { action }).then((r) => r.data),
  getTimeline: (params?: string) => client.get(`/api/timeline${params ? `?${params}` : ""}`).then((r) => r.data),
  getPersons: () => client.get("/api/persons").then((r) => r.data),
  getAccounts: () => client.get("/api/accounts").then((r) => r.data),
  disconnectAccount: (id: string) => client.delete(`/api/accounts/${id}`).then((r) => r.data),
  deleteUser: () => client.delete("/auth/me").then((r) => r.data),
  getChartData: () => client.get("/api/stats/chart").then((r) => r.data),
  getWeeklyDigest: () => client.get("/api/digest/weekly").then((r) => r.data),
  sendEmail: (body: { to: string; subject: string; body: string; thread_id?: string; in_reply_to?: string; account_email: string }) =>
    client.post("/api/email/send", body).then((r) => r.data),
  startGmailWatch: (email: string) => client.post(`/gmail/watch/start?email_address=${email}`).then((r) => r.data),
  createCalendarEvent: (commitmentId: string) =>
    client.post(`/api/commitments/${commitmentId}/calendar-event`).then((r) => r.data),
};