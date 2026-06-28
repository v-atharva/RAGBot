import type { CorpusExplain, Health, ModelStatus, Mode, QueryResponse, Turn } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function postQuery(
  mode: Mode,
  question: string,
  history: Turn[] = [],
  signal?: AbortSignal,
  withTrace = false,
): Promise<QueryResponse> {
  const res = await fetch(`${BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, question, history, with_trace: withTrace }),
    signal,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function postQueryTraced(
  mode: Mode,
  question: string,
  history: Turn[] = [],
  signal?: AbortSignal,
): Promise<QueryResponse> {
  return postQuery(mode, question, history, signal, true);
}

export async function getCorpusExplain(): Promise<CorpusExplain> {
  const res = await fetch(`${BASE}/corpus/explain`);
  if (!res.ok) throw new Error("corpus explain failed");
  return res.json();
}

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error("health check failed");
  return res.json();
}

export async function getModelStatus(): Promise<ModelStatus> {
  const res = await fetch(`${BASE}/model/status`);
  if (!res.ok) throw new Error("model status failed");
  return res.json();
}

export async function loadModel(): Promise<ModelStatus> {
  const res = await fetch(`${BASE}/model/load`, { method: "POST" });
  if (!res.ok) throw new Error("model load failed");
  return res.json();
}

export async function unloadModel(): Promise<ModelStatus> {
  const res = await fetch(`${BASE}/model/unload`, { method: "POST" });
  if (!res.ok) throw new Error("model unload failed");
  return res.json();
}
