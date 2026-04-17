"use client";
import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import {
  Mail,
  Calendar,
  Eye,
  EyeOff,
  Undo2,
  X,
  Search,
  Filter,
  CheckCircle,
  CalendarPlus,
  CalendarCheck,
  Pencil,
  MoreHorizontal,
} from "lucide-react";
import { toast } from "react-toastify";
import { useDebouncedCallback } from "use-debounce";
import { ListSkeleton } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import PageTransition from "@/components/PageTransition";
import { useAccountFilter } from "@/components/AccountFilterProvider";
// import EmailComposer from "@/components/EmailComposer";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import SortableCommitment from "@/components/SortableCommitment";

// ---------------------------------------------------------------------------
// Undo toast
// ---------------------------------------------------------------------------
type UndoAction = {
  commitmentId: string;
  previousStatus: string;
  newStatus: string;
  summary: string;
  timer: ReturnType<typeof setTimeout>;
};

function UndoToast({
  action,
  onUndo,
  onDismiss,
}: {
  action: UndoAction;
  onUndo: () => void;
  onDismiss: () => void;
}) {
  const [secondsLeft, setSecondsLeft] = useState(5);

  useEffect(() => {
    const interval = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(interval);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const statusLabels: Record<string, string> = {
    completed: "completed",
    abandoned: "abandoned",
    confirmed: "confirmed",
    in_progress: "started",
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 px-4 py-3 rounded-lg shadow-lg animate-slide-up">
      <p className="text-sm">
        Marked as{" "}
        <span className="font-medium">
          {statusLabels[action.newStatus] || action.newStatus}
        </span>
      </p>
      <button
        onClick={onUndo}
        className="flex items-center gap-1.5 text-sm font-medium px-3 py-1 rounded-md bg-white/20 dark:bg-black/10 hover:bg-white/30 dark:hover:bg-black/20 transition-colors"
      >
        <Undo2 size={13} />
        Undo ({secondsLeft}s)
      </button>
      <button
        onClick={onDismiss}
        className="p-1 hover:bg-white/20 dark:hover:bg-black/10 rounded transition-colors"
      >
        <X size={14} />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
function CommitmentsContent() {
  const searchParams = useSearchParams();
  const urlDirection = searchParams.get("direction");
  const urlStatus = searchParams.get("status");
  const { activeAccountId } = useAccountFilter();

  const [tab, setTab] = useState<"outbound" | "inbound" | "all">(
    urlDirection === "inbound"
      ? "inbound"
      : urlDirection === "outbound"
        ? "outbound"
        : urlStatus
          ? "all"
          : "outbound",
  );
  const [statusFilter, setStatusFilter] = useState<string | null>(urlStatus);
  const [searchQuery, setSearchQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [commitments, setCommitments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [undoAction, setUndoAction] = useState<UndoAction | null>(null);
  const [editingCommitment, setEditingCommitment] = useState<any | null>(null);

  const fetchCommitments = useDebouncedCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (tab !== "all") params.set("direction", tab);
      if (statusFilter) params.set("status", statusFilter);
      if (searchQuery) params.set("q", searchQuery);
      if (activeAccountId) params.set("account_id", activeAccountId);
      params.set("limit", "100");

      const data = searchQuery
        ? await api.searchCommitments(params.toString())
        : await api.getCommitments(params.toString());
      setCommitments(data.commitments);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, 300);

  useEffect(() => {
    fetchCommitments();
  }, [fetchCommitments, tab, statusFilter, searchQuery, activeAccountId]);

  const handleStatusChange = useCallback(
    async (id: string, newStatus: string) => {
      const commitment = commitments.find((c) => c.id === id);
      if (!commitment) return;

      const previousStatus = commitment.status;

      setCommitments((prev) =>
        prev.map((c) => (c.id === id ? { ...c, status: newStatus } : c)),
      );

      if (undoAction) {
        clearTimeout(undoAction.timer);
        setUndoAction(null);
      }

      try {
        await api.updateCommitment(id, { status: newStatus });
      } catch (err) {
        console.error(err);
        setCommitments((prev) =>
          prev.map((c) => (c.id === id ? { ...c, status: previousStatus } : c)),
        );
        return;
      }

      const terminalActions = ["completed", "abandoned"];
      if (terminalActions.includes(newStatus)) {
        const timer = setTimeout(() => {
          setUndoAction(null);
          window.dispatchEvent(new Event("commitgraph:refresh"));
        }, 5000);

        setUndoAction({
          commitmentId: id,
          previousStatus,
          newStatus,
          summary: commitment.summary,
          timer,
        });
      }
    },
    [commitments, undoAction],
  );

  const handleUndo = useCallback(async () => {
    if (!undoAction) return;
    clearTimeout(undoAction.timer);

    try {
      await api.updateCommitment(undoAction.commitmentId, {
        status: undoAction.previousStatus,
      });
      setCommitments((prev) =>
        prev.map((c) =>
          c.id === undoAction.commitmentId
            ? { ...c, status: undoAction.previousStatus }
            : c,
        ),
      );
    } catch (err) {
      console.error("Undo failed:", err);
    }
    setUndoAction(null);
  }, [undoAction]);

  const dismissUndo = useCallback(() => {
    if (undoAction) {
      clearTimeout(undoAction.timer);
      setUndoAction(null);
    }
  }, [undoAction]);

  const handleSaveEdit = useCallback(async (id: string, body: any) => {
    const result = await api.updateCommitment(id, body);
    const updated = result.commitment;

    setCommitments((prev) =>
      prev.map((c) => (c.id === id ? { ...c, ...updated } : c)),
    );

    setEditingCommitment(null);
    window.dispatchEvent(new Event("commitgraph:refresh"));
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = commitments.findIndex((c) => c.id === active.id);
    const newIndex = commitments.findIndex((c) => c.id === over.id);

    const reordered = arrayMove(commitments, oldIndex, newIndex);
    setCommitments(reordered);

    // Send new order to backend.
    const order = reordered.map((c, i) => ({ id: c.id, priority: i }));
    try {
      await api.reorderCommitments(order);
    } catch (err) {
      console.error("Reorder failed:", err);
    }
  };

  return (
    <PageTransition>
      <>
        <h2 className="text-2xl font-bold mb-6">Commitments</h2>

        {/* Search bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mb-4">
          <div className="flex-1 relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search commitments or email subjects..."
              className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X size={14} />
              </button>
            )}
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1.5 px-3 py-2.5 rounded-lg border text-sm transition-colors ${
              showFilters || statusFilter
                ? "border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300"
                : "border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
            }`}
          >
            <Filter size={14} />
            Filters
            {statusFilter && (
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            )}
          </button>
        </div>

        {/* Filters panel */}
        {showFilters && (
          <div className="flex items-center gap-2 mb-4 flex-wrap p-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800">
            <span className="text-xs text-gray-500 dark:text-gray-400 mr-1">
              Status:
            </span>
            {[
              "all",
              "confirmed",
              "overdue",
              "completed",
              "detected",
              "in_progress",
              "abandoned",
            ].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s === "all" ? null : s)}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  (s === "all" && !statusFilter) || statusFilter === s
                    ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 font-medium"
                    : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
                }`}
              >
                {s === "all" ? "All" : s.replace("_", " ")}
              </button>
            ))}

            <span className="text-gray-200 dark:text-gray-700 mx-1">|</span>
            <span className="text-xs text-gray-500 dark:text-gray-400 mr-1">
              Direction:
            </span>
            {[
              { value: "outbound", label: "I Owe" },
              { value: "inbound", label: "Owed To Me" },
              { value: "all", label: "Both" },
            ].map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setTab(value as "outbound" | "inbound" | "all")}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  tab === value
                    ? "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300 font-medium"
                    : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* Quick tabs */}
        <div className="flex items-center gap-2 mb-6">
          <button
            onClick={() => {
              setTab("outbound");
              setStatusFilter(null);
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === "outbound" && !statusFilter
                ? "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
            }`}
          >
            I Owe
          </button>
          <button
            onClick={() => {
              setTab("inbound");
              setStatusFilter(null);
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === "inbound" && !statusFilter
                ? "bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
            }`}
          >
            Owed To Me
          </button>

          {(statusFilter || searchQuery) && (
            <button
              onClick={() => {
                setStatusFilter(null);
                setSearchQuery("");
                setTab("outbound");
              }}
              className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 ml-2"
            >
              Clear all filters
            </button>
          )}
        </div>

        {/* Commitment list */}
        <div className="space-y-3 overflow-visible">
          {loading ? (
            <ListSkeleton count={4} />
          ) : commitments.length === 0 ? (
            <EmptyState
              icon={CheckCircle}
              title="No commitments found"
              description={
                searchQuery
                  ? `No results for "${searchQuery}"`
                  : "Commitments will appear here as emails are processed."
              }
            />
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={commitments.map((c) => c.id)}
                strategy={verticalListSortingStrategy}
              >
                {commitments.map((c: any) => (
                  <SortableCommitment key={c.id} id={c.id}>
                    <CommitmentCard
                      commitment={c}
                      onStatusChange={handleStatusChange}
                      onEdit={() => setEditingCommitment(c)}
                    />
                  </SortableCommitment>
                ))}
              </SortableContext>
            </DndContext>
          )}
        </div>

        {/* Undo toast */}
        {undoAction && (
          <UndoToast
            action={undoAction}
            onUndo={handleUndo}
            onDismiss={dismissUndo}
          />
        )}

        {editingCommitment && (
          <EditCommitmentModal
            commitment={editingCommitment}
            onClose={() => setEditingCommitment(null)}
            onSave={handleSaveEdit}
          />
        )}
      </>
    </PageTransition>
  );
}

export default function CommitmentsPage() {
  return (
    <Suspense>
      <CommitmentsContent />
    </Suspense>
  );
}

// ---------------------------------------------------------------------------
// Commitment card
// ---------------------------------------------------------------------------
function CommitmentCard({
  commitment: c,
  onStatusChange,
  onEdit,
}: {
  commitment: any;
  onStatusChange: (id: string, status: string) => void;
  onEdit: () => void;
}) {
  const [showEmail, setShowEmail] = useState(false);
  const [evidence, setEvidence] = useState<any[] | null>(null);
  const [loadingEvidence, setLoadingEvidence] = useState(false);
  const [calendarCreated, setCalendarCreated] = useState(!!c.calendar_event_id);
  const [calendarLink, setCalendarLink] = useState<string | null>(
    c.calendar_event_link || null,
  );
  const [creatingEvent, setCreatingEvent] = useState(false);
  const [removingEvent, setRemovingEvent] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const canAddToCalendar =
    !!c.due_date &&
    !calendarCreated &&
    ["confirmed", "in_progress"].includes(c.status) &&
    (c.confidence_score ?? 0) >= 0.8;

  const toggleEmail = async () => {
    setShowMenu(false);

    if (showEmail) {
      setShowEmail(false);
      return;
    }
    if (evidence === null) {
      setLoadingEvidence(true);
      try {
        const data = await api.getCommitment(c.id);
        setEvidence(data.evidence || []);
      } catch (err) {
        console.error(err);
        setEvidence([]);
      } finally {
        setLoadingEvidence(false);
      }
    }
    setShowEmail(true);
  };

  const statusColors: Record<string, string> = {
    confirmed:
      "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900 dark:text-blue-300 dark:border-blue-800",
    overdue:
      "bg-red-50 text-red-700 border-red-200 dark:bg-red-900 dark:text-red-300 dark:border-red-800",
    completed:
      "bg-green-50 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-300 dark:border-green-800",
    detected:
      "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900 dark:text-amber-300 dark:border-amber-800",
    in_progress:
      "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900 dark:text-purple-300 dark:border-purple-800",
    abandoned:
      "bg-gray-100 text-gray-500 border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700",
  };

  const urgency =
    c.status === "overdue"
      ? "border-l-red-500"
      : c.due_date && new Date(c.due_date) < new Date(Date.now() + 48 * 3600000)
        ? "border-l-amber-400"
        : "border-l-gray-200 dark:border-l-gray-700";

  const isTerminal = c.status === "completed" || c.status === "abandoned";

  return (
    <div
      className={`relative overflow-visible bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 border-l-4 ${urgency} p-4 transition-opacity ${isTerminal ? "opacity-60" : ""}`}
    >
      {/* Top section */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className={`font-medium ${isTerminal ? "line-through" : ""}`}>
            {c.summary}
          </p>
          {c.source_subject && (
            <div className="mt-1.5 flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-300 min-w-0">
              <Mail size={13} className="shrink-0 text-gray-400 dark:text-gray-500" />
              <span className="truncate font-medium">{c.source_subject}</span>
            </div>
          )}
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {c.owner_is_self
              ? `You → ${c.target_email || "general"}`
              : `${c.owner_email} → You`}
          </p>
          {c.source_sender && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Source: {c.source_sender}
            </p>
          )}
          {c.account_email && (
            <div className="mt-2">
              <span className="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-800 px-2 py-0.5 text-[11px] text-gray-500 dark:text-gray-400">
                {c.account_email}
              </span>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-gray-400 dark:text-gray-500">
            {c.due_date && (
              <span>Due: {new Date(c.due_date).toLocaleDateString()}</span>
            )}
            <span>Confidence: {Math.round(c.confidence_score * 100)}%</span>
            {c.commitment_type && (
              <span className="bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                {c.commitment_type}
              </span>
            )}
          </div>
        </div>
        <span
          className={`text-xs px-2 py-1 rounded-full font-medium border whitespace-nowrap ${statusColors[c.status] ?? "bg-gray-100 dark:bg-gray-800"}`}
        >
          {c.status}
        </span>
      </div>

      {/* Actions */}
      <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            {isTerminal ? (
              <button
                onClick={() => onStatusChange(c.id, "confirmed")}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                <Undo2 size={12} />
                Reopen
              </button>
            ) : (
              <button
                onClick={() => onStatusChange(c.id, "completed")}
                className="text-xs px-3 py-1.5 bg-green-50 text-green-700 dark:bg-green-900 dark:text-green-300 rounded-md hover:bg-green-100 dark:hover:bg-green-800 transition-colors"
              >
                Mark Complete
              </button>
            )}

            {canAddToCalendar && (
              <button
                onClick={async () => {
                  setCreatingEvent(true);
                  try {
                    const result = await api.createCalendarEvent(c.id);
                    setCalendarCreated(true);
                    setCalendarLink(result.event_link || null);
                    toast.success("Calendar event created!");
                    window.dispatchEvent(new Event("commitgraph:refresh"));
                  } catch (err: any) {
                    toast.error(
                      err.response?.data?.detail || "Failed to create event",
                    );
                  } finally {
                    setCreatingEvent(false);
                  }
                }}
                disabled={creatingEvent}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-green-50 text-green-700 dark:bg-green-900 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-800 transition-colors disabled:opacity-50"
              >
                <CalendarPlus size={12} />
                {creatingEvent ? "Creating..." : "Add to Calendar"}
              </button>
            )}

            {calendarCreated && calendarLink && (
              <a
                href={calendarLink}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-emerald-50 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-800 transition-colors"
              >
                <CalendarCheck size={12} />
                Open Calendar
              </a>
            )}

            {calendarCreated && (
              <button
                onClick={async () => {
                  setRemovingEvent(true);
                  try {
                    await api.deleteCalendarEvent(c.id);
                    setCalendarCreated(false);
                    setCalendarLink(null);
                    toast.success("Calendar event removed");
                    window.dispatchEvent(new Event("commitgraph:refresh"));
                  } catch (err: any) {
                    toast.error(
                      err.response?.data?.detail || "Failed to remove event",
                    );
                  } finally {
                    setRemovingEvent(false);
                  }
                }}
                disabled={removingEvent}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-red-50 text-red-700 dark:bg-red-900 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-800 transition-colors disabled:opacity-50"
              >
                <CalendarCheck size={12} />
                {removingEvent ? "Removing..." : "Remove from Calendar"}
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={toggleEmail}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md transition-colors ${
                showEmail
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
              }`}
            >
              {loadingEvidence ? (
                "Loading..."
              ) : showEmail ? (
                <>
                  <EyeOff size={12} /> Hide email
                </>
              ) : (
                <>
                  <Eye size={12} /> View email
                </>
              )}
            </button>

            <div className="relative">
              <button
                onClick={() => setShowMenu((v) => !v)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 transition-colors"
              >
                <MoreHorizontal size={12} />
                More
              </button>

              {showMenu && (
                <div className="absolute right-0 bottom-full mb-2 w-44 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-xl z-50 py-1">
                  <button
                    onClick={() => {
                      setShowMenu(false);
                      onEdit();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  >
                    <Pencil size={14} />
                    Edit
                  </button>

                  {!isTerminal && (
                    <button
                      onClick={() => {
                        setShowMenu(false);
                        onStatusChange(c.id, "abandoned");
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-red-600 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
                    >
                      <X size={14} />
                      Abandon
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Email panel */}
      {showEmail && evidence && (
        <div className="mt-3 space-y-3">
          {evidence.length === 0 ? (
            <p className="text-sm text-gray-400 dark:text-gray-500 py-2">
              No evidence linked.
            </p>
          ) : (
            evidence.map((e: any) => <EvidenceCard key={e.id} evidence={e} />)
          )}
        </div>
      )}
    </div>
  );
}

function EditCommitmentModal({
  commitment,
  onClose,
  onSave,
}: {
  commitment: any;
  onClose: () => void;
  onSave: (id: string, body: any) => Promise<void>;
}) {
  const [summary, setSummary] = useState(commitment.summary || "");
  const [dueDate, setDueDate] = useState(
    commitment.due_date
      ? new Date(commitment.due_date).toISOString().slice(0, 10)
      : "",
  );
  const [status, setStatus] = useState(commitment.status || "confirmed");
  const [saving, setSaving] = useState(false);

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="w-full max-w-lg rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-800">
          <h3 className="text-lg font-semibold">Edit Commitment</h3>
          <button
            onClick={onClose}
            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1.5">Summary</label>
            <input
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 px-3 py-2 text-sm"
              placeholder="Commitment summary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Due Date</label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 px-3 py-2 text-sm"
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Leave blank to remove the due date.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 px-3 py-2 text-sm"
            >
              <option value="confirmed">confirmed</option>
              <option value="in_progress">in progress</option>
              <option value="completed">completed</option>
              <option value="abandoned">abandoned</option>
              <option value="delegated">delegated</option>
            </select>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={async () => {
              setSaving(true);
              try {
                await onSave(commitment.id, {
                  summary,
                  due_date: dueDate || null,
                  status,
                });
                toast.success("Commitment updated");
              } catch (err: any) {
                toast.error(
                  err.response?.data?.detail || "Failed to update commitment",
                );
              } finally {
                setSaving(false);
              }
            }}
            disabled={saving}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Evidence card
// ---------------------------------------------------------------------------
function EvidenceCard({ evidence: e }: { evidence: any }) {
  const [showBody, setShowBody] = useState(false);
  // const [showReply, setShowReply] = useState(false);

  const typeLabels: Record<string, { label: string; color: string }> = {
    origin: {
      label: "Source",
      color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    },
    update: {
      label: "Follow-up",
      color:
        "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    },
    completion_signal: {
      label: "Completed",
      color:
        "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    },
    calendar_link: {
      label: "Calendar",
      color:
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
    },
    follow_up: {
      label: "Follow-up",
      color:
        "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    },
  };

  const typeInfo = typeLabels[e.evidence_type] || {
    label: e.evidence_type,
    color: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  };

  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2">
        {e.item_type === "calendar_event" ? (
          <Calendar size={14} className="text-green-500 shrink-0" />
        ) : (
          <Mail size={14} className="text-blue-500 shrink-0" />
        )}
        <span
          className={`text-xs px-1.5 py-0.5 rounded font-medium ${typeInfo.color}`}
        >
          {typeInfo.label}
        </span>
        {e.sent_at && (
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {new Date(e.sent_at).toLocaleString()}
          </span>
        )}
      </div>

      {e.subject && (
        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
          {e.subject}
        </p>
      )}
      {e.sender_email && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          {e.sender_name
            ? `${e.sender_name} <${e.sender_email}>`
            : e.sender_email}
        </p>
      )}

      {e.extracted_snippet && (
        <div className="mt-2 px-3 py-2 bg-blue-50 dark:bg-blue-950 border-l-2 border-blue-400 dark:border-blue-600 rounded-r text-sm text-gray-700 dark:text-gray-300 italic">
          &ldquo;{e.extracted_snippet}&rdquo;
        </div>
      )}

      {e.body_text && (
        <>
          <button
            onClick={() => setShowBody(!showBody)}
            className={`mt-3 flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md transition-colors ${
              showBody
                ? "bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                : "bg-gray-200 text-gray-600 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-400 dark:hover:bg-gray-600"
            }`}
          >
            {showBody ? (
              <>
                <EyeOff size={11} /> Hide full email
              </>
            ) : (
              <>
                <Eye size={11} /> Show full email
              </>
            )}
          </button>
          {showBody && (
            <div className="mt-2 p-3 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700 text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap max-h-64 overflow-y-auto">
              {e.body_text}
            </div>
          )}
        </>
      )}

      {/* Reply button */}
      {/* {e.sender_email && (
        <>
          {!showReply ? (
            <button
              onClick={() => setShowReply(true)}
              className="mt-2 flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
            >
              <Send size={11} />
              Reply
            </button>
          ) : (
            <EmailComposer
              to={e.sender_email}
              subject={e.subject || ""}
              threadId={e.thread_id}
              accountEmail={e.sender_email}
              onClose={() => setShowReply(false)}
            />
          )}
        </>
      )} */}
    </div>
  );
}
