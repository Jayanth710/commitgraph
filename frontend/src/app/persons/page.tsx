"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ListSkeleton } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import PageTransition from "@/components/PageTransition";
import { Users } from "lucide-react";
import { useAccountFilter } from "@/components/AccountFilterProvider";

export default function PersonsPage() {
  const [persons, setPersons] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const {activeAccountId} = useAccountFilter()

  useEffect(() => {
        async function load() {
      try {
        const params = new URLSearchParams();
        if (activeAccountId) params.set("account_id", activeAccountId);
        const data = await api.getPersons(params.toString());
        setPersons(data.persons);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [activeAccountId]);

  if (loading) return <ListSkeleton count={4} />;

  return (
    <PageTransition>
      <>
        <h2 className="text-2xl font-bold mb-6">People</h2>

        {persons.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No people found"
            description="People are discovered automatically from your email conversations."
          />
        ) : (
          <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden">
            {persons.map((p: any) => (
              <div key={p.id} className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-800 last:border-0">
                <div className="flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-medium ${
                    p.is_self ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                  }`}>
                    {(p.display_name || p.email_addresses?.[0] || "?")[0].toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium">
                      {p.display_name || p.email_addresses?.[0]}
                      {p.is_self && <span className="ml-2 text-xs text-blue-500">(you)</span>}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">{p.email_addresses?.join(", ")}</p>
                  </div>
                </div>
                <span className="text-sm text-gray-500 dark:text-gray-400">{p.commitment_count} commitments</span>
              </div>
            ))}
          </div>
        )}
      </>
    </PageTransition>
  );
}