import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-sm border px-2 py-0.5 text-[11px] font-medium font-mono transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-slate-900 text-white",
        secondary:
          "border-border bg-card-subtle text-text-secondary",
        outline:
          "border-border text-text-primary",
        ac:
          "border-emerald-200 bg-emerald-50 text-emerald-700",
        wa:
          "border-red-200 bg-red-50 text-red-700",
        tle:
          "border-amber-200 bg-amber-50 text-amber-700",
        rte:
          "border-purple-200 bg-purple-50 text-purple-700",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
