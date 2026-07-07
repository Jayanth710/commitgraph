// The JWT is stored in localStorage and sent as an `Authorization: Bearer`
// header on every API request (see lib/api.ts). A header is sent cross-site with
// no restrictions, so the Vercel frontend and Cloud Run backend work directly —
// no cookies, no proxy.

const TOKEN_KEY = "commitgraph_token";
const USER_KEY = "commitgraph_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): any | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setAuth(token: string, user: any): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// Routes viewable while logged out. With no token we must NOT redirect away from
// these — the marketing landing lives at "/", so a logged-out visitor there
// should see the landing page, not get bounced to /login.
export const PUBLIC_PATHS = ["/", "/login", "/privacy", "/terms"];

export function isPublicPath(path: string): boolean {
  return PUBLIC_PATHS.includes(path) || path.startsWith("/auth/callback");
}
