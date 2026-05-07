import { useState } from "react";
import type { InvestorInfo, InvestorChip, FundingRound } from "../types";
import { formatUsd } from "../utils/format";
import { t, fmtPagination } from "../i18n";
import type { Lang } from "../i18n";

interface FundsListProps {
  investors: InvestorInfo[];
  fundingRounds: FundingRound[];
  lang: Lang;
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

function formatDate(d: string | null, lang: Lang): string {
  if (!d) return "—";
  const dt = new Date(d);
  return dt.toLocaleDateString(lang === "ru" ? "ru-RU" : "en-US", { month: "short", day: "numeric", year: "numeric" });
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
  lang: Lang;
}

function InvestorModal({ round, onClose, lang }: InvestorModalProps) {
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
              {formatDate(round.date, lang)}
              {round.amount_usd != null && ` · ${t("raised", lang)} ${formatUsd(round.amount_usd)}`}
              {round.valuation_usd != null
                ? ` · ${t("valuation", lang)} ${formatUsd(round.valuation_usd)}`
                : round.fdv_is_predicted && round.predicted_valuation_usd != null
                  ? ` · ${t("predicted_val", lang)} ~${formatUsd(round.predicted_valuation_usd)}`
                  : null}
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
          {t("all_investors", lang)} ({investors.length})
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

function PredictedValuation({ round, lang }: { round: FundingRound; lang: Lang }) {
  const [expanded, setExpanded] = useState(false);
  const conf = round.fdv_confidence ?? "low";
  const confColor = {
    high: "bg-green-100 text-green-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-gray-100 text-gray-500",
  }[conf];

  return (
    <div className="text-right">
      <div className="text-[10px] text-gray-400 leading-none mb-0.5 flex items-center justify-end gap-1">
        {t("predicted_val", lang)}
        <span className={`text-[9px] font-semibold px-1 rounded ${confColor}`}>
          {t(`conf_${conf}` as Parameters<typeof t>[0], lang)}
        </span>
      </div>
      <button
        className="text-sm font-bold text-indigo-500 hover:text-indigo-700 transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        ~{formatUsd(round.predicted_valuation_usd!)}
      </button>
      {expanded && (
        <div className="mt-1 text-[10px] text-gray-500 text-left bg-indigo-50 rounded-lg p-2 max-w-[200px]">
          {round.fdv_range_low_usd != null && round.fdv_range_high_usd != null && (
            <p className="font-medium">
              {t("fdv_range_label", lang)}: {formatUsd(round.fdv_range_low_usd)} – {formatUsd(round.fdv_range_high_usd)}
            </p>
          )}
          {round.fdv_methodology && (
            <p className="mt-0.5 italic">{round.fdv_methodology}</p>
          )}
        </div>
      )}
    </div>
  );
}

interface RoundCardProps {
  round: FundingRound;
  lang: Lang;
}

function RoundCard({ round, lang }: RoundCardProps) {
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
            <span className="text-xs text-gray-400 whitespace-nowrap">{formatDate(round.date, lang)}</span>
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
                <div className="text-[10px] text-gray-400 leading-none mb-0.5">{t("raised", lang)}</div>
                <div className="text-sm font-bold text-gray-900">{formatUsd(round.amount_usd)}</div>
              </div>
            )}
            {round.valuation_usd != null ? (
              <div className="text-right">
                <div className="text-[10px] text-gray-400 leading-none mb-0.5">{t("valuation", lang)}</div>
                <div className="text-sm font-bold text-gray-900">{formatUsd(round.valuation_usd)}</div>
              </div>
            ) : round.fdv_is_predicted && round.predicted_valuation_usd != null ? (
              <PredictedValuation round={round} lang={lang} />
            ) : null}
          </div>
        </div>

        {/* Investors */}
        {investors.length > 0 ? (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-gray-400 mr-0.5">{t("col_name", lang)}:</span>
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
          <span className="text-xs text-gray-400 italic">{t("no_investor_data", lang)}</span>
        )}
      </div>

      {modalOpen && <InvestorModal round={round} onClose={() => setModalOpen(false)} lang={lang} />}
    </>
  );
}

function InvestorTable({ investors, lang }: { investors: InvestorInfo[]; lang: Lang }) {
  const [page, setPage] = useState(0);
  const totalPages = Math.ceil(investors.length / PAGE_SIZE);
  const slice = investors.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);
  const from = page * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE + PAGE_SIZE, investors.length);

  return (
    <div className="bg-white rounded-xl shadow-sm overflow-hidden">
      {/* Table header */}
      <div className="grid grid-cols-[1fr_40px_80px_90px] gap-x-4 px-4 py-2.5 border-b border-gray-100">
        <span className="text-xs font-semibold text-gray-400">{t("col_name", lang)}</span>
        <span className="text-xs font-semibold text-gray-400 text-center">{t("col_tier", lang)}</span>
        <span className="text-xs font-semibold text-gray-400">{t("col_type", lang)}</span>
        <span className="text-xs font-semibold text-gray-400">{t("col_stage", lang)}</span>
      </div>

      {/* Rows */}
      <div className="divide-y divide-gray-50">
        {slice.map((inv, i) => (
          <div key={i} className="grid grid-cols-[1fr_40px_80px_90px] gap-x-4 px-4 py-3 items-center">
            {/* Name + avatar */}
            <div className="flex items-center gap-2 min-w-0">
              <InvestorAvatar inv={{ name: inv.name, logo: inv.logo }} size={7} />
              <span className="text-sm text-gray-800 truncate">{inv.name}</span>
              {inv.is_lead && (
                <span className="text-[10px] font-semibold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded shrink-0">
                  {t("lead_badge", lang)}
                </span>
              )}
            </div>

            {/* Tier */}
            <span className="text-sm text-gray-600 text-center">
              {inv.tier ?? "—"}
            </span>

            {/* Type / category */}
            <span className="text-sm text-gray-600 truncate capitalize">
              {inv.category ?? "—"}
            </span>

            {/* Stages */}
            <div className="flex flex-wrap gap-1">
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
            {fmtPagination(from, to, investors.length, lang)}
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

export default function FundsList({ investors, fundingRounds, lang }: FundsListProps) {
  if (fundingRounds.length === 0 && investors.length === 0) {
    return (
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <p className="text-sm text-gray-500 italic">{t("no_funding_data", lang)}</p>
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
              <span className="text-sm text-gray-500">{t("total_raised", lang)}</span>
              <span className="text-base font-bold text-gray-900">{formatUsd(totalRaised)}</span>
            </div>
          )}
          <div className="space-y-2">
            {fundingRounds.map((r, i) => (
              <RoundCard key={i} round={r} lang={lang} />
            ))}
          </div>
        </>
      )}

      {investors.length > 0 && (
        <InvestorTable investors={investors} lang={lang} />
      )}
    </div>
  );
}
