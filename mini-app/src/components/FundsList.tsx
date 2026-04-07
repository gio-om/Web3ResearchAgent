import type { InvestorInfo, FundingRound } from "../types";
import { formatUsd } from "../utils/format";

interface FundsListProps {
  investors: InvestorInfo[];
  fundingRounds: FundingRound[];
}

const TIER_STYLE: Record<string, string> = {
  Tier1: "bg-purple-100 text-purple-700",
  Tier2: "bg-blue-100 text-blue-700",
  Tier3: "bg-gray-100 text-gray-600",
};

export default function FundsList({ investors, fundingRounds }: FundsListProps) {
  return (
    <div className="space-y-4">
      {fundingRounds.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
            Funding Rounds
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-gray-400">
                  <th className="pb-1 pr-3 font-medium">Round</th>
                  <th className="pb-1 pr-3 font-medium text-right">Raised</th>
                  <th className="pb-1 pr-3 font-medium text-right">Valuation</th>
                  <th className="pb-1 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {fundingRounds.map((r, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-1.5 pr-3 font-medium text-gray-800">
                      {r.round_name}
                    </td>
                    <td className="py-1.5 pr-3 text-right text-gray-700">
                      {formatUsd(r.amount_usd)}
                    </td>
                    <td className="py-1.5 pr-3 text-right text-gray-700">
                      {formatUsd(r.valuation_usd)}
                    </td>
                    <td className="py-1.5 text-gray-500">
                      {r.date ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {investors.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
            Investors
          </h3>
          <div className="space-y-2">
            {investors.map((inv, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2"
              >
                <div>
                  <span className="text-sm font-semibold text-gray-800">
                    {inv.name}
                  </span>
                  {(inv.portfolio_notable?.length ?? 0) > 0 && (
                    <p className="text-xs text-gray-500">
                      {inv.portfolio_notable.slice(0, 3).join(", ")}
                    </p>
                  )}
                </div>
                {inv.tier && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${TIER_STYLE[inv.tier] ?? "bg-gray-100 text-gray-600"}`}
                  >
                    {inv.tier}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {fundingRounds.length === 0 && investors.length === 0 && (
        <p className="text-sm text-gray-500 italic">No funding data available.</p>
      )}
    </div>
  );
}
