import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { VestingSchedule } from "../types";

interface VestingChartProps {
  schedules: VestingSchedule[];
}

const COLORS = [
  "#6366f1",
  "#8b5cf6",
  "#ec4899",
  "#f59e0b",
  "#10b981",
  "#3b82f6",
];

export default function VestingChart({ schedules }: VestingChartProps) {
  if (schedules.length === 0) {
    return (
      <p className="text-sm text-gray-500 italic">No vesting data available.</p>
    );
  }

  const data = schedules.map((s) => ({
    name: s.recipient_type,
    allocation: s.total_percent,
    cliff: s.cliff_months,
    vesting: s.vesting_months,
    tge: s.tge_percent,
  }));

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={schedules.length * 44 + 40}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
        >
          <XAxis type="number" unit="%" domain={[0, 100]} tick={{ fontSize: 11 }} />
          <YAxis
            type="category"
            dataKey="name"
            width={96}
            tick={{ fontSize: 11 }}
          />
          <Tooltip
            formatter={(value: number, name: string) => {
              if (name === "allocation") return [`${value}%`, "Allocation"];
              return [value, name];
            }}
          />
          <Bar dataKey="allocation" radius={[0, 4, 4, 0]}>
            {data.map((_entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

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
                <td className="py-1 pr-3">{s.recipient_type}</td>
                <td className="py-1 pr-3 text-right">{s.total_percent}%</td>
                <td className="py-1 pr-3 text-right">{s.cliff_months}mo</td>
                <td className="py-1 pr-3 text-right">{s.vesting_months}mo</td>
                <td className="py-1 text-right">{s.tge_percent}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
