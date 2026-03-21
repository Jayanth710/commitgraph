"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Mail, Calendar, Inbox } from "lucide-react";
import { PageSkeleton } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import PageTransition from "@/components/PageTransition";

export default function TimelinePage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getTimeline("limit=100");
        setItems(data.items);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const providerColors: Record<string, string> = {
    gmail: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    outlook:
      "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    gcal: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  };

  if (loading) return <PageSkeleton />;

  return (
    <PageTransition>
      <>
        <main className="flex-1 p-8">
          <h2 className="text-2xl font-bold mb-6">Timeline</h2>

          {loading ? (
            <p className="text-gray-500 dark:text-gray-400">Loading...</p>
          ) : items.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title="No events yet"
              description="Connect an email account and events will appear here."
              action={{ label: "Connect email", href: "/settings" }}
            />
          ) : (
            <div className="space-y-2">
              {items.map((item: any) => (
                <div
                  key={item.id}
                  className="flex items-start gap-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4"
                >
                  <div className="mt-0.5">
                    {item.item_type === "calendar_event" ? (
                      <Calendar size={18} className="text-green-500" />
                    ) : (
                      <Mail size={18} className="text-blue-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">
                      {item.subject || "(no subject)"}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      {item.sender_name || item.sender_email}
                      {item.sent_at &&
                        ` · ${new Date(item.sent_at).toLocaleString()}`}
                      {item.event_start &&
                        ` · ${new Date(item.event_start).toLocaleString()}`}
                    </p>
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${providerColors[item.provider] ?? "bg-gray-100 dark:bg-gray-800"}`}
                  >
                    {item.provider}
                  </span>
                </div>
              ))}
            </div>
          )}
        </main>
      </>
    </PageTransition>
  );
}
