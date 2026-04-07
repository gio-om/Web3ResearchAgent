import type { Report } from "../types";
import ScoreGauge from "./ScoreGauge";
import { formatUsd } from "../utils/format";

interface ProjectCardProps {
  report: Report;
}

const REC_STYLE: Record<Report["recommendation"], string> = {
  Strong: "bg-green-100 text-green-800",
  Interesting: "bg-blue-100 text-blue-800",
  DYOR: "bg-yellow-100 text-yellow-800",
  Avoid: "bg-red-100 text-red-800",
};

export default function ProjectCard({ report }: ProjectCardProps) {
  const { fdv_usd, market_cap_usd } = report.coingecko_summary;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-bold text-gray-900">
            {report.project_name}
          </h1>
          <span
            className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${REC_STYLE[report.recommendation]}`}
          >
            {report.recommendation}
          </span>
        </div>
        <ScoreGauge score={report.overall_score} size={96} />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-lg bg-gray-50 px-3 py-2">
          <p className="text-xs text-gray-500">FDV</p>
          <p className="font-semibold text-gray-800">{formatUsd(fdv_usd, "N/A")}</p>
        </div>
        <div className="rounded-lg bg-gray-50 px-3 py-2">
          <p className="text-xs text-gray-500">Market Cap</p>
          <p className="font-semibold text-gray-800">
            {formatUsd(market_cap_usd, "N/A")}
          </p>
        </div>
      </div>

      {report.summary && (
        <p className="mt-3 text-sm text-gray-600 leading-relaxed">
          {report.summary}
        </p>
      )}

      {(report.strengths?.length ?? 0) > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Strengths
          </p>
          <ul className="mt-1 space-y-0.5">
            {report.strengths.map((s, i) => (
              <li key={i} className="text-sm text-gray-700">
                ✅ {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(report.weaknesses?.length ?? 0) > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Weaknesses
          </p>
          <ul className="mt-1 space-y-0.5">
            {report.weaknesses.map((w, i) => (
              <li key={i} className="text-sm text-gray-700">
                ⚠️ {w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
