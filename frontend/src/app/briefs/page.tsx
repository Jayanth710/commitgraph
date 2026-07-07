"use client";

import { useEffect, useMemo, useState } from "react";
import { MoonStar, RefreshCw, Sunrise, CalendarDays, Inbox, Briefcase } from "lucide-react";
import { toast } from "react-toastify";

import { api } from "@/lib/api";
import type { DailyBriefRun, DailyBriefType } from "@/lib/types";
import PageTransition from "@/components/PageTransition";
import { ListSkeleton } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import BriefDeliverySettings from "@/components/BriefDeliverySettings";
import { useAccountFilter } from "@/components/AccountFilterProvider";

const SECTION_LABELS: Record<string, string> = {
  due_today: "Due today",
  overdue: "Overdue carryover",
  followups: "Important follow-ups",
  job_actions: "Job application actions",
  new_commitments: "New commitments",
  completed: "Completed today",
  review: "Important emails",
  job_updates: "Job updates",
  tomorrow: "Tomorrow's deadlines",
};

export default function BriefsPage() {
  const [briefType, setBriefType] = useState<DailyBriefType>("morning");
  const [latestRun, setLatestRun] = useState<DailyBriefRun | null>(null);
  const [history, setHistory] = useState<DailyBriefRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const { activeAccountId } = useAccountFilter();

  const params = useMemo(() => {
    const query = new URLSearchParams({ brief_type: briefType });
    if (activeAccountId) query.set("account_id", activeAccountId);
    return query.toString();
  }, [briefType, activeAccountId]);

  async function load(selectedId?: string) {
    setLoading(true);
    try {
      const [latest, runs] = await Promise.all([
        api.getLatestDailyBrief(params),
        api.getDailyBriefs(params),
      ]);

      let run = latest.run;
      if (selectedId) {
        const detail = await api.getDailyBrief(selectedId);
        run = detail.run;
      } else if (run?.id) {
        const detail = await api.getDailyBrief(run.id);
        run = detail.run;
      }

      setLatestRun(run);
      setHistory(runs.runs || []);
    } catch (err) {
      console.error(err);
      toast.error("Failed to load daily briefs.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [params]);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const result = await api.generateDailyBrief({
        brief_type: briefType,
        account_id: activeAccountId,
      });
      await load(result.run.id);
      window.dispatchEvent(new Event("commitgraph:refresh"));
      toast.success(`${briefType === "morning" ? "Morning" : "Night"} brief generated.`);
    } catch (err) {
      console.error(err);
      toast.error("Failed to generate daily brief.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <PageTransition>
      <>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
          <div>
            <h2 className="text-2xl font-bold">Daily Briefs</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Generate morning and night brief runs from commitments, review items, and job updates.
            </p>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
          >
            <RefreshCw size={16} className={generating ? "animate-spin" : ""} />
            Generate {briefType === "morning" ? "Morning" : "Night"} Brief
          </button>
        </div>

        <div className="flex gap-2 mb-6">
          <TabButton
            active={briefType === "morning"}
            icon={<Sunrise size={15} />}
            label="Morning"
            onClick={() => setBriefType("morning")}
          />
          <TabButton
            active={briefType === "night"}
            icon={<MoonStar size={15} />}
            label="Night"
            onClick={() => setBriefType("night")}
          />
        </div>

        {loading ? (
          <ListSkeleton count={4} />
        ) : !latestRun ? (
          <EmptyState
            icon={briefType === "morning" ? Sunrise : MoonStar}
            title={`No ${briefType} brief yet`}
            description={`Generate your first ${briefType} brief to capture the latest priorities and updates.`}
          />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-[1.5fr_0.9fr] gap-6">
            <section className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
              <div className="flex items-center justify-between gap-3 mb-4">
                <div>
                  <h3 className="text-lg font-semibold">
                    {briefType === "morning" ? "Morning" : "Night"} brief for{" "}
                    {new Date(latestRun.brief_date).toLocaleDateString()}
                  </h3>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    Generated {latestRun.created_at ? new Date(latestRun.created_at).toLocaleString() : "just now"}
                  </p>
                </div>
                <div className="text-right text-xs text-gray-500 dark:text-gray-400">
                  <p>{latestRun.stats_json?.overdue_count ?? latestRun.stats?.overdue_count ?? 0} overdue</p>
                  <p>{latestRun.items?.length ?? 0} tracked items</p>
                </div>
              </div>

              <div className="rounded-xl bg-gray-50 dark:bg-gray-800 px-4 py-3 text-sm whitespace-pre-wrap text-gray-700 dark:text-gray-200 mb-6">
                {latestRun.summary_markdown}
              </div>

              <div className="space-y-5">
                {Object.entries(latestRun.sections || {}).map(([sectionKey, items]) => (
                  <div key={sectionKey}>
                    <h4 className="text-xs uppercase tracking-wide font-semibold text-gray-400 dark:text-gray-500 mb-2">
                      {SECTION_LABELS[sectionKey] || sectionKey}
                    </h4>
                    {items.length === 0 ? (
                      <p className="text-sm text-gray-400 dark:text-gray-500">Nothing here.</p>
                    ) : (
                      <div className="space-y-2">
                        {items.map((item) => (
                          <div
                            key={item.id}
                            className="rounded-lg border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 px-3 py-3"
                          >
                            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                              {item.title}
                            </p>
                            {item.body && (
                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                {item.body}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <aside className="space-y-6">
              <section className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-4">
                  Recent Runs
                </h3>
                {history.length === 0 ? (
                  <p className="text-sm text-gray-400 dark:text-gray-500">No runs yet.</p>
                ) : (
                  <div className="space-y-2">
                    {history.map((run) => (
                      <button
                        key={run.id}
                        onClick={() => load(run.id)}
                        className={`w-full text-left rounded-lg border px-3 py-3 transition-colors ${
                          latestRun.id === run.id
                            ? "border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950"
                            : "border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-medium">
                            {new Date(run.brief_date).toLocaleDateString()}
                          </p>
                          <span className="text-[11px] text-gray-400 dark:text-gray-500 uppercase">
                            {run.brief_type}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
                          {run.summary_markdown}
                        </p>
                      </button>
                    ))}
                  </div>
                )}
              </section>

              <section className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-4">
                  What this brief includes
                </h3>
                <div className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
                  <InfoRow icon={<CalendarDays size={14} />} text="Commitments due today or tomorrow" />
                  <InfoRow icon={<Inbox size={14} />} text="Review queue items and follow-ups" />
                  <InfoRow icon={<Briefcase size={14} />} text="Job application updates and actions" />
                </div>
              </section>
            </aside>
          </div>
        )}

        <div className="mt-10 pt-8 border-t border-gray-200 dark:border-gray-800">
          <BriefDeliverySettings />
        </div>
      </>
    </PageTransition>
  );
}

function TabButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
        active
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function InfoRow({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-400 dark:text-gray-500">{icon}</span>
      <span>{text}</span>
    </div>
  );
}
