"use client";

import { useEffect, useState } from "react";
import {
  Briefcase,
  Building2,
  CalendarDays,
  ChevronDown,
  History,
  Search,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react";
import { toast } from "react-toastify";

import { useAccountFilter } from "@/components/AccountFilterProvider";
import EmptyState from "@/components/EmptyState";
import PageTransition from "@/components/PageTransition";
import { ListSkeleton } from "@/components/Skeleton";
import { api } from "@/lib/api";
import type {
  JobApplication,
  JobApplicationEvent,
  JobApplicationStatus,
} from "@/lib/types";

const STATUS_OPTIONS: JobApplicationStatus[] = [
  "applied",
  "assessment",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
  "closed",
];

const APPLIED_WITHIN_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All time" },
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
];

export default function ApplicationsPage() {
  const [items, setItems] = useState<JobApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [appliedWithin, setAppliedWithin] = useState("all");
  const [appliedFrom, setAppliedFrom] = useState("");
  const [appliedTo, setAppliedTo] = useState("");
  const [query, setQuery] = useState("");
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pendingDeleteItem, setPendingDeleteItem] = useState<JobApplication | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [eventsByApp, setEventsByApp] = useState<Record<string, JobApplicationEvent[]>>({});
  const [loadingEventsId, setLoadingEventsId] = useState<string | null>(null);
  const { activeAccountId } = useAccountFilter();

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (activeAccountId) params.set("account_id", activeAccountId);
        if (statusFilter !== "all") params.set("status", statusFilter);
        if (appliedFrom || appliedTo) {
          if (appliedFrom) params.set("applied_from", appliedFrom);
          if (appliedTo) params.set("applied_to", appliedTo);
        } else if (appliedWithin !== "all") {
          params.set("applied_within_days", appliedWithin);
        }
        if (query.trim()) params.set("q", query.trim());

        const data = await api.getJobApplications(params.toString());
        setItems(data.job_applications || []);
      } catch (err) {
        console.error(err);
        toast.error("Failed to load job applications.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [activeAccountId, statusFilter, appliedWithin, appliedFrom, appliedTo, query]);

  function selectPreset(value: string) {
    setAppliedWithin(value);
    setAppliedFrom("");
    setAppliedTo("");
  }

  async function handleStatusUpdate(id: string, status: JobApplicationStatus) {
    setUpdatingId(id);
    try {
      const result = await api.updateJobApplication(id, { status });
      setItems((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, ...result.job_application } : item,
        ),
      );
      // The manual change added a status_change event; refresh the timeline if
      // it's open, otherwise drop the stale cache so the next expand refetches.
      if (expandedId === id) {
        loadEvents(id);
      } else {
        setEventsByApp((prev) => {
          if (!(id in prev)) return prev;
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }
      toast.success("Application status updated.");
    } catch (err) {
      console.error(err);
      toast.error("Failed to update application status.");
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleDelete(item: JobApplication) {
    setDeletingId(item.id);
    try {
      await api.deleteJobApplication(item.id);
      setItems((prev) => prev.filter((entry) => entry.id !== item.id));
      toast.success("Job application deleted.");
      setPendingDeleteItem(null);
    } catch (err) {
      console.error(err);
      toast.error("Failed to delete job application.");
    } finally {
      setDeletingId(null);
    }
  }

  async function loadEvents(id: string) {
    setLoadingEventsId(id);
    try {
      const data = await api.getJobApplication(id);
      setEventsByApp((prev) => ({ ...prev, [id]: data.events || [] }));
    } catch (err) {
      console.error(err);
      toast.error("Failed to load update history.");
      setExpandedId((current) => (current === id ? null : current));
    } finally {
      setLoadingEventsId(null);
    }
  }

  function toggleTimeline(id: string) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (!eventsByApp[id]) loadEvents(id);
  }

  const appliedCount = items.filter((item) => item.status === "applied").length;
  const interviewCount = items.filter((item) => item.status === "interview").length;
  const rejectedCount = items.filter((item) => item.status === "rejected").length;

  return (
    <PageTransition>
      <>
        <div className="flex flex-col gap-2 mb-6">
          <h2 className="text-2xl font-bold">Applications</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Job applications detected from your email, with status tracking over time.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-6">
          <StatCard
            icon={<Briefcase size={16} className="text-blue-500" />}
            label="Tracked applications"
            value={items.length}
          />
          <StatCard
            icon={<Sparkles size={16} className="text-amber-500" />}
            label="Applied"
            value={appliedCount}
          />
          <StatCard
            icon={<CalendarDays size={16} className="text-green-500" />}
            label="Interviews"
            value={interviewCount}
          />
          <StatCard
            icon={<XCircle size={16} className="text-red-500" />}
            label="Rejected"
            value={rejectedCount}
          />
        </div>

        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search company, role, or summary"
                className="w-full pl-10 pr-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm outline-none"
            >
              <option value="all">All statuses</option>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {formatStatus(status)}
                </option>
              ))}
            </select>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
              Applied:
            </span>
            {APPLIED_WITHIN_OPTIONS.map((option) => {
              const active = !appliedFrom && !appliedTo && appliedWithin === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => selectPreset(option.value)}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    active
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                  }`}
                >
                  {option.label}
                </button>
              );
            })}

            <span className="mx-1 hidden h-5 w-px bg-gray-200 dark:bg-gray-700 sm:block" />

            <div className="flex flex-wrap items-center gap-2">
              <input
                type="date"
                value={appliedFrom}
                max={appliedTo || undefined}
                onChange={(e) => {
                  setAppliedFrom(e.target.value);
                  setAppliedWithin("all");
                }}
                aria-label="Applied from"
                className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-2.5 py-1.5 text-xs outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-xs text-gray-400">to</span>
              <input
                type="date"
                value={appliedTo}
                min={appliedFrom || undefined}
                onChange={(e) => {
                  setAppliedTo(e.target.value);
                  setAppliedWithin("all");
                }}
                aria-label="Applied to"
                className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-2.5 py-1.5 text-xs outline-none focus:ring-2 focus:ring-blue-500"
              />
              {(appliedFrom || appliedTo) && (
                <button
                  type="button"
                  onClick={() => selectPreset("all")}
                  className="text-xs font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>

        {loading ? (
          <ListSkeleton count={5} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={Briefcase}
            title="No job applications yet"
            description="Application-related emails will start appearing here once they’re detected from your inbox."
          />
        ) : (
          <div className="space-y-4">
            {items.map((item) => (
              <div
                key={item.id}
                className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5"
              >
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-lg font-semibold">{item.company_name}</h3>
                          <StatusBadge status={item.status} />
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setPendingDeleteItem(item)}
                        disabled={deletingId === item.id}
                        aria-label={`Delete ${item.company_name} application`}
                        className="shrink-0 rounded-md p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>

                    <div className="flex items-center gap-2 mt-1 text-sm text-gray-500 dark:text-gray-400">
                      <Building2 size={14} />
                      <span>{item.role_title || "Role not detected yet"}</span>
                    </div>

                    <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">
                      {item.summary}
                    </p>

                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs text-gray-400 dark:text-gray-500">
                      <span>
                        Applied: {item.date_applied ? formatDate(item.date_applied) : "Unknown"}
                      </span>
                      <span>
                        Last update: {item.last_status_at ? formatDate(item.last_status_at) : "Unknown"}
                      </span>
                      {item.account_email && <span>Mailbox: {item.account_email}</span>}
                      <span>Confidence: {Math.round((item.confidence_score || 0) * 100)}%</span>
                    </div>

                    {item.raw_text && (
                      <div className="mt-4 rounded-lg bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm text-gray-600 dark:text-gray-300">
                        {item.raw_text}
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => toggleTimeline(item.id)}
                      aria-expanded={expandedId === item.id}
                      className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400"
                    >
                      <History size={14} />
                      {expandedId === item.id ? "Hide update history" : "Show update history"}
                      <ChevronDown
                        size={14}
                        className={`transition-transform ${expandedId === item.id ? "rotate-180" : ""}`}
                      />
                    </button>

                    {expandedId === item.id && (
                      <Timeline
                        events={eventsByApp[item.id]}
                        loading={loadingEventsId === item.id}
                      />
                    )}
                  </div>

                  <div className="w-full lg:w-48 shrink-0">
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
                      Update status
                    </label>
                    <select
                      value={item.status}
                      onChange={(e) =>
                        handleStatusUpdate(item.id, e.target.value as JobApplicationStatus)
                      }
                      disabled={updatingId === item.id}
                      className="w-full px-3 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm outline-none"
                    >
                      {STATUS_OPTIONS.map((status) => (
                        <option key={status} value={status}>
                          {formatStatus(status)}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {pendingDeleteItem && (
          <DeleteApplicationModal
            item={pendingDeleteItem}
            deleting={deletingId === pendingDeleteItem.id}
            onCancel={() => {
              if (!deletingId) setPendingDeleteItem(null);
            }}
            onConfirm={() => handleDelete(pendingDeleteItem)}
          />
        )}
      </>
    </PageTransition>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 dark:text-gray-400">{label}</span>
        {icon}
      </div>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

function Timeline({
  events,
  loading,
}: {
  events: JobApplicationEvent[] | undefined;
  loading: boolean;
}) {
  if (loading && !events) {
    return (
      <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">Loading update history…</p>
    );
  }

  if (!events || events.length === 0) {
    return (
      <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">No updates recorded yet.</p>
    );
  }

  return (
    <ol className="mt-4 space-y-4 border-l border-gray-200 pl-4 dark:border-gray-700">
      {events.map((event) => (
        <li key={event.id} className="relative">
          <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-blue-500 ring-4 ring-white dark:ring-gray-900" />
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-gray-700 dark:text-gray-200">
              {formatEventType(event.event_type)}
            </span>
            {event.status && <StatusBadge status={event.status} />}
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {formatDate(event.event_date || event.created_at || "")}
            </span>
          </div>
          {event.summary && (
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{event.summary}</p>
          )}
          {event.subject && (
            <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">From: {event.subject}</p>
          )}
        </li>
      ))}
    </ol>
  );
}

function formatEventType(type: string) {
  switch (type) {
    case "detected":
      return "Detected";
    case "status_change":
      return "Status change";
    case "note":
      return "Update";
    default:
      return formatStatus(type);
  }
}

function StatusBadge({ status }: { status: JobApplicationStatus }) {
  const classes: Record<JobApplicationStatus, string> = {
    applied: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    assessment: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    interview: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
    offer: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
    rejected: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
    withdrawn: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    closed: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  };

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${classes[status]}`}>
      {formatStatus(status)}
    </span>
  );
}

function formatStatus(status: string) {
  return status.replace("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDate(value: string) {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unknown" : parsed.toLocaleDateString();
}

function DeleteApplicationModal({
  item,
  deleting,
  onCancel,
  onConfirm,
}: {
  item: JobApplication;
  deleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const label = item.role_title
    ? `${item.role_title} at ${item.company_name}`
    : item.company_name;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-xl rounded-3xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-gray-800 dark:bg-gray-950">
        <h3 className="text-3xl font-semibold tracking-tight text-gray-900 dark:text-gray-50">
          Delete application?
        </h3>
        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
          This will permanently remove the job tracker for{" "}
          <span className="font-semibold text-gray-900 dark:text-gray-50">
            {label}
          </span>
          .
        </p>

        <div className="mt-8 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={deleting}
            className="rounded-2xl border border-gray-300 px-6 py-3 text-base font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-900"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={deleting}
            className="rounded-2xl bg-red-600 px-6 py-3 text-base font-semibold text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
