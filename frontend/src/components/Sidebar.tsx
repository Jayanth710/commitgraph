"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import {
  LayoutDashboard, CheckCircle, AlertTriangle, Clock,
  Users, Settings, Waypoints, Menu, X, CalendarDays, FileText, Briefcase, Sunrise
} from "lucide-react";

// Add after Calendar:

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const [account, setAccount] = useState<any>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [badges, setBadges] = useState<Record<string, number>>({});

useEffect(() => {
    async function load() {
      try {
        const [accountsData, statsData] = await Promise.all([
          api.getAccounts(),
          api.getStats(),
        ]);
        const primary = accountsData.accounts?.find((a: any) => a.provider === "gmail") || accountsData.accounts?.[0];
        setAccount(primary);
        setBadges({
          "/": statsData.overdue_count || 0,
          "/commitments": statsData.open_count || 0,
          "/review": statsData.review_queue_count || 0,
        });
      } catch (err) {
        console.error(err);
      }
    }
    load();

    const refreshBadges = async () => {
      try {
        const stats = await api.getStats();
        setBadges({
          "/": stats.overdue_count || 0,
          "/commitments": stats.open_count || 0,
          "/review": stats.review_queue_count || 0,
        });
      } catch {}
    };

    // Refresh badges every 60 seconds
    const interval = setInterval(refreshBadges, 60000);

    // Refresh badges when commitments change
    window.addEventListener("commitgraph:refresh", refreshBadges);

    return () => {
      clearInterval(interval);
      window.removeEventListener("commitgraph:refresh", refreshBadges);
    };
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const displayName = user?.name || user?.email || account?.email_address || "Not connected";
  const displayEmail = user?.email || account?.email_address || "";
  const initials = (user?.name || user?.email || "?")
    .split(" ")
    .map((w: string) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const links = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard, badgeKey: "/" as string, badgeColor: "bg-red-500" },
    { href: "/commitments", label: "Commitments", icon: CheckCircle, badgeKey: "/commitments", badgeColor: "bg-blue-500" },
    { href: "/review", label: "Review Queue", icon: AlertTriangle, badgeKey: "/review", badgeColor: "bg-amber-500" },
    { href: "/timeline", label: "Timeline", icon: Clock, badgeKey: "", badgeColor: "" },
    { href: "/persons", label: "People", icon: Users, badgeKey: "", badgeColor: "" },
    { href: "/calendar", label: "Calendar", icon: CalendarDays, badgeKey: "", badgeColor: "" },
    { href: "/briefs", label: "Daily Briefs", icon: Sunrise, badgeKey: "", badgeColor: "" },
    { href: "/digest", label: "Weekly Digest", icon: FileText, badgeKey: "", badgeColor: "" },
    { href: "/applications", label: "Applications", icon: Briefcase, badgeKey: "", badgeColor: "" },
    { href: "/settings", label: "Settings", icon: Settings, badgeKey: "", badgeColor: "" },
  ];

  const sidebarContent = (
    <>
      <div className="flex items-center gap-3 px-3 py-3 mb-2">
        <Waypoints size={22} className="text-blue-600 dark:text-blue-400 shrink-0" />
        <span className="text-sm font-bold text-gray-900 dark:text-gray-100 whitespace-nowrap md:opacity-0 md:group-hover:opacity-100 md:transition-opacity md:duration-300">
          Commit<span className="text-blue-600 dark:text-blue-400">Graph</span>
        </span>
      </div>

      <div className="flex flex-col gap-1 flex-1">
        {links.map(({ href, label, icon: Icon, badgeKey, badgeColor }) => {
          const isActive = pathname === href;
          const badgeCount = badgeKey ? (badges[badgeKey] || 0) : 0;

          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors whitespace-nowrap relative ${
                isActive
                  ? "bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-400 font-medium"
                  : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
            >
              <div className="relative shrink-0">
                <Icon size={20} />
                {badgeCount > 0 && (
                  <span className={`absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 rounded-full ${badgeColor} text-white text-[10px] font-bold flex items-center justify-center`}>
                    {badgeCount > 99 ? "99+" : badgeCount}
                  </span>
                )}
              </div>
              <span className="md:opacity-0 md:group-hover:opacity-100 md:transition-opacity md:duration-300 flex-1">
                {label}
              </span>
              {/* Badge text (visible when expanded) */}
              {badgeCount > 0 && (
                <span className={`md:opacity-0 md:group-hover:opacity-100 md:transition-opacity md:duration-300 text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${badgeColor} text-white`}>
                  {badgeCount}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      <div className="border-t border-gray-200 dark:border-gray-800 pt-3 mt-3">
        <div className="flex items-center gap-3 px-2 py-2">
          <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 flex items-center justify-center text-xs font-semibold shrink-0">
            {initials}
          </div>
          <div className="md:opacity-0 md:group-hover:opacity-100 md:transition-opacity md:duration-300 min-w-0">
            <p className="text-sm font-medium truncate text-gray-900 dark:text-gray-100">{displayName}</p>
            {displayEmail && displayName !== displayEmail && (
              <p className="text-xs text-gray-400 dark:text-gray-500 truncate">{displayEmail}</p>
            )}
            {account?.sync_status && (
              <span className={`text-xs ${account.sync_status === "active" ? "text-green-500" : "text-amber-500"}`}>
                ● {account.sync_status}
              </span>
            )}
          </div>
        </div>
      </div>
    </>
  );

  return (
    <>
      <button
        onClick={() => setMobileOpen(true)}
        className="md:hidden fixed top-2.5 left-2 z-50 p-2 rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 shadow-sm"
      >
        <Menu size={20} className="text-gray-600 dark:text-gray-400" />
      </button>

      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/50" onClick={() => setMobileOpen(false)} />
      )}

      <aside
        className={`md:hidden fixed top-0 left-0 z-50 w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 min-h-screen p-3 flex flex-col transition-transform duration-300 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <button onClick={() => setMobileOpen(false)} className="self-end p-2 mb-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
          <X size={20} className="text-gray-600 dark:text-gray-400" />
        </button>
        {sidebarContent}
      </aside>

      <aside className="hidden md:flex group w-16 hover:w-56 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 h-screen sticky top-0 p-3 flex-col transition-all duration-300 ease-in-out overflow-hidden">
        {sidebarContent}
      </aside>
    </>
  );
}
