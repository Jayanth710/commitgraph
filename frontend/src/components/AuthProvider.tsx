"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getUser, setUser as cacheUser, clearAuth } from "@/lib/auth";
import { api } from "@/lib/api";

type AuthContextType = {
  user: any | null;
  loading: boolean;
  login: (user: any) => void;
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
      try {
        // The auth cookie (if present) authenticates this request.
        const me = await api.getMe();
        setUser(me);
        cacheUser(me);
      } catch (error: any) {
        const status = error?.response?.status;
        if (status === 401) {
          clearAuth();
          setUser(null);
          if (pathname !== "/login" && !pathname.startsWith("/auth/callback")) {
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

  const login = (userData: any) => {
    // The backend already set the httpOnly auth cookie on the login response.
    cacheUser(userData);
    setUser(userData);
    router.push("/");
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Even if the network call fails, clear local state below.
    }
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
