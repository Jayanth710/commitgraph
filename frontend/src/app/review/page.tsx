"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import { CheckCircle, Pencil, Merge } from "lucide-react";
import PageTransition from "@/components/PageTransition";
import type { ReviewItem } from "@/lib/types";

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingItem, setEditingItem] = useState<ReviewItem | null>(null);
  const [mergingItem, setMergingItem] = useState<ReviewItem | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getReviewQueue();
        setItems(data.review_items);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleAction = async (reviewId: string, action: string) => {
    try {
      await api.reviewAction(reviewId, { action });
      setItems((prev) => prev.filter((item) => item.id !== reviewId));
      window.dispatchEvent(new Event("commitgraph:refresh"));
    } catch (err) {
      console.error(err);
    }
  };

  const handleEditSave = async (
    item: ReviewItem,
    body: { summary: string; due_date: string | null; status: string },
  ) => {
    await api.reviewAction(item.id, {
      action: "edit",
      ...body,
    });
    setItems((prev) => prev.filter((x) => x.id !== item.id));
    setEditingItem(null);
    window.dispatchEvent(new Event("commitgraph:refresh"));
  };

  const handleMergeSave = async (item: ReviewItem, targetCommitmentId: string) => {
    await api.reviewAction(item.id, {
      action: "merge",
      merge_into_commitment_id: targetCommitmentId,
    });
    setItems((prev) => prev.filter((x) => x.id !== item.id));
    setMergingItem(null);
    window.dispatchEvent(new Event("commitgraph:refresh"));
  };

  if (loading) return <PageSkeleton />;

  return (
    <PageTransition>
      <>
        <main className="flex-1 p-8">
          <h2 className="text-2xl font-bold mb-6">Review Queue</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
            Low-confidence detections that need your review. Confirm if it&apos;s a real commitment, reject if it&apos;s not.
          </p>

          {items.length === 0 ? (
            <EmptyState
              icon={CheckCircle}
              title="Queue is empty"
              description="All commitments are above the confidence threshold. Nice!"
            />
          ) : (
            <div className="space-y-4">
              {items.map((item) => (
                <ReviewCard
                  key={item.id}
                  item={item}
                  onAction={handleAction}
                  onEdit={() => setEditingItem(item)}
                  onMerge={() => setMergingItem(item)}
                />
              ))}
            </div>
          )}
        </main>

        {editingItem && (
          <EditReviewModal
            item={editingItem}
            onClose={() => setEditingItem(null)}
            onSave={handleEditSave}
          />
        )}

        {mergingItem && (
          <MergeReviewModal
            item={mergingItem}
            onClose={() => setMergingItem(null)}
            onSave={handleMergeSave}
          />
        )}
      </>
    </PageTransition>
  );
}

function ReviewCard({
  item,
  onAction,
  onEdit,
  onMerge,
}: {
  item: ReviewItem;
  onAction: (id: string, action: string) => void;
  onEdit: () => void;
  onMerge: () => void;
}) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-amber-200 dark:border-amber-800 p-5">
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="font-medium">{item.summary}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {item.direction === "outbound" ? "You committed to" : "Someone committed to you"}
            {item.target_email && ` · ${item.target_email}`}
          </p>
        </div>
        <span className="text-xs px-2 py-1 bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300 rounded-full">
          {Math.round(item.confidence_score * 100)}% confidence
        </span>
      </div>

      {item.source_subject && (
        <div className="bg-gray-50 dark:bg-gray-800 rounded-md p-3 mb-3 text-sm">
          <p className="text-xs text-gray-400 dark:text-gray-500 mb-1">
            From: {item.source_sender} · {item.source_subject}
          </p>
          <p className="text-gray-600 dark:text-gray-300 line-clamp-3">{item.raw_text}</p>
        </div>
      )}

      <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
        Reason: {item.reason} · Suggested: {item.suggested_action}
      </p>

      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => onAction(item.id, "confirm")}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
        >
          Confirm
        </button>
        <button
          onClick={onEdit}
          className="px-4 py-2 bg-blue-50 text-blue-600 dark:bg-blue-900 dark:text-blue-300 text-sm rounded-md hover:bg-blue-100 dark:hover:bg-blue-800 transition-colors flex items-center gap-1.5"
        >
          <Pencil size={14} />
          Edit
        </button>
        <button
          onClick={onMerge}
          className="px-4 py-2 bg-purple-50 text-purple-600 dark:bg-purple-900 dark:text-purple-300 text-sm rounded-md hover:bg-purple-100 dark:hover:bg-purple-800 transition-colors flex items-center gap-1.5"
        >
          <Merge size={14} />
          Merge
        </button>
        <button
          onClick={() => onAction(item.id, "reject")}
          className="px-4 py-2 bg-red-50 text-red-600 dark:bg-red-900 dark:text-red-300 text-sm rounded-md hover:bg-red-100 dark:hover:bg-red-800 transition-colors"
        >
          Reject
        </button>
        <button
          onClick={() => onAction(item.id, "dismiss")}
          className="px-4 py-2 bg-gray-50 text-gray-500 dark:bg-gray-800 dark:text-gray-400 text-sm rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

