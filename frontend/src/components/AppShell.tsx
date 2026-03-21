"use client";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  if (pathname === "/login" || pathname.startsWith("/auth/callback")) {
    return <>{children}</>;
  }

  if (pathname === "/privacy" || pathname === "/terms") {
    return (
      <div className="min-h-screen p-8">
        {children}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col h-screen overflow-y-auto">
        <TopBar />
        <main className="flex-1 p-4 md:p-8 pb-20 md:pb-8">{children}</main>
      </div>
    </div>
  );
}