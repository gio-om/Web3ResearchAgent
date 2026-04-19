from pydantic import BaseModel, Field
from enum import Enum


class RiskLevel(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class RiskCategory(str, Enum):
    TOKENOMICS = "tokenomics"
    TEAM = "team"
    SOCIAL = "social"
    INVESTORS = "investors"
    GENERAL = "general"


class FundingRound(BaseModel):
    round_type: str                    # "Seed", "Series A", "Private", "Public"
    date: str | None = None
    amount_usd: float | None = None
    valuation_usd: float | None = None
    token_price: float | None = None
    investors: list[str] = Field(default_factory=list)


class VestingSchedule(BaseModel):
    category: str                      # "Team", "Investors", "Community", "Treasury"
    allocation_pct: float              # Процент от общей эмиссии
    cliff_months: int | None = None
    vesting_months: int | None = None
    tge_unlock_pct: float | None = None  # Процент, разблокированный на TGE
    round_date: str | None = None      # Дата раунда / старта аллокации (YYYY-MM-DD)
    unlock_type: str | None = None     # "linear", "vested_at_tge", etc.
    tokens: int | None = None          # Абсолютное число токенов
    unlocked_percent: float | None = None  # % токенов этой аллокации уже разблокированных


class TokenomicsData(BaseModel):
    token_name: str
    token_symbol: str = ""
    total_supply: float | None = None
    circulating_supply: float | None = None
    max_supply: float | None = None
    fdv_usd: float | None = None
    current_mcap_usd: float | None = None
    current_price_usd: float | None = None
    ath_usd: float | None = None
    tge_start_date: str | None = None  # Дата TGE (YYYY-MM-DD)
    vesting_schedules: list[VestingSchedule] = Field(default_factory=list)


class InvestorInfo(BaseModel):
    name: str
    tier: str                          # "Tier 1", "Tier 2", "Tier 3"
    entry_price: float | None = None
    current_roi_x: float | None = None
    portfolio_count: int | None = None
    confirmed_by_investor: bool = False  # Подтверждено ли самим фондом


class TeamMember(BaseModel):
    name: str
    role: str
    linkedin_url: str | None = None
    verified: bool = False             # Подтверждён ли профиль
    previous_companies: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    profile_created_recently: bool | None = None


class SocialMetrics(BaseModel):
    platform: str = "twitter"
    handle: str = ""
    followers_count: int = 0
    following_count: int = 0
    engagement_rate: float = 0.0
    kol_mentions: list[str] = Field(default_factory=list)
    sentiment_score: float = 0.0       # -1.0 .. 1.0
    bot_follower_pct: float | None = None
    key_concerns: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)


class RiskFlag(BaseModel):
    type: RiskLevel                    # "red" | "yellow" | "green"
    category: RiskCategory             # "tokenomics" | "team" | "social" | "investors"
    message: str
    source: str                        # Откуда получена информация
    severity_score: int = 0            # 0–10 для сортировки


class ScoreCard(BaseModel):
    tokenomics_score: int = 0          # 0–25
    investors_score: int = 0           # 0–25
    team_score: int = 0                # 0–25
    social_score: int = 0              # 0–25
    penalty: int = 0                   # Штрафы за red/yellow flags
    overall_score: int = 0             # 0–100


class AnalysisReport(BaseModel):
    project_name: str
    project_slug: str = ""
    overall_score: int = 0             # 0–100
    recommendation: str = "DYOR"       # "DYOR" | "Interesting" | "Strong" | "Avoid"
    scorecard: ScoreCard | None = None
    tokenomics: TokenomicsData | None = None
    funding_rounds: list[FundingRound] = Field(default_factory=list)
    investors: list[InvestorInfo] = Field(default_factory=list)
    team: list[TeamMember] = Field(default_factory=list)
    social: SocialMetrics | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    summary: str = ""                  # LLM-генерированное резюме
    data_sources: list[str] = Field(default_factory=list)
