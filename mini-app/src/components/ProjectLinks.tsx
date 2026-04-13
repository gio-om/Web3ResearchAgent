interface LinkConfig {
  label: string;
  icon: string;
  bg: string;
}

const LINK_CONFIG: Record<string, LinkConfig> = {
  website:    { label: "Website",    icon: "🌐", bg: "bg-gray-100 hover:bg-gray-200" },
  twitter:    { label: "X / Twitter",icon: "✕",  bg: "bg-black/5 hover:bg-black/10" },
  telegram:   { label: "Telegram",   icon: "✈",  bg: "bg-blue-50 hover:bg-blue-100" },
  discord:    { label: "Discord",    icon: "💬", bg: "bg-indigo-50 hover:bg-indigo-100" },
  github:     { label: "GitHub",     icon: "⌥",  bg: "bg-gray-100 hover:bg-gray-200" },
  linkedin:   { label: "LinkedIn",   icon: "in", bg: "bg-sky-50 hover:bg-sky-100" },
  medium:     { label: "Medium",     icon: "M",  bg: "bg-gray-100 hover:bg-gray-200" },
  reddit:     { label: "Reddit",     icon: "🔴", bg: "bg-orange-50 hover:bg-orange-100" },
  youtube:    { label: "YouTube",    icon: "▶",  bg: "bg-red-50 hover:bg-red-100" },
  docs:       { label: "Docs",       icon: "📄", bg: "bg-purple-50 hover:bg-purple-100" },
  cryptorank: { label: "CryptoRank", icon: "₿",  bg: "bg-amber-50 hover:bg-amber-100" },
};

const LINK_ORDER = [
  "website", "twitter", "telegram", "discord",
  "docs", "cryptorank", "github", "linkedin",
  "medium", "reddit", "youtube",
];

interface ProjectLinksProps {
  links: Record<string, string>;
}

export default function ProjectLinks({ links }: ProjectLinksProps) {
  const known = new Set(LINK_ORDER);

  const entries = LINK_ORDER
    .filter((key) => links[key])
    .map((key) => ({ key, url: links[key], cfg: LINK_CONFIG[key] }));

  const extra = Object.entries(links)
    .filter(([k]) => !known.has(k) && links[k])
    .map(([key, url]) => ({
      key, url,
      cfg: { label: key, icon: "🔗", bg: "bg-gray-100 hover:bg-gray-200" },
    }));

  const all = [...entries, ...extra];
  if (all.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {all.map(({ key, url, cfg }) => (
        <a
          key={key}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          title={cfg.label}
          className={`flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold text-gray-700 transition-colors ${cfg.bg}`}
        >
          {cfg.icon}
        </a>
      ))}
    </div>
  );
}
