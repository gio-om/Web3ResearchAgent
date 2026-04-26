/* ──────────────────────────────────────────────────────────
   SVG icon components – inline so no extra deps are needed.
   ────────────────────────────────────────────────────────── */

function IconX() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.748l7.73-8.835L1.254 2.25H8.08l4.253 5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function IconDiscord() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
    </svg>
  );
}

function IconCryptoRank() {
  /* Matches the CryptoRank "C>" mark on a blue background */
  return (
    <svg viewBox="0 0 40 40" fill="none" className="h-5 w-5">
      <rect width="40" height="40" rx="8" fill="#1A73E8" />
      {/* C arc */}
      <path
        d="M26 13.5A9.5 9.5 0 1 0 26 26.5"
        stroke="white"
        strokeWidth="3.5"
        strokeLinecap="round"
        fill="none"
      />
      {/* > chevron */}
      <path
        d="M24 17l4 3.5L24 24"
        stroke="white"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function IconWebsite() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );
}

function IconTelegram() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.19 13.68l-2.965-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.963.879z" />
    </svg>
  );
}

function IconGitHub() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  );
}

function IconLinkedIn() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

function IconMedium() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M13.54 12a6.8 6.8 0 0 1-6.77 6.82A6.8 6.8 0 0 1 0 12a6.8 6.8 0 0 1 6.77-6.82A6.8 6.8 0 0 1 13.54 12zm7.42 0c0 3.54-1.51 6.42-3.38 6.42-1.87 0-3.39-2.88-3.39-6.42s1.52-6.42 3.39-6.42 3.38 2.88 3.38 6.42M24 12c0 3.17-.53 5.75-1.19 5.75-.66 0-1.19-2.58-1.19-5.75s.53-5.75 1.19-5.75C23.47 6.25 24 8.83 24 12z" />
    </svg>
  );
}

function IconReddit() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z" />
    </svg>
  );
}

function IconYouTube() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M23.495 6.205a3.007 3.007 0 0 0-2.088-2.088c-1.87-.501-9.396-.501-9.396-.501s-7.507-.01-9.396.501A3.007 3.007 0 0 0 .527 6.205a31.247 31.247 0 0 0-.522 5.805 31.247 31.247 0 0 0 .522 5.783 3.007 3.007 0 0 0 2.088 2.088c1.868.502 9.396.502 9.396.502s7.506 0 9.396-.502a3.007 3.007 0 0 0 2.088-2.088 31.247 31.247 0 0 0 .5-5.783 31.247 31.247 0 0 0-.5-5.805zM9.609 15.601V8.408l6.264 3.602z" />
    </svg>
  );
}

function IconDocs() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function IconGitbook() {
  /* Book icon */
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M21 4H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1zm-1 15H7a1 1 0 0 1 0-2h13v1a1 1 0 0 1-1 1zM3 6a1 1 0 0 0-1 1v13a3 3 0 0 0 3 3h13a1 1 0 0 0 0-2H5a1 1 0 0 1-1-1V7a1 1 0 0 0-1-1z"/>
    </svg>
  );
}

function IconWhitepaper() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="12" y1="18" x2="12" y2="12" />
      <line x1="9" y1="15" x2="15" y2="15" />
    </svg>
  );
}

function IconBlog() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  );
}

function IconCoinMarketCap() {
  /* CMC logo approximation */
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm4.5 13.5c-.4 0-.75-.15-1.02-.4l-2.1-2.1a.7.7 0 0 0-.99 0l-.88.88c-.27.27-.64.43-1.04.43-.81 0-1.47-.66-1.47-1.47V9.5c0-.81.66-1.47 1.47-1.47.4 0 .77.16 1.04.43l.88.88a.7.7 0 0 0 .99 0l2.1-2.1c.27-.27.62-.4 1.02-.4.81 0 1.47.66 1.47 1.47v5.12c0 .81-.66 1.47-1.47 1.47z" />
    </svg>
  );
}

function IconCoinGecko() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <circle cx="12" cy="12" r="10" fill="#8BC34A" />
      <circle cx="9" cy="10" r="1.5" fill="white" />
      <circle cx="15" cy="10" r="1.5" fill="white" />
      <path d="M8.5 15.5c.9 1.2 2.1 1.8 3.5 1.8s2.6-.6 3.5-1.8" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
    </svg>
  );
}

