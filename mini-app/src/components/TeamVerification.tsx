import { useState } from "react";
import type { TeamMember } from "../types";
import { t } from "../i18n";
import type { Lang } from "../i18n";

interface TeamVerificationProps {
  team: TeamMember[];
  lang: Lang;
}

function roleScore(role: string): number {
  const r = role.toLowerCase();
  if (r.includes("founder")) return 10;
  if (/\bceo\b/.test(r) || r.includes("chief executive")) return 9;
  if (/\bcto\b/.test(r) || r.includes("chief tech")) return 8;
  if (/\bcoo\b/.test(r) || r.includes("chief operat")) return 7;
  if (/\bcfo\b/.test(r) || r.includes("chief financ")) return 7;
  if (r.startsWith("chief") || /\bc[a-z]o\b/.test(r)) return 6;
  if (r.startsWith("vp ") || r.includes("vice president")) return 5;
  if (r.startsWith("head of") || r.startsWith("head,")) return 4;
  if (r.includes("director")) return 3;
  if (r.includes("lead") || r.includes("principal")) return 2;
  return 1;
}

function Avatar({
  photo,
  name,
  size = "md",
}: {
  photo?: string;
  name: string;
  size?: "sm" | "md";
}) {
  const [failed, setFailed] = useState(false);
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  const cls =
    size === "sm"
      ? "h-8 w-8 rounded-full flex-shrink-0 text-xs"
      : "h-12 w-12 rounded-full flex-shrink-0 text-sm";

  if (photo && !failed) {
    return (
      <img
        src={photo}
        alt={name}
        onError={() => setFailed(true)}
        className={`${cls} object-cover`}
      />
    );
  }
  return (
    <div
      className={`${cls} bg-indigo-100 flex items-center justify-center font-semibold text-indigo-600`}
    >
      {initials}
    </div>
  );
}

const TIER1_NAMES = new Set([
  "google", "meta", "apple", "amazon", "microsoft", "netflix",
  "coinbase", "binance", "a16z", "andreessen horowitz",
  "polychain", "paradigm", "sequoia", "jump", "delphi",
  "ethereum foundation", "solana foundation", "consensys",
  "circle", "ripple", "chainalysis", "opensea",
]);

function isTier1(company: string): boolean {
  const lower = company.toLowerCase();
  return [...TIER1_NAMES].some((t) => lower.includes(t));
}

function PrevCompanies({ companies }: { companies: string[] }) {
  if (companies.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {companies.map((c, i) => (
        <span
          key={i}
          className={`rounded px-1.5 py-0.5 text-xs font-medium ${
            isTier1(c)
              ? "bg-amber-100 text-amber-700"
              : "bg-gray-100 text-gray-500"
          }`}
        >
          {c}
        </span>
      ))}
    </div>
  );
}

function KeyMemberCard({ member }: { member: TeamMember }) {
  const prev = member.previous_companies ?? [];

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
      <div className="flex gap-3">
        <Avatar photo={member.photo} name={member.name} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-semibold text-gray-900">
              {member.name}
            </span>
            {member.verified && (
              <span className="rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-700">
                ✓
              </span>
            )}
            {member.has_tier1_background && (
              <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700">
                Tier-1
              </span>
            )}
          </div>
          <p className="mt-0.5 text-xs font-medium text-indigo-600">
            {member.role}
          </p>
          {member.location && (
            <p className="mt-0.5 text-xs text-gray-400">{member.location}</p>
          )}
        </div>
        {member.linkedin_url && (
          <a
            href={member.linkedin_url}
            target="_blank"
            rel="noreferrer"
            className="mt-0.5 shrink-0 text-xs text-blue-500"
          >
            LinkedIn ↗
          </a>
        )}
      </div>

      {member.bio && (
        <p className="mt-3 line-clamp-3 text-xs text-gray-600">{member.bio}</p>
      )}

      <PrevCompanies companies={prev} />
    </div>
  );
}

function AllMemberRow({ member }: { member: TeamMember }) {
  return (
    <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg border border-gray-100 bg-gray-50">
      <Avatar photo={member.photo} name={member.name} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-sm font-semibold text-gray-800">
            {member.name}
          </span>
          {member.verified && (
            <span className="shrink-0 rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-700">
              ✓
            </span>
          )}
          {member.has_tier1_background && (
            <span className="shrink-0 rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700">
              Tier-1
            </span>
          )}
        </div>
        <p className="truncate text-xs text-gray-500">{member.role}</p>
      </div>
      {member.linkedin_url && (
        <a
          href={member.linkedin_url}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 text-xs text-blue-500"
        >
          ↗
        </a>
      )}
    </div>
  );
}

export default function TeamVerification({ team, lang }: TeamVerificationProps) {
  if (team.length === 0) {
    return (
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <p className="text-sm italic text-gray-500">{t("no_team_data", lang)}</p>
      </div>
    );
  }

  const sorted = [...team].sort((a, b) => roleScore(b.role) - roleScore(a.role));
  const keyMembers = sorted.slice(0, 5);

  return (
    <div className="space-y-3">
      {keyMembers.map((m, i) => (
        <KeyMemberCard key={i} member={m} />
      ))}

      {team.length > 0 && (
        <div className="rounded-xl border border-gray-100 bg-white p-3 shadow-sm">
          <p className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
            {t("all_members", lang)} ({team.length})
          </p>
          <div className="space-y-1.5">
            {sorted.map((m, i) => (
              <AllMemberRow key={i} member={m} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
