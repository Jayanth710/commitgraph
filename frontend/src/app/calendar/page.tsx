"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { CalendarEvent } from "@/lib/types";
import { ListSkeleton } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import PageTransition from "@/components/PageTransition";
import { CalendarDays, ChevronLeft, ChevronRight, MapPin, RefreshCw, Users } from "lucide-react";
import { toast } from "react-toastify";
import {
  startOfMonth, endOfMonth, startOfWeek, endOfWeek,
  addMonths, subMonths, eachDayOfInterval, format,
  isSameMonth, isToday, parseISO
} from "date-fns";
import { useAccountFilter } from "@/components/AccountFilterProvider";

// Date-only items (commitment due dates, all-day events) are bucketed by their
// UTC date string to avoid a timezone off-by-one. Timed events bucket by local
// date.
function dayKey(day: Date) {
  return format(day, "yyyy-MM-dd");
}
function commitmentDayKey(c: any) {
  return (c.due_date || "").slice(0, 10);
}
function eventDayKey(e: CalendarEvent) {
  if (!e.start) return "";
  return e.all_day ? e.start.slice(0, 10) : format(parseISO(e.start), "yyyy-MM-dd");
}
function eventTime(e: CalendarEvent) {
  if (e.all_day || !e.start) return "All day";
  return format(parseISO(e.start), "h:mmaaa");
}