function IconLinktree() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
      <path d="M7.953 15.066c-.08.163-.08.324 0 .486l2.637 4.74a.49.49 0 0 0 .435.252h1.95a.49.49 0 0 0 .435-.252l2.637-4.74c.08-.162.08-.323 0-.486l-2.637-4.74a.49.49 0 0 0-.435-.252h-1.95a.49.49 0 0 0-.435.252zm-5.196-8.87c-.08.163-.08.325 0 .487l1.43 2.572a.49.49 0 0 0 .434.251h2.86a.49.49 0 0 0 .434-.251l1.43-2.572c.08-.162.08-.324 0-.487L7.915.826A.49.49 0 0 0 7.48.575H4.622a.49.49 0 0 0-.434.251zm10.487 0c-.08.163-.08.325 0 .487l1.43 2.572a.49.49 0 0 0 .434.251h2.86a.49.49 0 0 0 .434-.251l1.43-2.572c.08-.162.08-.324 0-.487L18.403.826a.49.49 0 0 0-.435-.251h-2.858a.49.49 0 0 0-.434.251z"/>
    </svg>
  );
}


/* ──────────────────────────────────────────────────────────
   Icon + colour mapping
   ────────────────────────────────────────────────────────── */

interface LinkConfig {
  label: string;
  icon: JSX.Element;
  color: string; // icon colour (Tailwind text-* class)
}

const LINK_CONFIG: Record<string, LinkConfig> = {
  website:       { label: "Website",       icon: <IconWebsite />,       color: "text-gray-600"   },
  twitter:       { label: "X / Twitter",   icon: <IconX />,             color: "text-gray-900"   },
  telegram:      { label: "Telegram",      icon: <IconTelegram />,      color: "text-sky-500"    },
  discord:       { label: "Discord",       icon: <IconDiscord />,       color: "text-indigo-500" },
  github:        { label: "GitHub",        icon: <IconGitHub />,        color: "text-gray-800"   },
  linkedin:      { label: "LinkedIn",      icon: <IconLinkedIn />,      color: "text-sky-600"    },
  medium:        { label: "Medium",        icon: <IconMedium />,        color: "text-gray-800"   },
  reddit:        { label: "Reddit",        icon: <IconReddit />,        color: "text-orange-500" },
  youtube:       { label: "YouTube",       icon: <IconYouTube />,       color: "text-red-500"    },
  docs:          { label: "Docs",          icon: <IconDocs />,          color: "text-purple-500" },
  gitbook:       { label: "GitBook",       icon: <IconGitbook />,       color: "text-gray-700"   },
  whitepaper:    { label: "Whitepaper",    icon: <IconWhitepaper />,    color: "text-blue-600"   },
  blog:          { label: "Blog",          icon: <IconBlog />,          color: "text-green-600"  },
  coinmarketcap: { label: "CoinMarketCap", icon: <IconCoinMarketCap />, color: "text-blue-500"   },
  coingecko:     { label: "CoinGecko",     icon: <IconCoinGecko />,     color: "text-green-500"  },
  linktree:      { label: "Linktree",      icon: <IconLinktree />,      color: "text-green-600"  },
  cryptorank:    { label: "CryptoRank",    icon: <IconCryptoRank />,    color: "text-white"      },
};

// Only "social" keys shown in this component — docs/technical links go to DocumentationAnalysis
const SOCIAL_ORDER = [
  "website", "twitter", "telegram", "discord",
  "cryptorank", "coingecko", "coinmarketcap",
  "github", "linkedin", "medium", "blog",
  "reddit", "youtube", "linktree",
  "docs",
];

interface ProjectLinksProps {
  links: Record<string, string>;
}

export default function ProjectLinks({ links }: ProjectLinksProps) {
  const entries = SOCIAL_ORDER
    .filter((key) => links[key])
    .map((key) => ({ key, url: links[key], cfg: LINK_CONFIG[key] }));

  const all = entries;
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
          className={`flex h-9 w-9 items-center justify-center rounded-full bg-white shadow-sm border border-gray-200 transition-colors hover:bg-gray-50 ${cfg.color}`}
        >
          {cfg.icon}
        </a>
      ))}
    </div>
  );
}
