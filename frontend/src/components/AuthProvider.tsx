"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  getToken,
  getUser,
  setAuth,
  clearAuth,
} from "@/lib/auth";
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
      // Small delay to let callback page store token first
      await new Promise((r) => setTimeout(r, 100));

      const token = getToken();
      if (!token) {
        setLoading(false);
        if (pathname !== "/login" && !pathname.startsWith("/auth/callback")) {
          router.push("/login");
        }
        return;
      }

      try {
        const me = await api.getMe();
        setUser(me);
        setAuth(token, me);
      } catch (error: any) {
        const status = error?.response?.status;
        if (status === 401) {
          clearAuth();
          setUser(null);
          if (pathname !== "/login" && !pathname.startsWith("/auth/callback")) {
            router.push("/login");
          }
        } else {
          // Preserve the cached session on transient timeouts/5xx so a busy backend
          // doesn't look like a real logout during refresh.
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
