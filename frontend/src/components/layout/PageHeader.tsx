import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  icon?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({
  title,
  subtitle,
  eyebrow,
  icon,
  actions,
}: PageHeaderProps): JSX.Element {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-edge/12 bg-slab/60 px-6 py-5 backdrop-blur">
      <div className="flex items-center gap-3.5">
        {icon && (
          <div className="grid h-10 w-10 place-items-center rounded-md bg-beacon/10 text-beacon ring-1 ring-inset ring-beacon/20">
            {icon}
          </div>
        )}
        <div>
          {eyebrow && <div className="eyebrow mb-1">// {eyebrow}</div>}
          <h1 className="text-lg font-semibold tracking-tight text-fg">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-fg-dim">{subtitle}</p>}
        </div>
      </div>
      {actions}
    </div>
  );
}
