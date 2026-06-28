"use client";

import { useState } from "react";
import type { Mode } from "@/lib/types";
import { Tooltip } from "./Tooltip";

const STORAGE_KEY = "ragbot:notice-dismissed";

const NOTES: Record<Mode, { short: string; long: string }> = {
  lecture_only: {
    short: "Returns timestamps & lecture locations — when & where a topic was covered, not an explanation.",
    long: "Lecture-only mode is a locator: it points you to the exact recordings and timestamps where a topic comes up. For a full explanation, switch to Course-wide.",
  },
  course_wide: {
    short: "Explains the concept, then grounds it in cited course excerpts.",
    long: "Course-wide mode teaches the concept with an analogy and a worked example, citing the lectures and materials it draws on.",
  },
};

function InfoIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="size-3.5 shrink-0" aria-hidden>
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zM9 9a1 1 0 012 0v4a1 1 0 11-2 0V9zm1-4.25a1.1 1.1 0 100 2.2 1.1 1.1 0 000-2.2z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function UseCaseNotice({ mode }: { mode: Mode }) {
  // Lazy init from localStorage so a previously-dismissed notice doesn't flash in.
  const [dismissed, setDismissed] = useState<Record<string, boolean>>(() => {
    if (typeof window === "undefined") return {};
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch {
      return {};
    }
  });

  if (dismissed[mode]) return null;

  function dismiss() {
    setDismissed((prev) => {
      const next = { ...prev, [mode]: true };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {}
      return next;
    });
  }

  const note = NOTES[mode];
  return (
    <div
      suppressHydrationWarning
      className="mt-3 flex items-start gap-2 rounded-lg border border-border bg-surface-2/60 px-3 py-2 text-xs text-muted"
    >
      <Tooltip content={note.long}>
        <span className="mt-0.5 cursor-help text-accent" tabIndex={0} aria-label="About this mode">
          <InfoIcon />
        </span>
      </Tooltip>
      <p className="flex-1 leading-5">{note.short}</p>
      <button
        onClick={dismiss}
        aria-label="Dismiss"
        className="rounded p-0.5 text-muted transition-colors hover:text-foreground"
      >
        <svg viewBox="0 0 20 20" fill="currentColor" className="size-3.5" aria-hidden>
          <path d="M6.3 5l3.7 3.7L13.7 5 15 6.3 11.3 10 15 13.7 13.7 15 10 11.3 6.3 15 5 13.7 8.7 10 5 6.3z" />
        </svg>
      </button>
    </div>
  );
}
