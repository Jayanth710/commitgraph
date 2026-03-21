"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ListSkeleton } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import PageTransition from "@/components/PageTransition";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import {
  startOfMonth, endOfMonth, startOfWeek, endOfWeek,
  addMonths, subMonths, eachDayOfInterval, format,
  isSameMonth, isSameDay, isToday, parseISO
} from "date-fns";
import { useAccountFilter } from "@/components/AccountFilterProvider";

export default function CalendarPage() {
  const [commitments, setCommitments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const {activeAccountId} = useAccountFilter()

  useEffect(() => {
        async function load() {
      try {
        const params = new URLSearchParams({ limit: "200" });
        if (activeAccountId) params.set("account_id", activeAccountId);
        const data = await api.getCommitments(params.toString());
        setCommitments(data.commitments.filter((c: any) => c.due_date));
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [activeAccountId]);

  if (loading) return <ListSkeleton count={5} />;

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calStart = startOfWeek(monthStart);
  const calEnd = endOfWeek(monthEnd);
  const days = eachDayOfInterval({ start: calStart, end: calEnd });

  const getCommitmentsForDay = (day: Date) => {
    return commitments.filter((c) => {
      const dueDate = parseISO(c.due_date);
      return isSameDay(dueDate, day);
    });
  };

  const selectedCommitments = selectedDate ? getCommitmentsForDay(selectedDate) : [];

  const statusDot: Record<string, string> = {
    confirmed: "bg-blue-500",
    overdue: "bg-red-500",
    completed: "bg-green-500",
    detected: "bg-amber-500",
    in_progress: "bg-purple-500",
  };

  const statusColors: Record<string, string> = {
    confirmed: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    overdue: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    completed: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    detected: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
    in_progress: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    abandoned: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
  };

  return (
    <PageTransition>
      <>
        <h2 className="text-2xl font-bold mb-6">Calendar</h2>

        {commitments.length === 0 ? (
          <EmptyState
            icon={CalendarDays}
            title="No due dates"
            description="Commitments with due dates will appear on the calendar."
          />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Calendar grid */}
            <div className="lg:col-span-2 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5">
              {/* Month navigation */}
              <div className="flex items-center justify-between mb-5">
                <button
                  onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
                  className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  <ChevronLeft size={18} className="text-gray-500" />
                </button>
                <h3 className="text-lg font-semibold">{format(currentMonth, "MMMM yyyy")}</h3>
                <button
                  onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
                  className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  <ChevronRight size={18} className="text-gray-500" />
                </button>
              </div>

              {/* Day headers */}
              <div className="grid grid-cols-7 mb-2">
                {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
                  <div key={d} className="text-xs font-medium text-gray-500 dark:text-gray-400 text-center py-2">
                    {d}
                  </div>
                ))}
              </div>

              {/* Day cells */}
              <div className="grid grid-cols-7">
                {days.map((day) => {
                  const dayCommitments = getCommitmentsForDay(day);
                  const inMonth = isSameMonth(day, currentMonth);
                  const today = isToday(day);
                  const isSelected = selectedDate && isSameDay(day, selectedDate);

                  return (
                    <button
                      key={day.toISOString()}
                      onClick={() => setSelectedDate(isSelected ? null : day)}
                      className={`relative min-h-[72px] p-1.5 border border-gray-100 dark:border-gray-800 text-left transition-colors ${
                        !inMonth ? "opacity-30" : ""
                      } ${isSelected ? "bg-blue-50 dark:bg-blue-950" : "hover:bg-gray-50 dark:hover:bg-gray-800"}`}
                    >
                      <span className={`text-xs font-medium block mb-1 ${
                        today
                          ? "bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center"
                          : "text-gray-700 dark:text-gray-300"
                      }`}>
                        {format(day, "d")}
                      </span>
                      {dayCommitments.length > 0 && (
                        <div className="flex flex-wrap gap-0.5">
                          {dayCommitments.slice(0, 3).map((c) => (
                            <span
                              key={c.id}
                              className={`w-1.5 h-1.5 rounded-full ${statusDot[c.status] || "bg-gray-400"}`}
                              title={c.summary}
                            />
                          ))}
                          {dayCommitments.length > 3 && (
                            <span className="text-[9px] text-gray-400">+{dayCommitments.length - 3}</span>
                          )}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Side panel — selected day's commitments */}
            <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5">
              <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
                {selectedDate ? format(selectedDate, "EEEE, MMM d") : "Select a date"}
              </h3>

              {!selectedDate ? (
                <p className="text-sm text-gray-400 dark:text-gray-500">Click a date to see commitments due that day.</p>
              ) : selectedCommitments.length === 0 ? (
                <p className="text-sm text-gray-400 dark:text-gray-500">No commitments due this day.</p>
              ) : (
                <div className="space-y-3">
                  {selectedCommitments.map((c: any) => (
                    <div key={c.id} className="p-3 rounded-lg border border-gray-100 dark:border-gray-800">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium flex-1">{c.summary}</p>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium whitespace-nowrap ${statusColors[c.status] ?? "bg-gray-100"}`}>
                          {c.status}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {c.direction === "outbound" ? "You →" : "←"} {c.target_email || c.owner_email}
                      </p>
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                        {Math.round(c.confidence_score * 100)}% confidence
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Legend */}
              <div className="mt-6 pt-4 border-t border-gray-100 dark:border-gray-800">
                <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">Legend</p>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(statusDot).map(([status, color]) => (
                    <div key={status} className="flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full ${color}`} />
                      <span className="text-xs text-gray-500 dark:text-gray-400">{status}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </>
    </PageTransition>
  );
}