"use client";

import React from "react";
import { cn } from "@/lib/cn";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-surface",
        "shadow-[var(--shadow)]",
        className,
      )}
      {...props}
    />
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "outline";
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl text-sm font-semibold " +
    "transition-colors focus-visible:outline-none focus-visible:ring-2 " +
    "focus-visible:ring-[var(--ring)] disabled:opacity-50 disabled:pointer-events-none";
  const variants = {
    primary: "bg-accent text-accent-fg hover:opacity-90 active:opacity-100 px-4 py-2.5",
    outline: "border border-border bg-surface hover:bg-surface-2 px-4 py-2.5",
    ghost: "hover:bg-surface-2 px-3 py-2",
  } as const;
  return <button className={cn(base, variants[variant], className)} {...props} />;
}

export function Badge({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border",
        "bg-surface-2 px-2.5 py-0.5 text-xs font-medium text-muted",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
      aria-hidden
    />
  );
}
