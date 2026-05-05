import type { SocialData, TopPost } from "../types";
import ProjectLinks from "./ProjectLinks";
import { t } from "../i18n";
import type { Lang } from "../i18n";

interface SocialAnalysisProps {
  social?: SocialData;
  links?: Record<string, string>;
  lang: Lang;
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function SentimentBar({ score, lang }: { score: number; lang: Lang }) {
  const pct = Math.round(((score + 1) / 2) * 100);
  const color =
    score >= 0.3 ? "bg-green-500" :
    score <= -0.3 ? "bg-red-500" :
    "bg-yellow-400";

  return (
    <div className="flex items-center gap-2">
      <span className="w-14 text-xs text-gray-400">{t("sentiment", lang)}</span>
      <div className="relative h-2 flex-1 rounded-full bg-gray-100">
        <div
          className={`absolute h-2 w-2 -translate-x-1/2 rounded-full ${color}`}
          style={{ left: `${pct}%` }}
        />
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-red-200 via-yellow-200 to-green-200 opacity-40" />
      </div>
      <span className="w-8 text-right text-xs font-semibold text-gray-600">
        {score > 0 ? "+" : ""}{score.toFixed(2)}
      </span>
    </div>
  );
}

function TagList({ items, icon }: { items: string[]; icon: string }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 rounded-md bg-gray-50 px-2 py-0.5 text-xs text-gray-600"
        >
          {icon} {item}
        </span>
      ))}
    </div>
  );
}

export default function SocialAnalysis({ social, links, lang }: SocialAnalysisProps) {
  const hasLinks = Object.keys(links ?? {}).length > 0;
  const hasTwitter = social?.handle || (social?.followers_count ?? 0) > 0;
  const hasAnalysis =
    (social?.key_concerns?.length ?? 0) > 0 ||
    (social?.positive_signals?.length ?? 0) > 0 ||
    (social?.kol_mentions?.length ?? 0) > 0 ||
    social?.overall_assessment;

  if (!hasLinks && !hasTwitter && !hasAnalysis) {
    return (
      <p className="text-xs italic text-gray-400">{t("no_social_data", lang)}</p>
    );
  }

  return (
    <div className="space-y-4">

      {/* ── Links row ── */}
      {hasLinks && <ProjectLinks links={links!} />}

      {/* ── Twitter card ── */}
      {hasTwitter && (
        <div className="rounded-xl border border-gray-100 bg-white p-3 shadow-sm space-y-3">

          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-black/5 text-sm font-bold text-gray-800">
                ✕
              </span>
              <div>
                {social?.handle && (
                  <p className="text-sm font-semibold text-gray-800">
                    @{social.handle}
                  </p>
                )}
                {social?.tweet_count != null && (
                  <p className="text-xs text-gray-400">{social.tweet_count} {t("tweets_analysed", lang)}</p>
                )}
              </div>
            </div>
            {social?.followers_count != null && (
              <div className="text-right">
                <p className="text-base font-bold text-gray-800">
                  {fmt(social.followers_count)}
                </p>
                <p className="text-xs text-gray-400">{t("followers", lang)}</p>
              </div>
            )}
          </div>

          {/* Stats row */}
          {(social?.engagement_rate != null) && (
            <div className="flex flex-wrap gap-2">
              <div className="rounded-lg bg-gray-50 px-3 py-1.5 text-center">
                <p className="text-xs text-gray-400">{t("engagement", lang)}</p>
                <p className="text-sm font-semibold text-gray-700">
                  {(social.engagement_rate * 100).toFixed(2)}%
                </p>
              </div>
              {social?.avg_views_per_tweet != null && social.avg_views_per_tweet > 0 && (
                <div className="rounded-lg bg-gray-50 px-3 py-1.5 text-center">
                  <p className="text-xs text-gray-400">{t("avg_views", lang)}</p>
                  <p className="text-sm font-semibold text-gray-700">
                    {fmt(social.avg_views_per_tweet)}
                  </p>
                </div>
              )}
              {social?.following_count != null && (
                <div className="rounded-lg bg-gray-50 px-3 py-1.5 text-center">
                  <p className="text-xs text-gray-400">{t("following", lang)}</p>
                  <p className="text-sm font-semibold text-gray-700">
                    {fmt(social.following_count)}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Sentiment bar */}
          {social?.sentiment_score != null && (
            <SentimentBar score={social.sentiment_score} lang={lang} />
          )}

          {/* Overall assessment */}
          {social?.overall_assessment && (
            <p className="text-xs italic text-gray-500 leading-relaxed">
              "{social.overall_assessment}"
            </p>
          )}

          {/* Top posts */}
          {(social?.top_posts?.length ?? 0) > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
                {t("top_posts", lang)}
              </p>
              <div className="space-y-2">
                {social!.top_posts!.map((post: TopPost, i: number) => (
                  <a
                    key={i}
                    href={post.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 hover:bg-gray-100 transition-colors"
                  >
                    <p className="text-xs text-gray-700 leading-relaxed line-clamp-2 mb-1.5">
                      {post.text}{post.text.length >= 120 ? "…" : ""}
                    </p>
                    <div className="flex gap-3 text-xs text-gray-400">
                      <span>❤️ {fmt(post.likes)}</span>
                      <span>🔁 {fmt(post.retweets)}</span>
                      {post.views > 0 && <span>👁 {fmt(post.views)}</span>}
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Analysis details ── */}
      {hasAnalysis && (
        <div className="space-y-3">
          {(social?.positive_signals?.length ?? 0) > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                {t("positive_signals", lang)}
              </p>
              <TagList items={social!.positive_signals!} icon="✅" />
            </div>
          )}

          {(social?.key_concerns?.length ?? 0) > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                {t("key_concerns", lang)}
              </p>
              <TagList items={social!.key_concerns!} icon="⚠️" />
            </div>
          )}

          {(social?.kol_mentions?.length ?? 0) > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                {t("kol_mentions", lang)}
              </p>
              <TagList items={social!.kol_mentions!} icon="⭐" />
            </div>
          )}

          {(social?.bot_activity_signals?.length ?? 0) > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                {t("bot_activity_signals", lang)}
              </p>
              <TagList items={social!.bot_activity_signals!} icon="🤖" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
