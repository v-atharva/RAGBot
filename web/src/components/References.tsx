"use client";

import type { LectureReference } from "@/lib/types";
import { cn } from "@/lib/cn";

function StarIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden>
      <path d="M10 1.5l2.6 5.3 5.9.86-4.25 4.14 1 5.86L10 15.9l-5.25 2.76 1-5.86L1.5 7.66l5.9-.86L10 1.5z" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className} aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ReferenceCard({ ref_ }: { ref_: LectureReference }) {
  return (
    <div className="rounded-xl border border-border bg-surface-2/60 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="chip chip-lecture text-sm">{ref_.lecture_label}</span>
        {ref_.is_first_mention && (
          <span
            className="inline-flex items-center gap-1 rounded-full bg-accent/12 px-2 py-0.5 text-xs font-semibold"
            style={{ color: "var(--accent)" }}
          >
            <StarIcon className="size-3" />
            First proper mention
          </span>
        )}
        <span className="text-sm font-medium text-muted">{ref_.lecture_title}</span>
      </div>

      {ref_.timestamps.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {ref_.timestamps.map((t) => (
            <li key={t.timestamp} className="flex items-start gap-2.5 text-sm">
              <span className="chip chip-timestamp mt-0.5 shrink-0">
                <ClockIcon className="size-3" />
                {t.timestamp}
              </span>
              <span className={cn("text-foreground/90", t.is_warning && "text-amber-600 dark:text-amber-400")}>
                {t.blurb || <span className="text-muted italic">mentioned here</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function References({
  references,
  caption,
}: {
  references: LectureReference[];
  caption: string;
}) {
  if (references.length === 0) return null;
  return (
    <section className="mt-6">
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Lecture references
        </h3>
        <span className="h-px flex-1 bg-border" />
      </div>
      {caption && <p className="mb-3 text-sm text-muted">{caption}</p>}
      <div className="grid gap-3">
        {references.map((r) => (
          <ReferenceCard key={r.lecture_prefix} ref_={r} />
        ))}
      </div>
    </section>
  );
}
