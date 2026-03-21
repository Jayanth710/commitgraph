"use client";
import { useTheme } from "@/components/ThemeProvider";
import { useAuth } from "@/components/AuthProvider";
import { Sun, Moon, LogOut } from "lucide-react";

export default function TopBar() {
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();

  return (
    <div className="sticky top-0 z-30 flex items-center justify-between px-4 md:px-8 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
      <h1 className="text-base md:text-lg font-bold text-gray-900 dark:text-gray-100 ml-10 md:ml-0">
        Commit<span className="text-blue-600 dark:text-blue-400">Graph</span>
      </h1>
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