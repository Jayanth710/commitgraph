"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import { clearAuth } from "@/lib/auth";
import { ListSkeleton } from "@/components/Skeleton";
import { Unlink, LogOut, Trash2, AlertTriangle } from "lucide-react";
import { toast } from "react-toastify";
import PageTransition from "@/components/PageTransition";
import type { BriefDeliveryPreference, BriefDeliveryRun } from "@/lib/types";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirmDisconnect, setConfirmDisconnect] = useState<string | null>(
    null,
  );
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deliveryPreference, setDeliveryPreference] = useState<BriefDeliveryPreference | null>(null);
  const [deliveryRuns, setDeliveryRuns] = useState<BriefDeliveryRun[]>([]);
  const [savingDelivery, setSavingDelivery] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getAccounts();
        setAccounts(data.accounts);
        const [preferenceData, deliveryData] = await Promise.all([
          api.getBriefDeliveryPreferences(),
          api.getBriefDeliveryRuns(),
        ]);
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

  const handleDisconnect = async (accountId: string) => {
    setDisconnecting(true);
    try {
      await api.disconnectAccount(accountId);
      setAccounts((prev) => prev.filter((a) => a.id !== accountId));
      setConfirmDisconnect(null);
      toast.success("Account disconnected.");
    } catch (err) {
      console.error(err);
      toast.error("Failed to disconnect account.");
    } finally {
      setDisconnecting(false);
    }
  };

  const handleDeleteUser = async () => {
    setDeleting(true);
    try {
      await api.deleteUser();
      toast.success("Account deleted.");
      clearAuth();
      window.location.href = "/login";
    } catch (err) {
      console.error(err);
      toast.error("Failed to delete account.");
      setDeleting(false);
    }
  };

  const statusColors: Record<string, string> = {
    active: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    degraded:
      "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
    disconnected: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    error: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  };

  const providerLabels: Record<string, { label: string; color: string }> = {
    gmail: { label: "Gmail", color: "text-blue-600 dark:text-blue-400" },
    outlook: {
      label: "Outlook",
      color: "text-purple-600 dark:text-purple-400",
    },
    gcal: { label: "Calendar", color: "text-green-600 dark:text-green-400" },
  };

  const handleSaveDeliveryPreference = async () => {
    if (!deliveryPreference) return;
    setSavingDelivery(true);
    try {
      const result = await api.updateBriefDeliveryPreferences({
        channel: deliveryPreference.channel,
        destination: deliveryPreference.destination,
        timezone: deliveryPreference.timezone,
        morning_enabled: deliveryPreference.morning_enabled,
        morning_time: deliveryPreference.morning_time,
        night_enabled: deliveryPreference.night_enabled,
        night_time: deliveryPreference.night_time,
        sender_account_id: deliveryPreference.sender_account_id,
        account_id: deliveryPreference.account_id,
        is_active: deliveryPreference.is_active,
      });
      setDeliveryPreference(result.preference);
      toast.success("Brief delivery preferences saved.");
    } catch (err) {
      console.error(err);
      toast.error("Failed to save brief delivery preferences.");
    } finally {
      setSavingDelivery(false);
    }
  };

  return (
    <PageTransition>
      <>
        <h2 className="text-2xl font-bold mb-6">Settings</h2>

        {/* Profile section */}
        <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5 mb-8">
          <h3 className="text-lg font-semibold mb-4">Profile</h3>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 flex items-center justify-center text-lg font-semibold">
              {(user?.name || user?.email || "?")
                .split(" ")
                .map((w: string) => w[0])
                .slice(0, 2)
                .join("")
                .toUpperCase()}
            </div>
            <div>
              <p className="font-medium">{user?.name || "No name set"}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {user?.email}
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                Signed in via{" "}
                {user?.auth_provider === "google" ? "Google" : "email"}
              </p>
            </div>
          </div>
        </div>

        {/* Connected accounts */}
        <h3 className="text-lg font-semibold mb-4">Connected Accounts</h3>
        <div className="space-y-3 mb-8">
          {loading ? (
            <ListSkeleton count={2} />
          ) : accounts.length === 0 ? (
            <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6 text-center">
              <p className="text-gray-500 dark:text-gray-400 mb-3">
                No email accounts connected yet.
              </p>
              <a
                href={`${apiUrl}/auth/google/start?user_id=${user?.id || ""}`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
              >
                Connect Gmail
              </a>
            </div>
          ) : (
            accounts.map((a: any) => {
              const provider = providerLabels[a.provider] || {
                label: a.provider,
                color: "text-gray-600",
              };
              const isConfirming = confirmDisconnect === a.id;

              return (
                <div
                  key={a.id}
                  className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-sm">{a.email_address}</p>
                        <span
                          className={`text-xs font-medium ${provider.color}`}
                        >
                          {provider.label}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                        Last sync:{" "}
                        {a.last_sync_at
                          ? new Date(a.last_sync_at).toLocaleString()
                          : "never"}
                        {a.watch_expiry &&
                          ` · Watch expires: ${new Date(a.watch_expiry).toLocaleString()}`}
                      </p>
                    </div>
                    <span
                      className={`text-xs px-2 py-1 rounded-full font-medium ${statusColors[a.sync_status] ?? "bg-gray-100 dark:bg-gray-800"}`}
                    >
                      {a.sync_status}
                    </span>
                  </div>

                  {isConfirming ? (
                    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                      <p className="text-sm text-red-600 dark:text-red-400 mb-3">
                        This will remove the account and all its emails,
                        commitments, and evidence. This cannot be undone.
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleDisconnect(a.id)}
                          disabled={disconnecting}
                          className="text-xs px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors disabled:opacity-50"
                        >
                          {disconnecting
                            ? "Disconnecting..."
                            : "Yes, disconnect"}
                        </button>
                        <button
                          onClick={() => setConfirmDisconnect(null)}
                          className="text-xs px-4 py-2 bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 flex justify-end gap-2">
                      {a.provider === "gmail" && (
                        <button
                          onClick={async () => {
                            try {
                              await api.startGmailWatch(a.email_address);
                              toast.success("Gmail watch started!");
                            } catch (err: any) {
                              toast.error(err.response?.data?.detail || "Failed to start watch");
                            }
                          }}
                          className="flex items-center gap-1.5 text-xs px-3 py-1.5 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950 rounded-md hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
                        >
                          Start Watch
                        </button>
                      )}
                      <button
                        onClick={() => setConfirmDisconnect(a.id)}
                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-950 rounded-md hover:bg-red-100 dark:hover:bg-red-900 transition-colors"
                      >
                        <Unlink size={12} />
                        Disconnect
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Connect new account */}
        {accounts.length > 0 && (
          <>
            <h3 className="text-lg font-semibold mb-4">Connect New Account</h3>
            <div className="flex gap-3 mb-8">
              <a
                href={`${apiUrl}/auth/google/start?user_id=${user?.id || ""}`}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
              >
                Connect Gmail
              </a>
              <a
                href={`${apiUrl}/auth/microsoft/start`}
                className="px-4 py-2 bg-purple-600 text-white text-sm rounded-md hover:bg-purple-700 transition-colors"
              >
                Connect Outlook
              </a>
            </div>
          </>
        )}

        <h3 className="text-lg font-semibold mb-4">Daily Brief Delivery</h3>
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
              </div>

              <div className="mt-4 flex items-center justify-between gap-4">
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  SMS delivery requires Twilio to be configured on the backend. Email delivery uses a connected Gmail account.
                </p>
                <button
                  onClick={handleSaveDeliveryPreference}
                  disabled={savingDelivery}
                  className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  {savingDelivery ? "Saving..." : "Save preferences"}
                </button>
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
              No deliveries yet. Save your preferences and let the scheduler send the next brief.
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
                      {run.brief_type} brief · {run.channel} · {run.destination || "default destination"}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {new Date(run.brief_date).toLocaleDateString()} · {run.sent_at ? new Date(run.sent_at).toLocaleString() : "Not sent yet"}
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

        {/* Danger zone */}
        <div className="border border-red-200 dark:border-red-900 rounded-lg p-5">
          <h3 className="text-lg font-semibold text-red-600 dark:text-red-400 mb-4 flex items-center gap-2">
            <AlertTriangle size={20} />
            Danger Zone
          </h3>

          <div className="space-y-4">
            {/* Logout */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Sign out</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Sign out of your CommitGraph account on this device
                </p>
              </div>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 text-sm px-4 py-2 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                <LogOut size={14} />
                Sign out
              </button>
            </div>

            <div className="h-px bg-red-100 dark:bg-red-900" />

            {/* Delete account */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-red-600 dark:text-red-400">
                  Delete account
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Permanently delete your account, all connected emails, and all
                  commitments
                </p>
              </div>
              {confirmDelete ? (
                <div className="flex gap-2">
                  <button
                    onClick={handleDeleteUser}
                    disabled={deleting}
                    className="text-xs px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Yes, delete everything"}
                  </button>
                  <button
                    onClick={() => setConfirmDelete(false)}
                    className="text-xs px-4 py-2 bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="flex items-center gap-1.5 text-sm px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                >
                  <Trash2 size={14} />
                  Delete account
                </button>
              )}
            </div>
          </div>
        </div>
      </>
    </PageTransition>
  );
}
