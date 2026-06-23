"use client";

import { useEffect, useRef, useState } from "react";
import type { Health, Mode, QueryResponse } from "@/lib/types";
import { getHealth, postQuery } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Button, Card, Spinner } from "@/components/ui";
import { AnswerPanel } from "@/components/AnswerPanel";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "lecture_only", label: "Lecture-only", hint: "When & where a topic was covered" },
  { id: "course_wide", label: "Course-wide", hint: "Explained, then grounded in the course" },
];

const EXAMPLES: Record<Mode, string[]> = {
  lecture_only: [
    "When did the professor discuss BCNF?",
    "Where are joins covered?",
    "When was 3rd normal form taught?",
  ],
  course_wide: ["Explain BCNF", "What is a foreign key?", "Explain normalization"],
};

function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);
  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
  }
  return (
    <Button variant="outline" onClick={toggle} className="px-3 py-2" aria-label="Toggle theme">
      {dark ? "☾" : "☀"}
    </Button>
  );
}

function StatusPill({ health }: { health: Health | null }) {
  if (!health) return null;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-muted">
      <span
        className={cn(
          "size-2 rounded-full",
          health.index_ready ? "bg-emerald-500" : "bg-amber-500",
        )}
      />
      {health.model}
    </span>
  );
}

export default function Home() {
  const [mode, setMode] = useState<Mode>("lecture_only");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  async function ask(q: string) {
    const text = q.trim();
    if (!text || loading) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setError(null);
    try {
      const data = await postQuery(mode, text, ctrl.signal);
      setResult(data);
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col px-5 py-8 sm:py-12">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            RAGBot <span className="font-medium text-muted">· Course Tutor</span>
          </h1>
          <p className="mt-1 text-sm text-muted">
            Grounded answers from a real database course — cited to the lecture and timestamp.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill health={health} />
          <ThemeToggle />
        </div>
      </header>

      <Card className="p-4 sm:p-5">
        {/* Mode toggle */}
        <div className="grid grid-cols-2 gap-1.5 rounded-xl bg-surface-2 p-1.5">
          {MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={cn(
                "rounded-lg px-3 py-2 text-left transition-colors",
                mode === m.id ? "bg-surface shadow-[var(--shadow)]" : "hover:bg-surface/50",
              )}
            >
              <div
                className={cn(
                  "text-sm font-semibold",
                  mode === m.id ? "text-accent" : "text-foreground",
                )}
              >
                {m.label}
              </div>
              <div className="text-xs text-muted">{m.hint}</div>
            </button>
          ))}
        </div>

        {/* Composer */}
        <div className="mt-3">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(question);
            }}
            placeholder={
              mode === "lecture_only"
                ? "Ask when a topic was discussed…  e.g. When did the professor cover BCNF?"
                : "Ask about a topic…  e.g. Explain BCNF"
            }
            rows={3}
            className="w-full resize-none rounded-xl border border-border bg-surface px-3.5 py-3 text-[15px] outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          />
          <div className="mt-3 flex items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES[mode].map((ex) => (
                <button
                  key={ex}
                  onClick={() => {
                    setQuestion(ex);
                    ask(ex);
                  }}
                  className="rounded-full border border-border bg-surface-2 px-2.5 py-1 text-xs text-muted transition-colors hover:text-foreground"
                >
                  {ex}
                </button>
              ))}
            </div>
            <Button onClick={() => ask(question)} disabled={loading || !question.trim()}>
              {loading ? <Spinner /> : "Ask"}
              {loading && <span className="hidden sm:inline">Thinking…</span>}
            </Button>
          </div>
        </div>
      </Card>

      <div className="mt-6">
        {error && (
          <Card className="border-red-300 p-4 text-sm text-red-600 dark:border-red-900 dark:text-red-400">
            {error}
          </Card>
        )}
        {!error && loading && !result && (
          <div className="flex items-center gap-2 px-2 text-sm text-muted">
            <Spinner /> Retrieving and grounding…
          </div>
        )}
        {result && !loading && <AnswerPanel data={result} />}
        {!result && !loading && !error && (
          <div className="px-2 py-10 text-center text-sm text-muted">
            Pick a mode and ask a question to see grounded, cited answers.
          </div>
        )}
      </div>

      <footer className="mt-auto pt-10 text-center text-xs text-muted">
        Local demo · {health?.provider ?? "ollama"} · {health?.concepts ?? "—"} indexed concepts
      </footer>
    </div>
  );
}
