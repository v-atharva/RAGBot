"use client";

import { useId, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Minimal dependency-free tooltip. Shows on hover and keyboard focus, exposes the bubble via
 * `aria-describedby`/`role="tooltip"`. Fixed top/bottom placement (good enough for short hints).
 */
export function Tooltip({
  content,
  children,
  side = "top",
  className,
}: {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span aria-describedby={open ? id : undefined}>{children}</span>
      {open && (
        <span
          role="tooltip"
          id={id}
          className={cn(
            "glow-pill pointer-events-none absolute left-1/2 z-50 w-max max-w-[16rem] -translate-x-1/2",
            "rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-normal text-foreground",
            side === "top" ? "bottom-full mb-2" : "top-full mt-2",
            className,
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
