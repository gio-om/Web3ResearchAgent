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
}

export interface FundingRound {
  round_name: string;
  amount_usd: number | null;
  date: string | null;
  valuation_usd: number | null;
}

export interface InvestorInfo {
  name: string;
  tier: string | null;
  portfolio_notable: string[];
}

export interface TeamMember {
  name: string;
  role: string;
  linkedin_url: string | null;
  twitter_url: string | null;
  verified: boolean;
  previous_projects: string[];
}

export interface SocialMetrics {
  twitter_followers: number | null;
  twitter_engagement_rate: number | null;
  discord_members: number | null;
  telegram_members: number | null;
  sentiment_score: number | null;
}

export interface TokenomicsData {
  total_supply: number | null;
  circulating_supply: number | null;
  vesting_schedules: VestingSchedule[];
  token_distribution: Record<string, number>;
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
  social: SocialMetrics;
  risk_flags: RiskFlag[];
  strengths: string[];
  weaknesses: string[];
  summary: string;
  data_sources: string[];
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
