import type { ReactNode } from "react";

/** Soft tinted header band used at the top of storefront pages. */
export function PageBanner({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <section className="bg-secondary/40">
      <div className="mx-auto max-w-6xl px-4 py-10 text-center md:py-14">
        {eyebrow && <p className="text-sm font-medium uppercase tracking-widest text-primary">{eyebrow}</p>}
        <h1 className="mt-1 text-4xl md:text-5xl">{title}</h1>
        {children && <div className="mx-auto mt-3 max-w-xl text-ink/70">{children}</div>}
      </div>
    </section>
  );
}
