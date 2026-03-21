"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  ArrowUpRight,
  ArrowDownLeft,
  Mail,
  Waypoints,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useAccountFilter } from "@/components/AccountFilterProvider";

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [commitments, setCommitments] = useState<any[]>([]);
  const [chartData, setChartData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasAccounts, setHasAccounts] = useState(true);
  const router = useRouter();
  const { activeAccountId } = useAccountFilter();

  useEffect(() => {
    async function load() {
      try {
        const params = new URLSearchParams();
        if (activeAccountId) params.set("account_id", activeAccountId);

        const [statsData, commitmentsData] = await Promise.all([
          api.getStats(params.toString()),
          api.getCommitments(
            new URLSearchParams({
              ...(activeAccountId ? { account_id: activeAccountId } : {}),
              limit: "10",
            }).toString(),
          ),
        ]);

        setStats(statsData);
        setCommitments(commitmentsData.commitments);

        try {
          const accountsData = await api.getAccounts();
          setHasAccounts(accountsData.accounts?.length > 0);
        } catch {
          setHasAccounts(true);
        }

        try {
          const chartResponse = await api.getChartData(params.toString());
          setChartData(chartResponse.chart_data || []);
        } catch {
          setChartData([]);
        }
      } catch (err) {
        console.error("Failed to load dashboard:", err);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [activeAccountId]);

  if (loading) return <PageSkeleton />;

  // New user — no accounts connected
  if (!hasAccounts) {
    return <WelcomeState />;
  }

  const totalCommitments =
    (stats?.open_count ?? 0) + (stats?.completed_count ?? 0);

  // Has account but no commitments yet
  if (totalCommitments === 0 && commitments.length === 0) {
    return <EmptyState />;
  }

  return (
    <>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-8">
        <StatCard
          label="Open"
          value={stats?.open_count ?? 0}
          icon={<Clock size={20} className="text-blue-500" />}
          onClick={() => router.push("/commitments")}
        />
        <StatCard
          label="Overdue"
          value={stats?.overdue_count ?? 0}
          icon={<AlertTriangle size={20} className="text-red-500" />}
          onClick={() => router.push("/commitments?status=overdue")}
          highlight={stats?.overdue_count > 0 ? "red" : undefined}
        />
        <StatCard
          label="Completed"
          value={stats?.completed_count ?? 0}
          icon={<CheckCircle size={20} className="text-green-500" />}
          onClick={() => router.push("/commitments?status=completed")}
        />
        <StatCard
          label="Review Queue"
          value={stats?.review_queue_count ?? 0}
          icon={<AlertTriangle size={20} className="text-amber-500" />}
          onClick={() => router.push("/review")}
          highlight={stats?.review_queue_count > 0 ? "amber" : undefined}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4 mb-8">
        <StatCard
          label="I Owe"
          value={stats?.i_owe_count ?? 0}
          icon={<ArrowUpRight size={20} className="text-purple-500" />}
          onClick={() => router.push("/commitments?direction=outbound")}
        />
        <StatCard
          label="Owed To Me"
          value={stats?.owed_to_me_count ?? 0}
          icon={<ArrowDownLeft size={20} className="text-teal-500" />}
          onClick={() => router.push("/commitments?direction=inbound")}
        />
      </div>

      <CommitmentChart data={chartData} />

      <h3 className="text-lg font-semibold mb-4">Recent commitments</h3>
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden">
        {commitments.map((c: any) => (
          <CommitmentRow
            key={c.id}
            commitment={c}
            onClick={() => router.push(`/commitments?highlight=${c.id}`)}
          />
        ))}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Welcome state — brand new user, no accounts
// ---------------------------------------------------------------------------
function WelcomeState() {
  const router = useRouter();

  return (
    <div className="flex flex-col items-center justify-center py-20">
      <Waypoints size={48} className="text-blue-500 mb-4" />
      <h2 className="text-2xl font-bold mb-2">Welcome to CommitGraph</h2>
      <p className="text-gray-500 dark:text-gray-400 text-center max-w-md mb-8">
        Connect your email account to start tracking commitments automatically.
        We&apos;ll scan your inbox and extract promises, deadlines, and
        follow-ups.
      </p>
      <div className="flex gap-3">
        <button
          onClick={() => router.push("/settings")}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          <Mail size={18} />
          Connect your email
        </button>
      </div>
      <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6 max-w-2xl">
        <FeatureCard
          title="Auto-extract"
          description="AI reads your emails and finds commitments you've made or received"
        />
        <FeatureCard
          title="Track deadlines"
          description="Never miss a due date — see everything in one dashboard"
        />
        <FeatureCard
          title="Evidence trail"
          description="Every commitment links back to the original email"
        />
      </div>
    </div>
  );
}

function FeatureCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5 text-center">
      <p className="font-semibold text-sm mb-1">{title}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty state — account connected but no commitments yet
// ---------------------------------------------------------------------------
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="w-16 h-16 rounded-full bg-blue-50 dark:bg-blue-950 flex items-center justify-center mb-4">
        <CheckCircle size={28} className="text-blue-500" />
      </div>
      <h2 className="text-2xl font-bold mb-2">You&apos;re all set up!</h2>
      <p className="text-gray-500 dark:text-gray-400 text-center max-w-md mb-2">
        Your email is connected. Commitments will appear here as new emails come
        in.
      </p>
      <p className="text-sm text-gray-400 dark:text-gray-500 text-center max-w-md">
        Send yourself a test email with a promise like &quot;I&apos;ll send the
        report by Friday&quot; to see it in action.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------
function StatCard({
  label,
  value,
  icon,
  onClick,
  highlight,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  onClick?: () => void;
  highlight?: "red" | "amber";
}) {
  const highlightStyles = {
    red: "border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950",
    amber:
      "border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950",
  };

  return (
    <div
      onClick={onClick}
      className={`rounded-lg border p-4 cursor-pointer transition-all hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 ${
        highlight
          ? highlightStyles[highlight]
          : "bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {label}
        </span>
        {icon}
      </div>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Commitment row
// ---------------------------------------------------------------------------
function CommitmentRow({
  commitment: c,
  onClick,
}: {
  commitment: any;
  onClick: () => void;
}) {
  const statusColors: Record<string, string> = {
    confirmed: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    overdue: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    completed:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    detected:
      "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
    in_progress:
      "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    abandoned: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
  };

  return (
    <div
      onClick={onClick}
      className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
    >
      <div className="flex-1">
        <p className="font-medium text-sm">{c.summary}</p>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          {c.owner_is_self ? "You → " : "← "}
          {c.owner_is_self
            ? c.target_email || "general"
            : c.owner_email || "someone"}
          {c.due_date && ` · Due ${new Date(c.due_date).toLocaleDateString()}`}
        </p>
        {c.account_email && (
          <div className="mt-1">
            <span className="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-800 px-2 py-0.5 text-[11px] text-gray-500 dark:text-gray-400">
              {c.account_email}
            </span>
          </div>
        )}
      </div>
      <span
        className={`text-xs px-2 py-1 rounded-full font-medium ${statusColors[c.status] ?? "bg-gray-100 dark:bg-gray-800"}`}
      >
        {c.status}
      </span>
    </div>
  );
}

function CommitmentChart({ data }: { data: any[] }) {
  if (!data || !Array.isArray(data) || data.length === 0) return null;

  const formatted = data.map((d) => ({
    day: new Date(d.day).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
    outbound: d.outbound || 0,
    inbound: d.inbound || 0,
  }));

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-5 mb-8">
      <h3 className="text-lg font-semibold mb-4">Commitments over time</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={formatted} barGap={2}>
          <CartesianGrid
            strokeDasharray="3 3"
            className="stroke-gray-200 dark:stroke-gray-700"
          />
          <XAxis
            dataKey="day"
            tick={{ fontSize: 11 }}
            className="text-gray-500"
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11 }}
            className="text-gray-500"
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: "transparent" }}
          />
          <Bar
            dataKey="outbound"
            name="I Owe"
            fill="#8b5cf6"
            radius={[3, 3, 0, 0]}
          />
          <Bar
            dataKey="inbound"
            name="Owed To Me"
            fill="#14b8a6"
            radius={[3, 3, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
        {label}
      </p>
      {payload.map((entry: any) => (
        <p
          key={entry.name}
          className="text-xs text-gray-500 dark:text-gray-400"
        >
          <span
            className="inline-block w-2 h-2 rounded-full mr-1.5"
            style={{ backgroundColor: entry.color }}
          />
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
}
