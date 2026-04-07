import type { Report, PortfolioItem, CompareResult } from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const tg = window.Telegram?.WebApp;
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": tg?.initData ?? "",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<T>;
}

export const getReport = (id: number) =>
  apiFetch<Report>(`/api/report/${id}`);

export const getPortfolio = (userId: number) =>
  apiFetch<PortfolioItem[]>(`/api/portfolio/${userId}`);

export const compareProjects = (a: string, b: string) =>
  apiFetch<CompareResult>("/api/compare", {
    method: "POST",
    body: JSON.stringify({ project_a: a, project_b: b }),
  });
