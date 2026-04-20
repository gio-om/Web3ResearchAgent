import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from "recharts";
import type { VestingSchedule } from "../types";

interface VestingChartProps {
  schedules: VestingSchedule[];
  tgeStartDate?: string | null;
  tokenSymbol?: string;
  maxSupply?: number | null;
}

const COLORS = [
  "#6366f1",
  "#8b5cf6",
  "#ec4899",
  "#f59e0b",
  "#10b981",
  "#3b82f6",
  "#f97316",
  "#14b8a6",
];

type Tab = "chart" | "timeline" | "table";

function formatSupply(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}K`;
  return n.toLocaleString();
}

function addMonths(date: Date, months: number): Date {
  const d = new Date(date);
  d.setMonth(d.getMonth() + months);
  return d;
}

function fmtMonthYear(date: Date): string {
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

const RADIAN = Math.PI / 180;
function renderPieLabel({
  cx, cy, midAngle, innerRadius, outerRadius, percent,
}: {
  cx: number; cy: number; midAngle: number;
  innerRadius: number; outerRadius: number; percent: number;
}) {
  if (percent < 0.07) return null;
  const r = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return (
    <text
      x={x} y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      style={{ fontSize: 9, fontWeight: 700 }}
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

export default function VestingChart({
  schedules,
  tgeStartDate,
  tokenSymbol,
  maxSupply,
}: VestingChartProps) {
  const [tab, setTab] = useState<Tab>("chart");

  if (schedules.length === 0) {
    return (
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <p className="text-sm text-gray-500 italic">No vesting data available.</p>
      </div>
    );
  }

  const tgeDate = tgeStartDate ? new Date(tgeStartDate) : null;

  const items = schedules.map((s, i) => {
    const anchor = tgeDate ?? (s.round_date ? new Date(s.round_date) : null);
    const startDate = anchor ? addMonths(anchor, s.cliff_months ?? 0) : null;
    const endDate = startDate ? addMonths(startDate, s.vesting_months ?? 0) : null;
    return {
      s,
      color: COLORS[i % COLORS.length],
      startDate,
      endDate,
      isPointEvent: (s.vesting_months ?? 0) === 0,
    };
  });

  const minDate: Date | null = tgeDate ?? items.reduce<Date | null>(
    (m, it) => (!m || (it.startDate && it.startDate < m)) ? it.startDate : m,
    null,
  );
  const maxDate: Date | null = items.reduce<Date | null>(
    (m, it) => (!m || (it.endDate && it.endDate > m)) ? it.endDate : m,
    null,
  );
  const totalMs = minDate && maxDate ? maxDate.getTime() - minDate.getTime() : 0;

  const toPct = (d: Date | null): number => {
    if (!d || !minDate || !totalMs) return 0;
    return Math.max(0, Math.min(100, (d.getTime() - minDate.getTime()) / totalMs * 100));
  };

  const todayPct = toPct(new Date());

  const axisLabels: Array<{ label: string; pct: number }> = [];
  if (minDate && maxDate && totalMs) {
    const spanMonths = Math.round(totalMs / (1000 * 60 * 60 * 24 * 30.5));
    const step = spanMonths <= 18 ? 3 : spanMonths <= 48 ? 6 : spanMonths <= 84 ? 12 : 24;
    const cur = new Date(minDate);
    while (cur <= maxDate) {
      axisLabels.push({ label: fmtMonthYear(cur), pct: toPct(new Date(cur)) });
      cur.setMonth(cur.getMonth() + step);
    }
  }

  const hasTimeline = !!(minDate && totalMs);
  const hasUnlocked = schedules.some((s) => s.unlocked_percent != null);

  return (
    <div className="space-y-4 bg-white rounded-xl p-4 shadow-sm">

      {/* ── Allocation header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold uppercase tracking-wide text-gray-500">Allocation</span>
        {maxSupply != null && (
          <span className="text-gray-400">
            Max. Supply:{" "}
            <span className="font-semibold text-gray-700">
              {tokenSymbol ? `${tokenSymbol} ` : ""}
              {formatSupply(maxSupply)}
            </span>
          </span>
        )}
      </div>

      {/* ── Donut + summary table ──────────────────────────────────────────── */}
      <div className="flex gap-3 items-start">
        <div className="w-28 h-28 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={schedules}
                dataKey="total_percent"
                nameKey="recipient_type"
                cx="50%"
                cy="50%"
                innerRadius="52%"
                outerRadius="82%"
                strokeWidth={1}
                stroke="#fff"
                labelLine={false}
                label={renderPieLabel}
              >
                {schedules.map((_s, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(v: number) => [`${v}%`, "Allocation"]}
                contentStyle={{ fontSize: 11 }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="flex-1 min-w-0 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400 text-left border-b border-gray-100">
                <th className="pb-1 pr-2 font-medium">Name</th>
                <th className="pb-1 pr-2 font-medium text-right">Total</th>
                {hasUnlocked && (
                  <>
                    <th className="pb-1 pr-2 font-medium text-right">Unlocked</th>
                    <th className="pb-1 font-medium text-right">Locked</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {schedules.map((s, i) => {
                const unlockedOfAlloc = s.unlocked_percent ?? null;
                const unlockedOfSupply =
                  unlockedOfAlloc != null
                    ? (s.total_percent * unlockedOfAlloc) / 100
                    : null;
                const lockedOfSupply =
                  unlockedOfSupply != null
                    ? Math.max(0, s.total_percent - unlockedOfSupply)
                    : null;
                return (
                  <tr key={i} className="border-b border-gray-50">
                    <td className="py-1 pr-2">
                      <span className="flex items-center gap-1">
                        <span
                          className="inline-block w-2 h-2 rounded-full shrink-0"
                          style={{ backgroundColor: COLORS[i % COLORS.length] }}
                        />
                        <span className="break-words leading-tight">{s.recipient_type}</span>
                      </span>
                    </td>
                    <td className="py-1 pr-2 text-right font-medium whitespace-nowrap">{s.total_percent}%</td>
                    {hasUnlocked && (
                      <>
                        <td className="py-1 pr-2 text-right text-emerald-600 whitespace-nowrap">
                          {unlockedOfSupply != null
                            ? `${unlockedOfSupply.toFixed(2)}%`
                            : "—"}
                        </td>
                        <td className="py-1 text-right text-red-500 font-medium whitespace-nowrap">
                          {lockedOfSupply != null
                            ? `${lockedOfSupply.toFixed(2)}%`
                            : "—"}
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Vesting Schedule heading + tabs ───────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-gray-100 pb-0">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 pb-1.5">
          Vesting Schedule
        </span>
        <div className="flex gap-0.5 text-xs font-medium">
          {(["table", "timeline", "chart"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-2.5 py-1 rounded-t-md capitalize transition-colors ${
                tab === t
                  ? "bg-white border border-b-white border-gray-200 text-indigo-600 -mb-px z-10"
                  : "text-gray-400 hover:text-gray-600"
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* ── Table tab ─────────────────────────────────────────────────────── */}
      {tab === "table" && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-gray-600">
            <thead>
              <tr className="border-b text-left text-gray-400">
                <th className="pb-1 pr-3 font-medium">Recipient</th>
                <th className="pb-1 pr-3 font-medium text-right">%</th>
                <th className="pb-1 pr-3 font-medium text-right">Cliff</th>
                <th className="pb-1 pr-3 font-medium text-right">Vesting</th>
                <th className="pb-1 font-medium text-right">TGE%</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-1.5 pr-3">
                    <span className="flex items-center gap-1.5">
                      <span
                        className="inline-block w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: COLORS[i % COLORS.length] }}
                      />
                      {s.recipient_type}
                    </span>
                  </td>
                  <td className="py-1.5 pr-3 text-right font-medium">{s.total_percent}%</td>
                  <td className="py-1.5 pr-3 text-right">{s.cliff_months}mo</td>
                  <td className="py-1.5 pr-3 text-right">{s.vesting_months}mo</td>
                  <td className="py-1.5 text-right">{s.tge_percent}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Timeline tab ──────────────────────────────────────────────────── */}
      {tab === "timeline" && (
        <div className="space-y-1.5">
          {!hasTimeline ? (
            <p className="text-xs text-gray-400 italic">
              Timeline unavailable — no TGE date in data.
            </p>
          ) : (
            <>
              {/* TODAY label */}
              <div className="relative ml-[116px] h-4">
                <div
                  className="absolute top-0 text-[10px] font-bold text-indigo-500 -translate-x-1/2 select-none"
                  style={{ left: `${todayPct}%` }}
                >
                  TODAY
                </div>
              </div>

              {/* Allocation rows */}
              {items.map((item, i) => {
                const startPct = toPct(item.startDate);
                const rawEnd = toPct(item.endDate);
                const barW = item.isPointEvent
                  ? 1.5
                  : Math.max(1, rawEnd - startPct);

                const unlockedFrac =
                  item.s.unlocked_percent != null
                    ? item.s.unlocked_percent / 100
                    : (() => {
                        if (!item.startDate || !item.endDate) return 0;
                        const now = Date.now();
                        const s = item.startDate.getTime();
                        const e = item.endDate.getTime();
                        if (now <= s) return 0;
                        if (now >= e) return 1;
                        return (now - s) / (e - s);
                      })();

                const unlockedW = barW * Math.min(1, unlockedFrac);
                const lockedW = barW - unlockedW;

                const unlockedLabel =
                  item.s.unlocked_percent != null
                    ? `Unlock ${item.s.unlocked_percent.toFixed(1)}%`
                    : item.s.unlock_type === "vested_at_tge"
                    ? "Vested at TGE"
                    : "Linear";

                const lockedPct =
                  item.s.unlocked_percent != null
                    ? (100 - item.s.unlocked_percent).toFixed(1)
                    : null;

                return (
                  <div key={i} className="flex items-center gap-2">
                    {/* Row label — wider, allows 2 lines */}
                    <div
                      className="text-[11px] text-gray-500 shrink-0 text-right leading-tight"
                      style={{ width: 112 }}
                    >
                      {item.s.recipient_type}
                    </div>

                    {/* Track */}
                    <div className="relative flex-1 h-7 bg-gray-100 rounded overflow-hidden">
                      {/* Today line */}
                      <div
                        className="absolute inset-y-0 w-px bg-indigo-400 z-20"
                        style={{ left: `${todayPct}%` }}
                      />

                      {/* Unlocked segment */}
                      {unlockedW > 0 && (
                        <div
                          className="absolute inset-y-0 flex items-center overflow-hidden"
                          style={{
                            left: `${startPct}%`,
                            width: `${unlockedW}%`,
                            backgroundColor: item.color,
                          }}
                        >
                          {unlockedW > 8 && (
                            <span className="px-1.5 text-[10px] text-white font-medium truncate select-none">
                              {unlockedLabel}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Locked segment */}
                      {lockedW > 0 && (
                        <div
                          className="absolute inset-y-0 flex items-center overflow-hidden"
                          style={{
                            left: `${startPct + unlockedW}%`,
                            width: `${lockedW}%`,
                            backgroundColor: item.color,
                            opacity: 0.22,
                          }}
                        >
                          {lockedW > 10 && lockedPct != null && (
                            <span
                              className="px-1.5 text-[10px] font-medium truncate select-none"
                              style={{ color: item.color }}
                            >
                              Lock {lockedPct}%
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* X-axis labels */}
              <div className="relative ml-[116px] h-5 mt-1">
                {axisLabels.map(({ label, pct }, i) => (
                  <span
                    key={i}
                    className="absolute text-[10px] text-gray-400 -translate-x-1/2 select-none"
                    style={{ left: `${pct}%` }}
                  >
                    {label}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Chart tab ─────────────────────────────────────────────────────── */}
      {tab === "chart" && (
        <ResponsiveContainer width="100%" height={schedules.length * 44 + 40}>
          <BarChart
            data={schedules.map((s) => ({
              name: s.recipient_type,
              allocation: s.total_percent,
            }))}
            layout="vertical"
            margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
          >
            <XAxis type="number" unit="%" domain={[0, 100]} tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="name"
              width={110}
              tick={{ fontSize: 11 }}
            />
            <Tooltip formatter={(v: number) => [`${v}%`, "Allocation"]} />
            <Bar dataKey="allocation" radius={[0, 4, 4, 0]}>
              {schedules.map((_s, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
