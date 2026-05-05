import { useState } from "react";
import type { DocumentationInfo } from "../types";
import { t, fmtPages, fmtProjectLinks } from "../i18n";
import type { Lang } from "../i18n";

interface Props {
  documentation?: DocumentationInfo;
  lang: Lang;
}

const COMPLETENESS_BADGE: Record<string, string> = {
  high:   "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  low:    "bg-red-100 text-red-700",
};

function fmt(n: number | null | undefined): string {
  if (n == null) return "N/A";
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000)     return `${(n / 1_000_000).toFixed(0)}M`;
  return n.toLocaleString();
}

export default function DocumentationAnalysis({ documentation, lang }: Props) {
  const [linksOpen, setLinksOpen] = useState(false);
  if (!documentation) {
    return (
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <p className="text-sm text-gray-400 italic">{t("no_docs_data", lang)}</p>
      </div>
    );
  }

  if (documentation.error && !documentation.docs_url) {
    return (
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <p className="text-sm text-gray-400 italic">
          {t("docs_not_found", lang)} {documentation.error}
        </p>
      </div>
    );
  }

  const completeness = documentation.data_completeness;
  const conditions = documentation.unusual_conditions ?? [];
  const pages = documentation.scraped_pages ?? [];
  const features = documentation.key_features ?? [];
  const projectLinks = Object.entries(documentation.project_links ?? {});

  const COMPLETENESS_KEY: Record<string, "completeness_high" | "completeness_medium" | "completeness_low"> = {
    high: "completeness_high",
    medium: "completeness_medium",
    low: "completeness_low",
  };
  const completenessLabel = completeness && COMPLETENESS_KEY[completeness]
    ? `${t(COMPLETENESS_KEY[completeness], lang)} ${t("completeness_data", lang)}`
    : completeness ?? null;

  return (
    <div className="bg-white rounded-xl p-4 shadow-sm space-y-3">
      {/* Top row: docs/website link + completeness badge */}
      <div className="flex items-start justify-between gap-2">
        {documentation.docs_url ? (
          <a
            href={documentation.docs_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-indigo-600 hover:underline"
          >
            <span className="text-base">📄</span>
            {documentation.docs_url.length > 45
              ? documentation.docs_url.slice(0, 45) + "…"
              : documentation.docs_url}
          </a>
        ) : documentation.scraped_from_website && documentation.website_url ? (
          <a
            href={documentation.website_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-orange-500 hover:underline"
          >
            <span className="text-base">🌐</span>
            {documentation.website_url.length > 45
              ? documentation.website_url.slice(0, 45) + "…"
              : documentation.website_url}
          </a>
        ) : <span />}
        {completenessLabel && completeness && (
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${COMPLETENESS_BADGE[completeness] ?? "bg-gray-100 text-gray-500"}`}>
            {completenessLabel}
          </span>
        )}
      </div>

      {/* Fallback notice */}
      {documentation.scraped_from_website && (
        <div className="flex items-start gap-2 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-700">
          <span className="shrink-0 mt-0.5">ℹ️</span>
          <span>{t("docs_fallback_notice", lang)}</span>
        </div>
      )}

      {/* Project description */}
      {documentation.project_description && (
        <p className="text-sm text-gray-700 leading-relaxed">
          {documentation.project_description}
        </p>
      )}

      {/* Key features */}
      {features.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">{t("key_features", lang)}</p>
          <ul className="space-y-1">
            {features.map((f, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-gray-700">
                <span className="mt-0.5 shrink-0 text-indigo-400">•</span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Token info */}
      {(documentation.token_name || documentation.token_symbol || documentation.total_supply != null) && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-gray-100 pt-2">
          {(documentation.token_name || documentation.token_symbol) && (
            <p className="text-xs text-gray-500">
              {t("token_label", lang)}{" "}
              <span className="font-medium text-gray-700">
                {documentation.token_name ?? ""}
                {documentation.token_symbol && ` (${documentation.token_symbol})`}
              </span>
            </p>
          )}
          {documentation.total_supply != null && (
            <p className="text-xs text-gray-500">
              {t("supply_label", lang)} <span className="font-medium text-gray-700">{fmt(documentation.total_supply)}</span>
            </p>
          )}
        </div>
      )}

      {/* Scraped pages count */}
      {pages.length > 0 && (
        <p className="text-xs text-gray-400">
          {fmtPages(pages.length, lang)}
        </p>
      )}

      {/* Unusual conditions */}
      {conditions.length > 0 && (
        <div className="space-y-1.5 pt-1 border-t border-gray-100">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            {t("unusual_conditions", lang)}
          </p>
          <ul className="space-y-1">
            {conditions.map((c, i) => (
              <li
                key={i}
                className="flex items-start gap-2 rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800"
              >
                <span className="mt-0.5 shrink-0">⚠️</span>
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* No issues found */}
      {conditions.length === 0 && (documentation.docs_url || documentation.scraped_from_website) && (
        <p className="text-xs text-green-600 flex items-center gap-1">
          <span>✅</span> {t("no_unusual_conditions", lang)}
        </p>
      )}

      {/* Collapsible project links from docs */}
      {projectLinks.length > 0 && (
        <div className="border-t border-gray-100 pt-2">
          <button
            onClick={() => setLinksOpen((v) => !v)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors w-full text-left"
          >
            <span className="transition-transform duration-200" style={{ display: "inline-block", transform: linksOpen ? "rotate(90deg)" : "rotate(0deg)" }}>▶</span>
            {fmtProjectLinks(projectLinks.length, lang)}
          </button>
          {linksOpen && (
            <ul className="mt-2 space-y-1.5">
              {projectLinks.map(([label, url]) => (
                <li key={label}>
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-xs text-indigo-600 hover:underline min-w-0"
                  >
                    <span className="shrink-0 text-gray-400">🔗</span>
                    <span className="font-medium capitalize text-gray-600 shrink-0 max-w-[45%] truncate">{label}:</span>
                    <span className="break-all min-w-0">{url.length > 50 ? url.slice(0, 50) + "…" : url}</span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
