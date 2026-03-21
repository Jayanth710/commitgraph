"use client";
import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import { api } from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import { CheckCircle } from "lucide-react";
import PageTransition from "@/components/PageTransition";

export default function ReviewPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

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
      await api.reviewAction(reviewId, action);
      setItems((prev) => prev.filter((item) => item.id !== reviewId));
      window.dispatchEvent(new Event("commitgraph:refresh"));
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <PageSkeleton />;

  return (
    <PageTransition>
    <>
        <main className="flex-1 p-8">
          <h2 className="text-2xl font-bold mb-6">Review Queue</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
            Low-confidence detections that need your review. Confirm if it's a real commitment, reject if it's not.
          </p>

          {loading ? (
            <p className="text-gray-500 dark:text-gray-400">Loading...</p>
          ) : items.length === 0 ? (
            <EmptyState
              icon={CheckCircle}
              title="Queue is empty"
              description="All commitments are above the confidence threshold. Nice!"
            />
          ) : (
            <div className="space-y-4">
              {items.map((item: any) => (
                <ReviewCard key={item.id} item={item} onAction={handleAction} />
              ))}
            </div>
          )}
        </main>
    </>
    </PageTransition>
  );
}

function ReviewCard({ item, onAction }: { item: any; onAction: (id: string, action: string) => void }) {
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
          <p className="text-xs text-gray-400 dark:text-gray-500 mb-1">From: {item.source_sender} · {item.source_subject}</p>
          <p className="text-gray-600 dark:text-gray-300 line-clamp-3">{item.raw_text}</p>
        </div>
      )}

      <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
        Reason: {item.reason} · Suggested: {item.suggested_action}
      </p>

      <div className="flex gap-2">
        <button
          onClick={() => onAction(item.id, "confirm")}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
        >
          Confirm
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