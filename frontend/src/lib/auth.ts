// The JWT now lives in an httpOnly cookie that JavaScript cannot read, so the
// browser sends it automatically and an XSS payload can't steal it. We only
// cache the non-sensitive user profile here for a fast initial render; the
// source of truth for auth is the cookie + GET /auth/me.

const USER_KEY = "commitgraph_user";

export function getUser(): any | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setUser(user: any): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(USER_KEY);
}
