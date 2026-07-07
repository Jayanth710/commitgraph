"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getToken, getUser, setAuth, clearAuth, isPublicPath } from "@/lib/auth";
import { api } from "@/lib/api";

type AuthContextType = {
  user: any | null;
  loading: boolean;
  login: (token: string, user: any) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: () => {},
  logout: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<any | null>(getUser());
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    async function checkAuth() {
      // Let the OAuth callback page store its token first.
      await new Promise((r) => setTimeout(r, 100));

      const token = getToken();
      if (!token) {
        setLoading(false);
        // No token: only bounce to /login on protected routes. Public routes
        // (the landing "/", /login, /privacy, /terms, /auth/callback) stay put
        // so the marketing landing can render for logged-out visitors.
        if (!isPublicPath(pathname)) {
          router.push("/login");
        }
        return;
      }

      try {
        // The Bearer token (attached by lib/api.ts) authenticates this request.
        const me = await api.getMe();
        setUser(me);
        setAuth(token, me);
      } catch (error: any) {
        const status = error?.response?.status;
        if (status === 401) {
          clearAuth();
          setUser(null);
          if (!isPublicPath(pathname)) {
            router.push("/login");
          }
        } else {
          // Preserve the cached session on transient timeouts/5xx so a busy
          // backend doesn't look like a real logout during refresh.
          setUser((prev: any | null) => prev ?? getUser());
          console.error("Auth check failed without a 401; preserving session", error);
        }
      } finally {
        setLoading(false);
      }
    }
    checkAuth();
  }, [pathname, router]);

  const login = (token: string, userData: any) => {
    setAuth(token, userData);
    setUser(userData);
    router.push("/");
  };

  const logout = () => {
    clearAuth();
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
