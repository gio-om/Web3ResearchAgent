import { useState } from "react";
import type { InvestorInfo, InvestorChip, FundingRound } from "../types";
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
const PAGE_SIZE = 10;

function InvestorAvatar({ inv, size = 8 }: { inv: InvestorChip; size?: number }) {
  const sz = `w-${size} h-${size}`;
  if (inv.logo) {
    return (
      <img
        src={inv.logo}
        alt={inv.name}
        className={`${sz} rounded-full object-cover bg-gray-100 shrink-0`}
        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
      />
    );
  }
  return (
    <div
      className={`${sz} rounded-full flex items-center justify-center text-white shrink-0`}
      style={{ backgroundColor: avatarColor(inv.name), fontSize: size <= 6 ? 8 : 10, fontWeight: 700 }}
    >
      {initials(inv.name)}
    </div>
  );
}

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
          {investors.map((inv, i) => (
            <div key={i} className="flex items-center gap-2.5">
              <InvestorAvatar inv={inv} size={8} />
              <span className="text-sm text-gray-800">{inv.name}</span>
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
          <div className="flex items-center gap-3 shrink-0">
            {round.amount_usd != null && (
              <div className="text-right">
                <div className="text-[10px] text-gray-400 leading-none mb-0.5">Raised</div>
                <div className="text-sm font-bold text-gray-900">{formatUsd(round.amount_usd)}</div>
              </div>
            )}
            {round.valuation_usd != null && (
              <div className="text-right">
                <div className="text-[10px] text-gray-400 leading-none mb-0.5">Valuation</div>
                <div className="text-sm font-bold text-gray-900">{formatUsd(round.valuation_usd)}</div>
              </div>
            )}
          </div>
        </div>

        {/* Investors */}
        {investors.length > 0 ? (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-gray-400 mr-0.5">Investors:</span>
            {visible.map((inv, i) => (
              <div key={i} className="flex items-center gap-1 bg-gray-50 rounded-full pl-1 pr-2.5 py-0.5">
                <InvestorAvatar inv={inv} size={5} />
                <span className="text-xs text-gray-700 max-w-[90px] truncate">{inv.name}</span>
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

function InvestorTable({ investors }: { investors: InvestorInfo[] }) {
  const [page, setPage] = useState(0);
  const totalPages = Math.ceil(investors.length / PAGE_SIZE);
  const slice = investors.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);
  const from = page * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE + PAGE_SIZE, investors.length);

  return (
    <div className="bg-white rounded-xl shadow-sm overflow-hidden">
      {/* Table header */}
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-3 px-4 py-2.5 border-b border-gray-100">
        <span className="text-xs font-semibold text-gray-400">Name</span>
        <span className="text-xs font-semibold text-gray-400 text-center w-8">Tier</span>
        <span className="text-xs font-semibold text-gray-400 w-20">Type</span>
        <span className="text-xs font-semibold text-gray-400 w-24">Stage</span>
      </div>

      {/* Rows */}
      <div className="divide-y divide-gray-50">
        {slice.map((inv, i) => (
          <div key={i} className="grid grid-cols-[1fr_auto_auto_auto] gap-x-3 px-4 py-3 items-center">
            {/* Name + avatar */}
            <div className="flex items-center gap-2 min-w-0">
              <InvestorAvatar inv={{ name: inv.name, logo: inv.logo }} size={7} />
              <span className="text-sm text-gray-800 truncate">{inv.name}</span>
              {inv.is_lead && (
                <span className="text-[10px] font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded shrink-0">
                  Lead
                </span>
              )}
            </div>

            {/* Tier */}
            <span className="text-sm text-gray-600 text-center w-8">
              {inv.tier ?? "—"}
            </span>

            {/* Type / category */}
            <span className="text-sm text-gray-600 w-20 truncate capitalize">
              {inv.category ?? "—"}
            </span>

            {/* Stages */}
            <div className="flex flex-wrap gap-1 w-24">
              {(inv.stages && inv.stages.length > 0)
                ? inv.stages.map((s, j) => (
                    <span key={j} className="text-[10px] bg-gray-100 text-gray-600 rounded px-1.5 py-0.5 whitespace-nowrap">
                      {s}
                    </span>
                  ))
                : inv.round
                  ? <span className="text-[10px] bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">{inv.round}</span>
                  : <span className="text-xs text-gray-300">—</span>
              }
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
          <span className="text-xs text-gray-400">
            {from} – {to} from {investors.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="w-7 h-7 flex items-center justify-center rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-sm"
            >
              ‹
            </button>
            {Array.from({ length: totalPages }, (_, i) => (
              <button
                key={i}
                onClick={() => setPage(i)}
                className={`w-7 h-7 flex items-center justify-center rounded text-xs font-medium transition-colors ${
                  i === page
                    ? "bg-indigo-500 text-white"
                    : "text-gray-500 hover:bg-gray-100"
                }`}
              >
                {i + 1}
              </button>
            ))}
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page === totalPages - 1}
              className="w-7 h-7 flex items-center justify-center rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-sm"
            >
              ›
            </button>
          </div>
        </div>
      )}
    </div>
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

  const totalRaised = fundingRounds.reduce(
    (sum, r) => (r.amount_usd != null ? sum + r.amount_usd : sum),
    0,
  );

  return (
    <div className="space-y-3">
      {fundingRounds.length > 0 && (
        <>
          {totalRaised > 0 && (
            <div className="flex items-center justify-between bg-white rounded-xl px-4 py-3 shadow-sm">
              <span className="text-sm text-gray-500">Total Raised</span>
              <span className="text-base font-bold text-gray-900">{formatUsd(totalRaised)}</span>
            </div>
          )}
          <div className="space-y-2">
            {fundingRounds.map((r, i) => (
              <RoundCard key={i} round={r} />
            ))}
          </div>
        </>
      )}

      {investors.length > 0 && (
        <InvestorTable investors={investors} />
      )}
    </div>
  );
}
