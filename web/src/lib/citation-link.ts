// Canonical citation href builder — shared by the answer chips (Idea 7) and the Inspector
// (Phase 2). Href ONLY: chip label text lives on CitationMarker (inline_display), not here.
// The shape works for both CitationMarker and CitationRef (both carry these fields).

import type { CitationKind } from "./types";

const RECORDINGS_BASE = process.env.NEXT_PUBLIC_RECORDINGS_BASE ?? "";

export interface CitationHrefInput {
  kind?: CitationKind | string | null;
  lecture_prefix?: string | null;
  timestamp?: string | null;
  link_target?: string | null;
}

/** Build the href a citation chip links to, or `undefined` when nothing is linkable. */
export function citationHref(c: CitationHrefInput): string | undefined {
  if (c.kind === "lecture" && c.lecture_prefix) {
    const base = `${RECORDINGS_BASE}/lectures/${c.lecture_prefix}`;
    return c.timestamp ? `${base}?t=${c.timestamp}` : base;
  }
  if (c.link_target) {
    return `${RECORDINGS_BASE}/materials/${encodeURIComponent(c.link_target)}`;
  }
  return undefined;
}
