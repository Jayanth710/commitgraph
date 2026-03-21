"use client";
import { useEffect, useState } from "react";
import { useTheme } from "@/components/ThemeProvider";
import { useAuth } from "@/components/AuthProvider";
import { useAccountFilter } from "@/components/AccountFilterProvider";
import { api } from "@/lib/api";
import { Sun, Moon, LogOut } from "lucide-react";

export default function TopBar() {
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();
  const { activeAccountId, setActiveAccountId } = useAccountFilter();
  const [accounts, setAccounts] = useState<any[]>([]);

  useEffect(() => {
    async function loadAccounts() {
      try {
        const data = await api.getAccounts();
        setAccounts(data.accounts || []);
      } catch (err) {
        console.error(err);
      }
    }
    loadAccounts();
  }, []);

  return (
    <div className="sticky top-0 z-30 flex items-center justify-between px-4 md:px-8 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
      <div className="flex items-center gap-3 min-w-0">
        <h1 className="text-base md:text-lg font-bold text-gray-900 dark:text-gray-100 ml-10 md:ml-0 whitespace-nowrap">
          Commit<span className="text-blue-600 dark:text-blue-400">Graph</span>
        </h1>

        <div className="hidden md:flex items-center gap-2 ml-2">
          <button
            onClick={() => setActiveAccountId(null)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              activeAccountId === null
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
            }`}
          >
            All
          </button>

          {accounts.map((account) => {
            const label = (account.email_address || "?")[0].toUpperCase();
            const active = activeAccountId === account.id;

            return (
              <button
                key={account.id}
                onClick={() => setActiveAccountId(account.id)}
                title={account.email_address}
                className={`w-8 h-8 rounded-full text-xs font-semibold border transition-colors flex items-center justify-center ${
                  active
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-700"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-1 md:gap-3">
        <button
          onClick={toggle}
          className="flex items-center gap-1.5 px-2 md:px-3 py-1.5 rounded-lg text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          <span className="hidden md:inline">{theme === "dark" ? "Light" : "Dark"}</span>
        </button>
        {user && (
          <>
            <span className="hidden md:inline text-xs text-gray-400 dark:text-gray-500">
              {user.email}
            </span>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 px-2 md:px-3 py-1.5 rounded-lg text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
            >
              <LogOut size={14} />
              <span className="hidden md:inline">Logout</span>
            </button>
          </>
        )}
      </div>
    </div>
  );
}