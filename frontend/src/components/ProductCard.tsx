import { Link } from "react-router-dom";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";
import type { ProductCard as Card } from "@/lib/types";

export function ProductCard({ p }: { p: Card }) {
  const cur = useSettings().data?.general.currency_code;
  return (
    <Link to={`/shop/${p.slug}`} className="group fade-in flex flex-col overflow-hidden rounded-3xl bg-surface shadow-card transition duration-300 hover:-translate-y-1 hover:shadow-xl">
      <div className="relative aspect-square overflow-hidden bg-secondary/30">
        {p.image ? (
          <img src={p.image} alt={p.name} loading="lazy" className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />
        ) : (
          <div className="flex h-full items-center justify-center font-heading text-lg text-primary/50">{p.name}</div>
        )}
        {!p.in_stock && <div className="absolute inset-0 flex items-center justify-center bg-white/60 text-sm font-semibold uppercase tracking-wide text-ink/70">Sold out</div>}
        <div className="absolute left-3 top-3 flex gap-2 text-xs font-medium">
          {p.on_sale && <span className="rounded-full bg-primary px-3 py-1 text-white">Sale</span>}
          {p.is_bestseller && <span className="rounded-full bg-secondary px-3 py-1">Best seller</span>}
        </div>
      </div>
      <div className="flex flex-1 flex-col p-4">
        <h3 className="text-lg leading-snug">{p.name}</h3>
        <div className="mt-auto flex items-center justify-between pt-3">
          <span className="text-lg font-semibold text-primary">{p.has_options ? <span className="mr-1 text-xs font-normal text-ink/50">From</span> : null}{money(p.from_price, cur)}</span>
          <span className="rounded-full bg-secondary/50 px-3 py-1 text-xs font-medium text-primary transition group-hover:bg-primary group-hover:text-white">{p.has_options ? "Choose options" : "View"}</span>
        </div>
      </div>
    </Link>
  );
}
