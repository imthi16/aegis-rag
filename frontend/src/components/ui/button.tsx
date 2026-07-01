import { type VariantProps, cva } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-100 disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        // Primary is a beveled physical key: bright top lip, solid base, and it
        // depresses on press (drops the cast shadow, sinks 1px).
        primary:
          "bg-beacon text-ink shadow-key hover:bg-beacon/90 active:translate-y-px active:shadow-key-press",
        subtle: "bg-raise text-fg shadow-e1 hover:bg-raise/70 ring-1 ring-inset ring-edge/12 active:translate-y-px",
        outline: "border border-edge/18 bg-transparent text-fg-dim hover:border-edge/30 hover:text-fg",
        ghost: "text-fg-dim hover:bg-raise hover:text-fg",
        danger: "bg-crimson/15 text-crimson ring-1 ring-inset ring-crimson/30 hover:bg-crimson/25",
      },
      size: {
        sm: "h-8 px-3",
        md: "h-10 px-4",
        lg: "h-11 px-5 text-[15px]",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps): JSX.Element {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
