export interface ScoreCard {
  tokenomics_score: number;
  investors_score: number;
  team_score: number;
  social_score: number;
  overall_score: number;
}

export interface RiskFlag {
  type: "red" | "yellow" | "green";
  category: string;
  message: string;
}

export interface VestingSchedule {
  recipient_type: string;
  total_percent: number;
  cliff_months: number;
  vesting_months: number;
  tge_percent: number;
  round_date?: string | null;
  unlock_type?: string | null;
  tokens?: number;
  unlocked_percent?: number | null;
}

export interface InvestorChip {
  name: string;
  logo?: string | null;
}

export interface FundingRound {
  round_name: string;
  amount_usd: number | null;
  date: string | null;
  valuation_usd: number | null;
  investors?: InvestorChip[];
  announcement?: string | null;
}

export interface InvestorInfo {
  name: string;
  logo?: string | null;
  tier: string | null;
  round?: string;
  stages?: string[];
  category?: string | null;
  is_lead?: boolean;
  portfolio_notable: string[];
}

export interface ExperienceEntry {
  position: string;
  company: string;
  period?: string;
  description?: string;
}

export interface EducationEntry {
  school: string;
  degree?: string;
  field?: string;
  period?: string;
}

export interface TeamMember {
  name: string;
  role: string;
  linkedin_url: string | null;
  twitter_url?: string | null;
  verified: boolean;
  location?: string;
  bio?: string;
  experience?: ExperienceEntry[];
  education?: EducationEntry[];
  top_skills?: string[];
  photo?: string;
  previous_companies?: string[];
  has_tier1_background?: boolean;
  profile_notes?: string;
  source?: string;
}

export interface TopPost {
  url: string;
  text: string;
  likes: number;
  retweets: number;
  views: number;
}

export interface SocialData {
  handle?: string;
  followers_count?: number;
  following_count?: number;
  engagement_rate?: number;
  avg_views_per_tweet?: number;
  top_posts?: TopPost[];
  tweet_count?: number;
  sentiment_score?: number;
  key_concerns?: string[];
  positive_signals?: string[];
  kol_mentions?: string[];
  bot_activity_signals?: string[];
  overall_assessment?: string;
  error?: string;
}

export interface TokenomicsData {
  total_supply: number | null;
  circulating_supply: number | null;
  max_supply?: number | null;
  token_symbol?: string;
  tge_start_date?: string | null;
  vesting_schedules: VestingSchedule[];
  token_distribution: Record<string, number>;
}

export interface DocumentationInfo {
  project_description?: string | null;
  key_features?: string[];
  token_name?: string | null;
  token_symbol?: string | null;
  total_supply?: number | null;
  unusual_conditions?: string[];
  data_completeness?: "high" | "medium" | "low" | null;
  docs_url?: string | null;
  scraped_pages?: string[];
  project_links?: Record<string, string>;
  scraped_from_website?: boolean;
  website_url?: string | null;
  error?: string | null;
}

export interface Report {
  project_name: string;
  project_slug: string;
  overall_score: number;
  recommendation: "DYOR" | "Interesting" | "Strong" | "Avoid";
  scorecard: ScoreCard;
  coingecko_summary: { fdv_usd: number | null; market_cap_usd: number | null };
  tokenomics: TokenomicsData;
  funding_rounds: FundingRound[];
  investors: InvestorInfo[];
  team: TeamMember[];
  social?: SocialData;
  documentation?: DocumentationInfo;
  risk_flags: RiskFlag[];
  strengths: string[];
  weaknesses: string[];
  summary: string;
  data_sources: string[];
  project_links?: Record<string, string>;
  id: number;
}

export interface PortfolioItem {
  project_id: number;
  project_name: string;
  added_at: string;
}

export interface CompareResult {
  project_a: Report;
  project_b: Report;
}
