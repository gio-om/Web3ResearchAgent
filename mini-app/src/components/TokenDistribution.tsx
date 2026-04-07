import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface TokenDistributionProps {
  distribution: Record<string, number>;
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

export default function TokenDistribution({ distribution }: TokenDistributionProps) {
  const entries = Object.entries(distribution);

  if (entries.length === 0) {
    return (
      <p className="text-sm text-gray-500 italic">
        No distribution data available.
      </p>
    );
  }

  const data = entries.map(([name, value]) => ({ name, value }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="45%"
          outerRadius={80}
          dataKey="value"
          label={({ name, value }: { name: string; value: number }) =>
            `${name} ${value}%`
          }
          labelLine={false}
        >
          {data.map((_entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(value: number) => [`${value}%`, "Allocation"]} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
