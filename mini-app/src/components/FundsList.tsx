import { useState } from "react";
import type { InvestorInfo, FundingRound } from "../types";
import { formatUsd } from "../utils/format";

interface FundsListProps {
  investors: InvestorInfo[];
  fundingRounds: FundingRound[];
}

const AVATAR_COLORS = [
  "#6366f1", "#8b5cf6", "#ec4899", "#f59e0b",
  "#10b981", "#3b82f6", "#f97316", "#14b8a6",
  "#ef4444", "#a855f7",
];

function avatarColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffffffff;
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function formatDate(d: string | null): string {
  if (!d) return "—";
  const dt = new Date(d);
  return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

const VISIBLE_INVESTORS = 4;

interface InvestorModalProps {
  round: FundingRound;
  onClose: () => void;
}

function InvestorModal({ round, onClose }: InvestorModalProps) {
  const investors = round.investors ?? [];
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl max-h-[75vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="font-bold text-gray-900 text-base">{round.round_name}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {formatDate(round.date)}
              {round.amount_usd != null && ` · Raised ${formatUsd(round.amount_usd)}`}
              {round.valuation_usd != null && ` · Val. ${formatUsd(round.valuation_usd)}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none ml-3"
          >
            ×
          </button>
        </div>

        <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">
          All Investors ({investors.length})
        </p>
        <div className="space-y-2">
          {investors.map((name, i) => (
            <div key={i} className="flex items-center gap-2.5">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
                style={{ backgroundColor: avatarColor(name) }}
              >
                {initials(name)}
              </div>
              <span className="text-sm text-gray-800">{name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface RoundCardProps {
  round: FundingRound;
}

function RoundCard({ round }: RoundCardProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const investors = round.investors ?? [];
  const visible = investors.slice(0, VISIBLE_INVESTORS);
  const extra = investors.length - VISIBLE_INVESTORS;

  return (
    <>
      <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-1 h-5 rounded-full bg-indigo-500 shrink-0" />
            <span className="font-bold text-gray-900 text-sm truncate">{round.round_name}</span>
            <span className="text-xs text-gray-400 whitespace-nowrap">{formatDate(round.date)}</span>
            {round.announcement && (
              <a
                href={round.announcement}
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-400 hover:text-indigo-600 text-xs"
              >
                ↗
              </a>
            )}
          </div>
          <div className="flex items-center gap-3 shrink-0 text-xs">
            {round.amount_usd != null && (
              <span className="text-gray-500">
                Raised <span className="font-semibold text-gray-800">{formatUsd(round.amount_usd)}</span>
              </span>
            )}
            {round.valuation_usd != null && (
              <span className="text-gray-500">
                Val. <span className="font-semibold text-gray-800">{formatUsd(round.valuation_usd)}</span>
              </span>
            )}
          </div>
        </div>

        {/* Investors */}
        {investors.length > 0 ? (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-gray-400 mr-0.5">Investors:</span>
            {visible.map((name, i) => (
              <div key={i} className="flex items-center gap-1 bg-gray-50 rounded-full pl-1 pr-2.5 py-0.5">
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-white shrink-0"
                  style={{ backgroundColor: avatarColor(name), fontSize: 8, fontWeight: 700 }}
                >
                  {initials(name)}
                </div>
                <span className="text-xs text-gray-700 max-w-[90px] truncate">{name}</span>
              </div>
            ))}
            {extra > 0 && (
              <button
                onClick={() => setModalOpen(true)}
                className="text-xs font-semibold text-indigo-500 bg-indigo-50 hover:bg-indigo-100 rounded-full px-2.5 py-0.5 transition-colors"
              >
                +{extra} more
              </button>
            )}
          </div>
        ) : (
          <span className="text-xs text-gray-400 italic">No investor data</span>
        )}
      </div>

      {modalOpen && <InvestorModal round={round} onClose={() => setModalOpen(false)} />}
    </>
  );
}

export default function FundsList({ investors, fundingRounds }: FundsListProps) {
  if (fundingRounds.length === 0 && investors.length === 0) {
    return (
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <p className="text-sm text-gray-500 italic">No funding data available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {fundingRounds.length > 0 && (
        <div className="space-y-2">
          {fundingRounds.map((r, i) => (
            <RoundCard key={i} round={r} />
          ))}
        </div>
      )}

      {/* Fallback investor list if no per-round data */}
      {fundingRounds.length === 0 && investors.length > 0 && (
        <div className="bg-white rounded-xl p-4 shadow-sm space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Investors</p>
          {investors.map((inv, i) => (
            <div key={i} className="flex items-center gap-2.5">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
                style={{ backgroundColor: avatarColor(inv.name) }}
              >
                {initials(inv.name)}
              </div>
              <span className="text-sm text-gray-800">{inv.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
