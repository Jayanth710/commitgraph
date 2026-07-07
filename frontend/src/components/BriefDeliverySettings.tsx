"use client";
import { useEffect, useState } from "react";
import { toast } from "react-toastify";

import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import { ListSkeleton } from "@/components/Skeleton";
import type { BriefDeliveryPreference, BriefDeliveryRun } from "@/lib/types";

export default function BriefDeliverySettings() {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [deliveryPreference, setDeliveryPreference] =
    useState<BriefDeliveryPreference | null>(null);
  const [deliveryRuns, setDeliveryRuns] = useState<BriefDeliveryRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingDelivery, setSavingDelivery] = useState(false);
  const [sendingBriefNow, setSendingBriefNow] = useState<"morning" | "night" | null>(
    null,
  );

  useEffect(() => {
    async function load() {
      try {
        const [accountsData, preferenceData, deliveryData] = await Promise.all([
          api.getAccounts(),
          api.getBriefDeliveryPreferences(),
          api.getBriefDeliveryRuns(),
        ]);
        setAccounts(accountsData.accounts || []);
        setDeliveryPreference(preferenceData.preference);
        setDeliveryRuns(deliveryData.runs || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const buildDeliveryPreferencePayload = (preference: BriefDeliveryPreference) => ({
    channel: preference.channel,
    destination:
      preference.destination?.trim() ||
      (preference.channel === "email" ? user?.email || null : null),
    timezone: preference.timezone?.trim() || "America/Denver",
    morning_enabled: preference.morning_enabled,
    morning_time: (preference.morning_time || "08:00").slice(0, 5),
    night_enabled: preference.night_enabled,
    night_time: (preference.night_time || "20:00").slice(0, 5),
    sender_account_id: preference.sender_account_id || null,
    account_id: preference.account_id || null,
    is_active: preference.is_active,
    deadline_reminders_enabled: preference.deadline_reminders_enabled,
  });

  const handleSaveDeliveryPreference = async () => {
    if (!deliveryPreference) return;
    setSavingDelivery(true);
    try {
      const result = await api.updateBriefDeliveryPreferences(
        buildDeliveryPreferencePayload(deliveryPreference),
      );
      setDeliveryPreference(result.preference);
      toast.success("Brief delivery preferences saved.");
    } catch (err: any) {
      console.error(err);
      toast.error(
        err.response?.data?.detail || "Failed to save brief delivery preferences.",
      );
    } finally {
      setSavingDelivery(false);
    }
  };

  const handleSendBriefNow = async (briefType: "morning" | "night") => {
    if (!deliveryPreference) return;

    const gmailAccounts = accounts.filter((account) => account.provider === "gmail");
    if (deliveryPreference.channel === "email" && gmailAccounts.length === 0) {
      toast.error("Connect a Gmail account before sending email briefs.");
      return;
    }

    setSendingBriefNow(briefType);
    try {
      const preferenceResult = await api.updateBriefDeliveryPreferences(
        buildDeliveryPreferencePayload(deliveryPreference),
      );
      setDeliveryPreference(preferenceResult.preference);
      await api.sendBriefNow({ brief_type: briefType });
      const deliveryData = await api.getBriefDeliveryRuns();
      setDeliveryRuns(deliveryData.runs || []);
      toast.success(`${briefType === "morning" ? "Morning" : "Night"} brief sent.`);
    } catch (err: any) {
      console.error(err);
      toast.error(err.response?.data?.detail || "Failed to send brief.");
    } finally {
      setSendingBriefNow(null);
    }
  };

  return (
    <>
      <h3 className="text-lg font-semibold mb-4">Schedule &amp; Delivery</h3>
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5 mb-8">
        {loading || !deliveryPreference ? (
          <ListSkeleton count={2} />
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Channel</label>
                <select
                  value={deliveryPreference.channel}
                  onChange={(e) =>
                    setDeliveryPreference((prev) =>
                      prev ? { ...prev, channel: e.target.value as "email" | "sms" } : prev,
                    )
                  }
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm"
                >
                  <option value="email">Email</option>
                  <option value="sms">Phone / SMS</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  {deliveryPreference.channel === "sms" ? "Phone number" : "Email destination"}
                </label>
                <input
                  value={deliveryPreference.destination || ""}
                  onChange={(e) =>
                    setDeliveryPreference((prev) =>
                      prev ? { ...prev, destination: e.target.value } : prev,
                    )
                  }
                  placeholder={
                    deliveryPreference.channel === "sms"
                      ? "+15551234567"
                      : user?.email || "you@example.com"
                  }
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Timezone</label>
                <input
                  value={deliveryPreference.timezone}
                  onChange={(e) =>
                    setDeliveryPreference((prev) =>
                      prev ? { ...prev, timezone: e.target.value } : prev,
                    )
                  }
                  placeholder="America/Denver"
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Brief scope</label>
                <select
                  value={deliveryPreference.account_id || ""}
                  onChange={(e) =>
                    setDeliveryPreference((prev) =>
                      prev ? { ...prev, account_id: e.target.value || null } : prev,
                    )
                  }
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm"
                >
                  <option value="">All accounts</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.email_address}
                    </option>
                  ))}
                </select>
              </div>

              <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-medium">Morning brief</p>
                  <input
                    type="checkbox"
                    checked={deliveryPreference.morning_enabled}
                    onChange={(e) =>
                      setDeliveryPreference((prev) =>
                        prev ? { ...prev, morning_enabled: e.target.checked } : prev,
                      )
                    }
                  />
                </div>
                <input
                  type="time"
                  value={(deliveryPreference.morning_time || "08:00").slice(0, 5)}
                  onChange={(e) =>
                    setDeliveryPreference((prev) =>
                      prev ? { ...prev, morning_time: e.target.value } : prev,
                    )
                  }
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm"
                />
              </div>

              <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-medium">Night brief</p>
                  <input
                    type="checkbox"
                    checked={deliveryPreference.night_enabled}
                    onChange={(e) =>
                      setDeliveryPreference((prev) =>
                        prev ? { ...prev, night_enabled: e.target.checked } : prev,
                      )
                    }
                  />
                </div>
                <input
                  type="time"
                  value={(deliveryPreference.night_time || "20:00").slice(0, 5)}
                  onChange={(e) =>
                    setDeliveryPreference((prev) =>
                      prev ? { ...prev, night_time: e.target.value } : prev,
                    )
                  }
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Sender Gmail account</label>
                <select
                  value={deliveryPreference.sender_account_id || ""}
                  onChange={(e) =>
                    setDeliveryPreference((prev) =>
                      prev ? { ...prev, sender_account_id: e.target.value || null } : prev,
                    )
                  }
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm"
                >
                  <option value="">Auto-select first Gmail account</option>
                  {accounts
                    .filter((a) => a.provider === "gmail")
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.email_address}
                      </option>
                    ))}
                </select>
              </div>

              <div className="flex items-end">
                <label className="flex items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    checked={deliveryPreference.is_active}
                    onChange={(e) =>
                      setDeliveryPreference((prev) =>
                        prev ? { ...prev, is_active: e.target.checked } : prev,
                      )
                    }
                  />
                  Delivery active
                </label>
              </div>

              <div className="md:col-span-2 rounded-lg border border-gray-200 dark:border-gray-800 p-4">
                <label className="flex items-center gap-3 text-sm font-medium">
                  <input
                    type="checkbox"
                    checked={deliveryPreference.deadline_reminders_enabled}
                    onChange={(e) =>
                      setDeliveryPreference((prev) =>
                        prev
                          ? { ...prev, deadline_reminders_enabled: e.target.checked }
                          : prev,
                      )
                    }
                  />
                  Deadline reminders
                </label>
                <p className="mt-1.5 ml-7 text-xs text-gray-500 dark:text-gray-400">
                  Email me ~1 day and ~3 hours before a commitment I owe is due — earlier
                  than the calendar&apos;s last-minute popup.
                </p>
              </div>
            </div>

            <div className="mt-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Scheduled briefs are sent by the background scheduler at the times above
                (in your timezone). SMS requires Twilio configured on the backend; email
                uses a connected Gmail account.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleSendBriefNow("morning")}
                  disabled={sendingBriefNow !== null}
                  className="px-4 py-2 rounded-md bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200 text-sm hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50"
                >
                  {sendingBriefNow === "morning" ? "Sending..." : "Send Morning Now"}
                </button>
                <button
                  onClick={() => handleSendBriefNow("night")}
                  disabled={sendingBriefNow !== null}
                  className="px-4 py-2 rounded-md bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200 text-sm hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50"
                >
                  {sendingBriefNow === "night" ? "Sending..." : "Send Night Now"}
                </button>
                <button
                  onClick={handleSaveDeliveryPreference}
                  disabled={savingDelivery}
                  className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  {savingDelivery ? "Saving..." : "Save preferences"}
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      <h3 className="text-lg font-semibold mb-4">Recent Brief Deliveries</h3>
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5 mb-8">
        {loading ? (
          <ListSkeleton count={2} />
        ) : deliveryRuns.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            No deliveries yet. Save your preferences and let the scheduler send the next
            brief.
          </p>
        ) : (
          <div className="space-y-3">
            {deliveryRuns.map((run) => (
              <div
                key={run.id}
                className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 rounded-md border border-gray-200 dark:border-gray-800 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium">
                    {run.brief_type} brief · {run.channel} ·{" "}
                    {run.destination || "default destination"}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {new Date(run.brief_date).toLocaleDateString()} ·{" "}
                    {run.sent_at ? new Date(run.sent_at).toLocaleString() : "Not sent yet"}
                  </p>
                </div>
                <div className="text-right">
                  <span className="inline-flex rounded-full px-2 py-1 text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
                    {run.status}
                  </span>
                  {run.error_message && (
                    <p className="text-xs text-red-500 mt-1">{run.error_message}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
