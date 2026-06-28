"use client";

import { Card, Skeleton } from "./ui";

/** Answer-shaped shimmer shown while a query is in flight (mirrors AnswerPanel's layout). */
export function AnswerSkeleton() {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border bg-surface-2/50 px-6 py-3">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-5 w-20" />
      </div>
      <div className="space-y-2.5 px-6 py-5">
        <Skeleton className="h-4 w-[92%]" />
        <Skeleton className="h-4 w-[97%]" />
        <Skeleton className="h-4 w-[78%]" />
        <Skeleton className="h-4 w-[40%]" />
        <div className="grid gap-3 pt-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      </div>
    </Card>
  );
}
