import type { RiskFlag } from "../types";

interface RiskFlagsProps {
  flags: RiskFlag[];
}

const ICON: Record<RiskFlag["type"], string> = {
  red: "🔴",
  yellow: "🟡",
  green: "🟢",
};

const BG: Record<RiskFlag["type"], string> = {
  red: "bg-red-50 border-red-200",
  yellow: "bg-yellow-50 border-yellow-200",
  green: "bg-green-50 border-green-200",
};

const TEXT: Record<RiskFlag["type"], string> = {
  red: "text-red-700",
  yellow: "text-yellow-700",
  green: "text-green-700",
};

export default function RiskFlags({ flags }: RiskFlagsProps) {
  if (flags.length === 0) {
    return (
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <p className="text-sm text-gray-500 italic">No risk flags detected.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl p-4 shadow-sm">
    <ul className="space-y-2">
      {flags.map((flag, i) => (
        <li
          key={i}
          className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${BG[flag.type]}`}
        >
          <span className="mt-0.5 shrink-0">{ICON[flag.type]}</span>
          <div>
            <span className={`font-semibold ${TEXT[flag.type]}`}>
              {flag.category}:
            </span>{" "}
            <span className="text-gray-700">{flag.message}</span>
          </div>
        </li>
      ))}
    </ul>
    </div>
  );
}
