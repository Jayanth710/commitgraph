"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ListSkeleton } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import PageTransition from "@/components/PageTransition";
import {
  CalendarDays,
  CheckCircle,
  AlertTriangle,
  TrendingUp,
  Clock,
  ArrowUpRight,
  ArrowDownLeft,
  Users,
} from "lucide-react";

export default function DigestPage() {
  const [digest, setDigest] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getWeeklyDigest();
        setDigest(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <ListSkeleton count={5} />;

  if (!digest) {
    return (
      <EmptyState
        icon={CalendarDays}
        title="No digest available"
        description="Connect an email account to start generating weekly digests."
      />
    );
  }

  const { stats, due_groups, recently_completed, overdue, top_people } = digest;

  return (
    <PageTransition>
      <>
        <h2 className="text-2xl font-bold mb-2">Weekly Digest</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          Your commitment summary for this week
        </p>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          <DigestStat label="New this week" value={stats.new_this_week} icon={<TrendingUp size={16} className="text-blue-500" />} />
          <DigestStat label="Completed" value={stats.completed_this_week} icon={<CheckCircle size={16} className="text-green-500" />} />
          <DigestStat label="Due this week" value={stats.due_this_week} icon={<Clock size={16} className="text-amber-500" />} />
          <DigestStat label="Overdue" value={stats.currently_overdue} icon={<AlertTriangle size={16} className="text-red-500" />} highlight={stats.currently_overdue > 0} />
          <DigestStat label="Total open" value={stats.total_open} icon={<CalendarDays size={16} className="text-gray-500" />} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
          <DigestStat label="I owe" value={stats.outbound_open} icon={<ArrowUpRight size={16} className="text-purple-500" />} />
          <DigestStat label="Owed to me" value={stats.inbound_open} icon={<ArrowDownLeft size={16} className="text-teal-500" />} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2 space-y-6">
            <section className={`bg-white dark:bg-gray-900 rounded-lg border p-5 ${
              overdue.length > 0 ? "border-red-200 dark:border-red-900" : "border-gray-200 dark:border-gray-800"
            }`}>
              <h3 className="text-sm font-semibold uppercase tracking-wide mb-4 flex items-center gap-2 text-red-500 dark:text-red-400">
                <AlertTriangle size={14} />
                Overdue ({overdue.length})
              </h3>
              {overdue.length === 0 ? (
                <p className="text-sm text-green-500 py-4 text-center">You&apos;re all caught up!</p>
              ) : (
                <div className="space-y-2">
                  {overdue.map((c: any) => (
                    <DigestItem key={c.id} commitment={c} showDate urgent />
                  ))}
                </div>
              )}
            </section>

            <section className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5">
              <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4 flex items-center gap-2">
                <Clock size={14} />
                Due This Week
              </h3>

              {due_groups.length === 0 ? (
                <p className="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">
                  Nothing due this week
                </p>
              ) : (
                <div className="space-y-5">
                  {due_groups.map((group: any) => (
                    <div key={group.date}>
                      <p className="text-xs font-semibold tracking-wide text-gray-400 dark:text-gray-500 uppercase mb-2">
                        {new Date(group.date).toLocaleDateString("en-US", {
                          weekday: "long",
                          month: "short",
                          day: "numeric",
                        })}
                      </p>
                      <div className="space-y-2">
                        {group.items.map((c: any) => (
                          <DigestItem key={c.id} commitment={c} showDate />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5">
              <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4 flex items-center gap-2">
                <CheckCircle size={14} className="text-green-500" />
                Completed This Week ({recently_completed.length})
              </h3>
              {recently_completed.length === 0 ? (
                <p className="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">
                  No completions this week yet
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {recently_completed.map((c: any) => (
                    <div key={c.id} className="flex items-center gap-2 p-2 rounded-lg bg-green-50 dark:bg-green-950">
                      <CheckCircle size={14} className="text-green-500 shrink-0" />
                      <p className="text-sm text-gray-700 dark:text-gray-300 truncate">{c.summary}</p>
                      {c.completed_at && (
                        <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0 ml-auto">
                          {new Date(c.completed_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <aside className="space-y-6">
            <section className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5">
              <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4 flex items-center gap-2">
                <Users size={14} />
                Top People
              </h3>

              {top_people.length === 0 ? (
                <p className="text-sm text-gray-400 dark:text-gray-500">No people data yet.</p>
              ) : (
                <div className="space-y-3">
                  {top_people.map((p: any) => (
                    <div key={p.id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{p.label}</p>
                        <p className="text-xs text-gray-400 dark:text-gray-500 truncate">{p.email}</p>
                      </div>
                      <span className="text-xs px-2 py-1 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
                        {p.open_commitment_count}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </aside>
        </div>
      </>
    </PageTransition>
  );
}

function DigestStat({
  label,
  value,
  icon,
  highlight,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        highlight
          ? "border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950"
          : "border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900"
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
        {icon}
      </div>
      <p className="text-xl font-bold">{value}</p>
    </div>
  );
}

function DigestItem({
  commitment: c,
  showDate,
  urgent,
}: {
  commitment: any;
  showDate?: boolean;
  urgent?: boolean;
}) {
  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-lg ${
        urgent ? "bg-red-50 dark:bg-red-950" : "bg-gray-50 dark:bg-gray-800"
      }`}
    >
      <div className="mt-0.5">
        {c.direction === "outbound" ? (
          <ArrowUpRight size={14} className="text-purple-500" />
        ) : (
          <ArrowDownLeft size={14} className="text-teal-500" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{c.summary}</p>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          {c.direction === "outbound" ? "You → " : "← "}
          {c.target_email || "general"}
        </p>
      </div>
      {showDate && c.due_date && (
        <span className={`text-xs shrink-0 ${urgent ? "text-red-500 font-medium" : "text-gray-400 dark:text-gray-500"}`}>
          {new Date(c.due_date).toLocaleDateString("en-US", {
            weekday: "short",
            month: "short",
            day: "numeric",
          })}
        </span>
      )}
    </div>
  );
}