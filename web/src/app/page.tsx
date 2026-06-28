"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Health, Mode, ModelStatus, PipelineTrace, QueryResponse, Turn } from "@/lib/types";
import { getHealth, getModelStatus, loadModel, postQuery, postQueryTraced, unloadModel } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Button, Card, Spinner } from "@/components/ui";
import { AnswerPanel } from "@/components/AnswerPanel";
import { AnswerSkeleton } from "@/components/AnswerSkeleton";
import { StagedProgress } from "@/components/StagedProgress";
import { UseCaseNotice } from "@/components/UseCaseNotice";
import { Tooltip } from "@/components/Tooltip";
import { InspectorModal } from "@/components/inspector/InspectorModal";

interface Exchange {
  question: string;
  data: QueryResponse;
}

/** Plain-text answer for conversation history: strip markdown + remove [S#] markers. */
function answerText(data: QueryResponse): string {
  if (data.no_concept_match) return data.intro_text;
  const stripped = data.answer_markdown
    .replace(/\[\s*S\d+(?:\s*[,;]?\s*S\d+)*\s*\]/g, "") // drop [S#] markers
    .replace(/[*_`#>]/g, "") // drop common markdown punctuation
    .replace(/\n{2,}/g, "\n")
    .trim();
  return [data.intro_text, stripped].filter(Boolean).join("\n").trim();
}

function formatBytes(n: number): string {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
}

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
  // Lazy init from the DOM (themeInit script sets the class pre-paint) — no setState-in-effect.
  const [dark, setDark] = useState(
    () => typeof document !== "undefined" && document.documentElement.classList.contains("dark"),
  );
  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
  }
  return (
    <Button
      variant="outline"
      onClick={toggle}
      className="px-3 py-2"
      aria-label="Toggle theme"
      suppressHydrationWarning
    >
      {dark ? "☾" : "☀"}
    </Button>
  );
}

function StatusPill({
  health,
  modelStatus,
  busy,
  disabled,
  onToggle,
}: {
  health: Health | null;
  modelStatus: ModelStatus | null;
  busy: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  if (!health) return null;

  // Non-Ollama providers can't be unloaded — show the static pill.
  if (health.provider !== "ollama") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-muted">
        <span className={cn("size-2 rounded-full", health.index_ready ? "bg-emerald-500" : "bg-amber-500")} />
        {health.model}
      </span>
    );
  }

  const loaded = modelStatus?.loaded ?? false;
  const dot = busy ? "bg-[var(--timestamp)]" : loaded ? "bg-emerald-500" : "bg-slate-400";
  const freed = modelStatus?.freed_bytes;
  const title = busy
    ? "Working…"
    : loaded
      ? "Model loaded — click to unload and free RAM"
      : "Model unloaded — click to load";

  const pill = (
    <button
      onClick={onToggle}
      disabled={disabled || busy}
      aria-label={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-muted",
        "transition-colors hover:text-foreground disabled:opacity-60",
        busy ? "glow-pulse" : loaded && "glow-pill",
      )}
    >
      <span className={cn("size-2 rounded-full", dot)} />
      {health.model}
    </button>
  );

  // After an unload, surface the freed RAM as a tooltip hint.
  return !loaded && freed ? <Tooltip content={`Freed ~${formatBytes(freed)}`}>{pill}</Tooltip> : pill;
}

export default function Home() {
  const [mode, setMode] = useState<Mode>("lecture_only");
  const [firstWord, setFirstWord] = useState<"When" | "Where">("When");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [thread, setThread] = useState<Exchange[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [pillBusy, setPillBusy] = useState(false);
  const [inspecting, setInspecting] = useState<PipelineTrace | null>(null);
  const [inspectIdx, setInspectIdx] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (health?.provider === "ollama") getModelStatus().then(setModelStatus).catch(() => {});
  }, [health?.provider]);

  // lecture_only enforces a "When/Where" first word; the textarea holds only the remainder.
  function composeQuestion(): string {
    const q = question.trim();
    if (!q) return "";
    return mode === "lecture_only" ? `${firstWord} ${q}` : q;
  }

  function switchMode(next: Mode) {
    if (next === mode) return;
    setMode(next);
    setQuestion(""); // a stale remainder reads oddly under the other mode
  }

  async function ask(q: string) {
    const text = q.trim();
    if (!text || loading) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setError(null);
    const history: Turn[] = thread.map((x) => ({ question: x.question, answer: answerText(x.data) }));
    try {
      const data = await postQuery(mode, text, history, ctrl.signal);
      setThread((prev) => [...prev, { question: text, data }]);
      setQuestion("");
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function runExample(ex: string) {
    if (mode === "lecture_only") {
      const m = ex.match(/^(When|Where)\s+(.*)$/i);
      if (m) {
        setFirstWord((m[1][0].toUpperCase() + m[1].slice(1).toLowerCase()) as "When" | "Where");
        setQuestion(m[2]);
      }
    } else {
      setQuestion(ex);
    }
    ask(ex);
  }

  function newConversation() {
    abortRef.current?.abort();
    setThread([]);
    setError(null);
    setQuestion("");
  }

  async function inspect(i: number) {
    const ex = thread[i];
    if (ex.data.trace) {
      setInspecting(ex.data.trace);
      return;
    }
    setInspectIdx(i);
    try {
      const history: Turn[] = thread
        .slice(0, i)
        .map((x) => ({ question: x.question, answer: answerText(x.data) }));
      const data = await postQueryTraced(ex.data.mode, ex.question, history);
      if (data.trace) setInspecting(data.trace);
    } catch {
      /* ignore */
    } finally {
      setInspectIdx(null);
    }
  }

  async function toggleModel() {
    if (pillBusy || loading) return;
    setPillBusy(true);
    try {
      const next = modelStatus?.loaded ? await unloadModel() : await loadModel();
      setModelStatus(next);
    } catch {
      /* leave prior status */
    } finally {
      setPillBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col px-5 py-8 sm:py-12">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
            RAGBot <span className="font-medium text-muted">· Course Tutor</span>
          </h1>
          <p className="mt-1 text-sm text-muted">
            Grounded answers from a real database course — cited to the lecture and timestamp.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill
            health={health}
            modelStatus={modelStatus}
            busy={pillBusy}
            disabled={loading}
            onToggle={toggleModel}
          />
          <Link
            href="/inspector"
            className="rounded-xl border border-border bg-surface px-3 py-2 text-sm font-semibold text-muted transition-colors hover:text-accent"
          >
            Inspector
          </Link>
          <ThemeToggle />
        </div>
      </header>

      <Card className="p-4 sm:p-5">
        {/* Mode toggle */}
        <div className="grid grid-cols-2 gap-1.5 rounded-xl bg-surface-2 p-1.5">
          {MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => switchMode(m.id)}
              className={cn(
                "rounded-lg px-3 py-2 text-left transition-colors",
                mode === m.id ? "bg-surface shadow-[var(--shadow)] glow-pill" : "hover:bg-surface/50",
              )}
            >
              <div className={cn("text-sm font-semibold", mode === m.id ? "text-accent" : "text-foreground")}>
                {m.label}
              </div>
              <div className="text-xs text-muted">{m.hint}</div>
            </button>
          ))}
        </div>

        <UseCaseNotice mode={mode} />

        {/* Composer */}
        <div className="mt-3">
          <div className="rounded-xl border border-border bg-surface transition-shadow focus-within:ring-2 focus-within:ring-[var(--ring)]">
            {mode === "lecture_only" && (
              <div className="flex items-center gap-2 px-3.5 pt-2.5">
                <span className="text-xs text-muted">Start with</span>
                <div className="inline-flex rounded-lg bg-surface-2 p-0.5">
                  {(["When", "Where"] as const).map((w) => (
                    <button
                      key={w}
                      onClick={() => setFirstWord(w)}
                      className={cn(
                        "rounded-md px-2.5 py-0.5 text-xs font-semibold transition-colors",
                        firstWord === w ? "bg-surface text-accent glow-pill" : "text-muted hover:text-foreground",
                      )}
                    >
                      {w}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(composeQuestion());
              }}
              placeholder={
                mode === "lecture_only"
                  ? "…did the professor cover BCNF?"
                  : "Ask about a topic…  e.g. Explain BCNF"
              }
              rows={3}
              className="w-full resize-none bg-transparent px-3.5 py-3 text-[15px] outline-none"
            />
          </div>
          <div className="mt-3 flex items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES[mode].map((ex) => (
                <button
                  key={ex}
                  onClick={() => runExample(ex)}
                  className="rounded-full border border-border bg-surface-2 px-2.5 py-1 text-xs text-muted transition-colors hover:text-foreground"
                >
                  {ex}
                </button>
              ))}
            </div>
            <Button onClick={() => ask(composeQuestion())} disabled={loading || !question.trim()}>
              {loading ? <Spinner /> : "Ask"}
              {loading && <span className="hidden sm:inline">Thinking…</span>}
            </Button>
          </div>
        </div>
      </Card>

      <div className="mt-6 space-y-6">
        {thread.length > 0 && (
          <div className="flex justify-end">
            <Button variant="outline" onClick={newConversation} className="px-3 py-1.5 text-sm">
              New conversation
            </Button>
          </div>
        )}

        {thread.map((x, i) => (
          <div key={i} className="space-y-2">
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl bg-surface-2 px-4 py-2 text-[15px] text-foreground">
                {x.question}
              </div>
            </div>
            <AnswerPanel data={x.data} onInspect={() => inspect(i)} inspectBusy={inspectIdx === i} />
          </div>
        ))}

        {error && (
          <Card className="border-red-300 p-4 text-sm text-red-600 dark:border-red-900 dark:text-red-400">
            {error}
          </Card>
        )}
        {loading && (
          <div className="space-y-3" aria-live="polite">
            <StagedProgress />
            <AnswerSkeleton />
          </div>
        )}
        {thread.length === 0 && !loading && !error && (
          <div className="px-2 py-10 text-center text-sm text-muted">
            Pick a mode and ask a question to see grounded, cited answers.
          </div>
        )}
      </div>

      <footer className="mt-auto pt-10 text-center text-xs text-muted">
        Local demo · {health?.provider ?? "ollama"} · {health?.concepts ?? "—"} indexed concepts
      </footer>

      {inspecting && <InspectorModal trace={inspecting} onClose={() => setInspecting(null)} />}
    </div>
  );
}
