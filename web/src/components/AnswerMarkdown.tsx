"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { CitationMarker } from "@/lib/types";
import { citationHref } from "@/lib/citation-link";

/**
 * Renders the model's markdown answer (bold/italic/lists/SQL code blocks) and swaps inline
 * citation tokens for chips:
 *  - `[S#]` markers resolve (via `markerMap`) to clickable lecture/material chips.
 *  - bare `Lecture N @ HH:MM:SS` / `Lecture N` / `HH:MM:SS` become text-only chips
 *    (lecture-only mode has no marker_map, so these stay non-clickable by design).
 * Tokens inside `code`/`pre` are left untouched, so SQL timestamps aren't chipped.
 */

// --- minimal hast shapes (avoid an extra @types/hast dependency) ---
interface HText {
  type: "text";
  value: string;
}
interface HElement {
  type: "element";
  tagName: string;
  properties?: Record<string, unknown>;
  children: HNode[];
}
type HNode = HText | HElement | { type: string; value?: string; children?: HNode[] };

const TOKEN_RE = new RegExp(
  "(\\[\\s*S\\d+(?:\\s*[,;]?\\s*S\\d+)*\\s*\\])" + // 1: [S#] (or [S1, S3]) marker group
    "|(\\[?\\s*Lecture\\s+\\d+\\s*@\\s*\\d{2}:\\d{2}:\\d{2}\\s*\\]?)" + // 2: Lecture N @ ts
    "|(\\bLecture\\s+\\d+\\b)" + // 3: bare Lecture N
    "|(\\b\\d{2}:\\d{2}:\\d{2}\\b)", // 4: bare timestamp
  "g",
);

function text(value: string): HText {
  return { type: "text", value };
}

function chip(tag: "span" | "a", cls: string, label: string, href?: string): HElement {
  const properties: Record<string, unknown> = { className: ["chip", cls] };
  if (tag === "a" && href) {
    properties.href = href;
    properties.target = "_blank";
    properties.rel = ["noopener", "noreferrer"];
  }
  return { type: "element", tagName: tag, properties, children: [text(label)] };
}

function lectureTimestamp(seg: string): HNode[] {
  const m = seg.match(/Lecture\s+(\d+)\s*@\s*(\d{2}:\d{2}:\d{2})/);
  if (!m) return [text(seg)];
  const out: HNode[] = [];
  if (seg.trimStart().startsWith("[")) out.push(text("["));
  out.push(chip("span", "chip-lecture", `Lecture ${m[1]}`));
  out.push(text(" @ "));
  out.push(chip("span", "chip-timestamp", m[2]));
  if (seg.trimEnd().endsWith("]")) out.push(text("]"));
  return out;
}

function splitText(value: string, byMarker: Map<string, CitationMarker>): HNode[] {
  const out: HNode[] = [];
  let last = 0;
  for (const match of value.matchAll(TOKEN_RE)) {
    const idx = match.index ?? 0;
    if (idx > last) out.push(text(value.slice(last, idx)));
    last = idx + match[0].length;
    if (match[1]) {
      // [S#] group — one chip per resolvable id; hallucinated ids are dropped.
      for (const id of match[1].match(/S\d+/g) ?? []) {
        const m = byMarker.get(id);
        if (!m) continue;
        const cls = m.kind === "material" ? "chip-source" : "chip-citation";
        const href = citationHref(m);
        out.push(href ? chip("a", cls, m.inline_display, href) : chip("span", cls, m.inline_display));
      }
    } else if (match[2]) {
      out.push(...lectureTimestamp(match[2]));
    } else if (match[3]) {
      out.push(chip("span", "chip-lecture", match[3]));
    } else if (match[4]) {
      out.push(chip("span", "chip-timestamp", match[4]));
    }
  }
  if (last < value.length) out.push(text(value.slice(last)));
  return out;
}

function rehypeCitations(options?: { markerMap?: CitationMarker[] }) {
  const byMarker = new Map((options?.markerMap ?? []).map((m) => [m.marker, m]));
  const visit = (node: HNode, insideCode: boolean): void => {
    const children = (node as { children?: HNode[] }).children;
    if (!Array.isArray(children)) return;
    const out: HNode[] = [];
    for (const child of children) {
      if (child.type === "text" && !insideCode) {
        out.push(...splitText((child as HText).value, byMarker));
      } else {
        const tag = child.type === "element" ? (child as HElement).tagName : "";
        visit(child, insideCode || tag === "code" || tag === "pre");
        out.push(child);
      }
    }
    (node as { children?: HNode[] }).children = out;
  };
  return (tree: HNode) => visit(tree, false);
}

export function AnswerMarkdown({
  markdown,
  markerMap,
}: {
  markdown: string;
  markerMap: CitationMarker[];
}) {
  return (
    <div className="answer-markdown text-[15px] leading-7 text-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight, [rehypeCitations, { markerMap }]]}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