function EditReviewModal({
  item,
  onClose,
  onSave,
}: {
  item: ReviewItem;
  onClose: () => void;
  onSave: (item: ReviewItem, body: { summary: string; due_date: string | null; status: string }) => Promise<void>;
}) {
  const [summary, setSummary] = useState(item.summary);
  const [dueDate, setDueDate] = useState(
    item.due_date ? new Date(item.due_date).toISOString().slice(0, 10) : "",
  );
  const [status, setStatus] = useState("confirmed");
  const [saving, setSaving] = useState(false);

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="w-full max-w-lg rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-800">
          <h3 className="text-lg font-semibold">Edit Review Item</h3>
          <button onClick={onClose} className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800">
            ×
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1.5">Summary</label>
            <input
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 px-3 py-2 text-sm"
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
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 px-3 py-2 text-sm"
            >
              <option value="confirmed">confirmed</option>
              <option value="in_progress">in_progress</option>
              <option value="completed">completed</option>
              <option value="abandoned">abandoned</option>
              <option value="delegated">delegated</option>
            </select>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300"
          >
            Cancel
          </button>
          <button
            onClick={async () => {
              setSaving(true);
              try {
                await onSave(item, {
                  summary: summary.trim(),
                  due_date: dueDate || null,
                  status,
                });
              } finally {
                setSaving(false);
              }
            }}
            disabled={saving}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

function MergeReviewModal({
  item,
  onClose,
  onSave,
}: {
  item: ReviewItem;
  onClose: () => void;
  onSave: (item: ReviewItem, targetCommitmentId: string) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Array<{ id: string; summary: string }>>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  async function search() {
    setLoading(true);
    try {
      const data = await api.searchCommitments(`q=${encodeURIComponent(query)}&limit=10`);
      setResults(
        data.commitments
          .filter((c) => c.id !== item.commitment_id)
          .map((c) => ({ id: c.id, summary: c.summary })),
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="w-full max-w-lg rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-800">
          <h3 className="text-lg font-semibold">Merge Review Item</h3>
          <button onClick={onClose} className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800">
            ×
          </button>
        </div>

        <div className="p-4 space-y-4">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search target commitment"
            className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 px-3 py-2 text-sm"
          />
          <button
            onClick={search}
            disabled={!query.trim() || loading}
            className="px-4 py-2 text-sm rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50"
          >
            {loading ? "Searching..." : "Search"}
          </button>

          <div className="space-y-2 max-h-60 overflow-y-auto">
            {results.map((r) => (
              <label
                key={r.id}
                className="flex items-center gap-2 p-3 rounded-lg border border-gray-200 dark:border-gray-700"
              >
                <input
                  type="radio"
                  name="merge_target"
                  value={r.id}
                  checked={selectedId === r.id}
                  onChange={() => setSelectedId(r.id)}
                />
                <span className="text-sm">{r.summary}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300"
          >
            Cancel
          </button>
          <button
            onClick={async () => {
              if (!selectedId) return;
              setSaving(true);
              try {
                await onSave(item, selectedId);
              } finally {
                setSaving(false);
              }
            }}
            disabled={!selectedId || saving}
            className="px-4 py-2 text-sm rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50"
          >
            {saving ? "Merging..." : "Merge"}
          </button>
        </div>
      </div>
    </div>
  );
}