export default function CalendarPage() {
  const [commitments, setCommitments] = useState<any[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const { activeAccountId } = useAccountFilter();

  const loadEvents = useCallback(async () => {
    const params = new URLSearchParams();
    if (activeAccountId) params.set("account_id", activeAccountId);
    const data = await api.getCalendarEvents(params.toString());
    setEvents(data.events || []);
  }, [activeAccountId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const params = new URLSearchParams({ limit: "200" });
        if (activeAccountId) params.set("account_id", activeAccountId);
        const [commitData] = await Promise.all([
          api.getCommitments(params.toString()),
          loadEvents(),
        ]);
        if (!cancelled) {
          setCommitments(commitData.commitments.filter((c: any) => c.due_date));
        }
      } catch (err) {
        console.error(err);
      } finally {
        if (!cancelled) setLoading(false);
      }

      // Quietly pull fresh events from Google in the background, then refresh.
      try {
        const syncParams = new URLSearchParams();
        if (activeAccountId) syncParams.set("account_id", activeAccountId);
        await api.syncCalendar(syncParams.toString());
        if (!cancelled) {
          await loadEvents();
          setLastSynced(new Date());
        }
      } catch {
        // Silent — the manual Sync button surfaces errors.
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [activeAccountId, loadEvents]);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    try {
      const params = new URLSearchParams();
      if (activeAccountId) params.set("account_id", activeAccountId);
      const result = await api.syncCalendar(params.toString());
      await loadEvents();
      setLastSynced(new Date());
      toast.success(
        result.events_created > 0
          ? `Synced ${result.events_created} new event${result.events_created === 1 ? "" : "s"}`
          : "Calendar up to date",
      );
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Calendar sync failed");
    } finally {
      setSyncing(false);
    }
  }, [activeAccountId, loadEvents]);

  if (loading) return <ListSkeleton count={5} />;

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calStart = startOfWeek(monthStart);
  const calEnd = endOfWeek(monthEnd);
  const days = eachDayOfInterval({ start: calStart, end: calEnd });

  const commitmentsForDay = (day: Date) => {
    const key = dayKey(day);
    return commitments.filter((c) => commitmentDayKey(c) === key);
  };
  const eventsForDay = (day: Date) => {
    const key = dayKey(day);
    return events.filter((e) => eventDayKey(e) === key);
  };

  const selectedCommitments = selectedDate ? commitmentsForDay(selectedDate) : [];
  const selectedEvents = selectedDate ? eventsForDay(selectedDate) : [];

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

  const isEmpty = commitments.length === 0 && events.length === 0;

  return (
    <PageTransition>
      <>
        <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
          <h2 className="text-2xl font-bold">Calendar</h2>
          <div className="flex items-center gap-3">
            {lastSynced && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                Synced {format(lastSynced, "h:mmaaa")}
              </span>
            )}
            <button
              onClick={handleSync}
              disabled={syncing}
              className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={syncing ? "animate-spin" : ""} />
              {syncing ? "Syncing..." : "Sync Google Calendar"}
            </button>
          </div>
        </div>

        {isEmpty ? (
          <EmptyState
            icon={CalendarDays}
            title="Nothing on the calendar yet"
            description="Sync your Google Calendar, or add due dates to commitments — both show up here."
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
                  const dayCommitments = commitmentsForDay(day);
                  const dayEvents = eventsForDay(day);
                  const inMonth = isSameMonth(day, currentMonth);
                  const today = isToday(day);
                  const isSelected = selectedDate && dayKey(day) === dayKey(selectedDate);

                  return (
                    <button
                      key={day.toISOString()}
                      onClick={() => setSelectedDate(isSelected ? null : day)}
                      className={`relative min-h-[80px] p-1.5 border border-gray-100 dark:border-gray-800 text-left align-top transition-colors ${
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

                      <div className="space-y-0.5">
                        {dayCommitments.length > 0 && (
                          <div className="flex flex-wrap gap-0.5">
                            {dayCommitments.slice(0, 4).map((c) => (
                              <span
                                key={c.id}
                                className={`w-1.5 h-1.5 rounded-full ${statusDot[c.status] || "bg-gray-400"}`}
                                title={c.summary}
                              />
                            ))}
                            {dayCommitments.length > 4 && (
                              <span className="text-[9px] text-gray-400">+{dayCommitments.length - 4}</span>
                            )}
                          </div>
                        )}

                        {dayEvents.slice(0, 2).map((e) => (
                          <div
                            key={e.id}
                            title={e.title}
                            className="truncate rounded-sm bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-200 px-1 text-[9px] leading-tight"
                          >
                            {e.all_day ? "" : `${format(parseISO(e.start!), "ha")} `}{e.title}
                          </div>
                        ))}
                        {dayEvents.length > 2 && (
                          <div className="text-[9px] text-gray-400">+{dayEvents.length - 2} more</div>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Side panel — selected day */}
            <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5">
              <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
                {selectedDate ? format(selectedDate, "EEEE, MMM d") : "Select a date"}
              </h3>

              {!selectedDate ? (
                <p className="text-sm text-gray-400 dark:text-gray-500">Click a date to see events and commitments.</p>
              ) : selectedEvents.length === 0 && selectedCommitments.length === 0 ? (
                <p className="text-sm text-gray-400 dark:text-gray-500">Nothing on this day.</p>
              ) : (
                <div className="space-y-4">
                  {selectedEvents.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Google Calendar</p>
                      {selectedEvents.map((e) => (
                        <div key={e.id} className="p-3 rounded-lg border border-emerald-100 dark:border-emerald-900 bg-emerald-50/40 dark:bg-emerald-950/30">
                          <p className="text-sm font-medium">{e.title}</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{eventTime(e)}</p>
                          {e.location && (
                            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5 flex items-center gap-1">
                              <MapPin size={11} /> {e.location}
                            </p>
                          )}
                          {e.attendees.length > 0 && (
                            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5 flex items-center gap-1">
                              <Users size={11} /> {e.attendees.length} attendee{e.attendees.length === 1 ? "" : "s"}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {selectedCommitments.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-blue-600 dark:text-blue-400">Commitments due</p>
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
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Legend */}
              <div className="mt-6 pt-4 border-t border-gray-100 dark:border-gray-800">
                <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">Legend</p>
                <div className="flex flex-wrap gap-3">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-2 rounded-sm bg-emerald-300 dark:bg-emerald-700" />
                    <span className="text-xs text-gray-500 dark:text-gray-400">event</span>
                  </div>
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
