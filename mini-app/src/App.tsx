import { useEffect, useState, Component } from "react";
import type { ReactNode } from "react";
import type { Report, PortfolioItem, CompareResult } from "./types";
import { getReport, getPortfolio, compareProjects } from "./api/client";
import { useTelegram } from "./hooks/useTelegram";
import ProjectCard from "./components/ProjectCard";
import RiskFlags from "./components/RiskFlags";
import VestingChart from "./components/VestingChart";
import TokenDistribution from "./components/TokenDistribution";
import FundsList from "./components/FundsList";
import TeamVerification from "./components/TeamVerification";
import ScoreGauge from "./components/ScoreGauge";
import SocialAnalysis from "./components/SocialAnalysis";

// ─── Error Boundary ───────────────────────────────────────────────────────────

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: string | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { error: error.message };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="flex h-screen items-center justify-center p-6">
          <p className="text-center text-red-500 text-sm">
            Render error: {this.state.error}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Shared loading / error states ───────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-gray-200 border-t-indigo-500" />
    </div>
  );
}

function ErrorScreen({ message }: { message: string }) {
  return (
    <div className="flex h-screen items-center justify-center p-6">
      <p className="text-center text-red-500">{message}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wider text-gray-400">
        {title}
      </h2>
      {children}
    </section>
  );
}

// ─── Report View ─────────────────────────────────────────────────────────────

function ReportView({ reportId }: { reportId: number }) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (reportId === 0) return;
    getReport(reportId)
      .then(setReport)
      .catch(() => setError("Failed to load report."));
  }, [reportId]);

  if (reportId === 0)
    return (
      <div className="flex h-screen items-center justify-center p-6 text-gray-400">
        No report selected.
      </div>
    );
  if (error) return <ErrorScreen message={error} />;
  if (!report) return <Spinner />;

  return (
    <div className="space-y-6 p-4 pb-10">
      <Section title="Overview">
        <ProjectCard report={report} />
      </Section>

      <Section title="Risk Flags">
        <RiskFlags flags={report.risk_flags ?? []} />
      </Section>

      <Section title="Tokenomics — Vesting">
        <VestingChart schedules={report.tokenomics?.vesting_schedules ?? []} />
      </Section>

      {Object.keys(report.tokenomics?.token_distribution ?? {}).length > 0 && (
        <Section title="Token Distribution">
          <TokenDistribution
            distribution={report.tokenomics?.token_distribution ?? {}}
          />
        </Section>
      )}

      <Section title="Funding & Investors">
        <FundsList
          investors={report.investors ?? []}
          fundingRounds={report.funding_rounds ?? []}
        />
      </Section>

      <Section title="Team">
        <TeamVerification team={report.team ?? []} />
      </Section>

      <Section title="Socials">
        <SocialAnalysis
          social={report.social}
          links={report.project_links ?? {}}
        />
      </Section>

      {(report.data_sources?.length ?? 0) > 0 && (
        <Section title="Data Sources">
          <ul className="space-y-0.5 text-xs text-gray-400">
            {(report.data_sources ?? []).map((src, i) => (
              <li key={i}>{src}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

// ─── Portfolio View ───────────────────────────────────────────────────────────

function PortfolioView({ userId }: { userId: number }) {
  const [items, setItems] = useState<PortfolioItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPortfolio(userId)
      .then(setItems)
      .catch(() => setError("Failed to load portfolio."));
  }, [userId]);

  if (error) return <ErrorScreen message={error} />;
  if (!items) return <Spinner />;

  if (items.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center p-6 text-gray-400">
        Portfolio is empty.
      </div>
    );
  }

  return (
    <div className="p-4 pb-10">
      <h1 className="mb-4 text-lg font-bold text-gray-900">Portfolio</h1>
      <ul className="space-y-2">
        {items.map((item) => (
          <li
            key={item.project_id}
            className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm"
          >
            <span className="font-semibold text-gray-800">
              {item.project_name}
            </span>
            <span className="text-xs text-gray-400">
              {new Date(item.added_at).toLocaleDateString()}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Compare View ─────────────────────────────────────────────────────────────

function CompareView({ a, b }: { a: string; b: string }) {
  const [result, setResult] = useState<CompareResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    compareProjects(a, b)
      .then(setResult)
      .catch(() => setError("Failed to compare projects."));
  }, [a, b]);

  if (error) return <ErrorScreen message={error} />;
  if (!result) return <Spinner />;

  const { project_a, project_b } = result;

  return (
    <div className="p-4 pb-10">
      <h1 className="mb-4 text-center text-lg font-bold text-gray-900">
        Compare
      </h1>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col items-center rounded-xl border bg-white p-3 shadow-sm">
          <p className="truncate text-xs font-semibold text-gray-700">
            {project_a.project_name}
          </p>
          <ScoreGauge score={project_a.overall_score} size={80} />
          <span className="mt-1 text-xs text-gray-500">
            {project_a.recommendation}
          </span>
        </div>
        <div className="flex flex-col items-center rounded-xl border bg-white p-3 shadow-sm">
          <p className="truncate text-xs font-semibold text-gray-700">
            {project_b.project_name}
          </p>
          <ScoreGauge score={project_b.overall_score} size={80} />
          <span className="mt-1 text-xs text-gray-500">
            {project_b.recommendation}
          </span>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {(["tokenomics_score", "investors_score", "team_score", "social_score"] as const).map(
          (key) => (
            <div key={key}>
              <p className="mb-1 text-xs font-medium capitalize text-gray-400">
                {key.replace("_score", "")}
              </p>
              <div className="flex items-center gap-2">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-indigo-500"
                    style={{
                      width: `${project_a.scorecard[key]}%`,
                    }}
                  />
                </div>
                <span className="w-8 text-right text-xs font-semibold text-gray-700">
                  {project_a.scorecard[key]}
                </span>
                <span className="text-xs text-gray-300">vs</span>
                <span className="w-8 text-left text-xs font-semibold text-gray-700">
                  {project_b.scorecard[key]}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="ml-auto h-full rounded-full bg-purple-500"
                    style={{
                      width: `${project_b.scorecard[key]}%`,
                    }}
                  />
                </div>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}

// ─── Router ──────────────────────────────────────────────────────────────────

function Router() {
  useTelegram();

  const params = new URLSearchParams(window.location.search);

  const reportId = params.get("report_id");
  if (reportId) return <ReportView reportId={parseInt(reportId, 10)} />;

  const view = params.get("view");
  const userId = params.get("user_id");
  if (view === "portfolio" && userId)
    return <PortfolioView userId={parseInt(userId, 10)} />;

  const compare = params.get("compare");
  if (compare) {
    const [projA, projB] = compare.split(",");
    if (projA && projB) return <CompareView a={projA} b={projB} />;
  }

  return <ReportView reportId={0} />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <Router />
    </ErrorBoundary>
  );
}
