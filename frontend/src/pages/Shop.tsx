import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageBanner } from "@/components/PageBanner";
import { ProductCard } from "@/components/ProductCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Empty, ErrorBox, Spinner } from "@/components/states";
import { useCategories, useProducts } from "@/lib/queries";
import { useSeo } from "@/lib/theme";

const SORTS = [["latest", "Latest"], ["popular", "Most popular"], ["price_asc", "Price: low to high"], ["price_desc", "Price: high to low"]] as const;

export default function Shop() {
  const [sp, setSp] = useSearchParams();
  const { data: cats } = useCategories();
  const qs = new URLSearchParams();
  for (const k of ["q", "category", "min_price", "max_price", "sort", "page"]) { const v = sp.get(k); if (v) qs.set(k, v); }
  const { data, isLoading, isError, isFetching } = useProducts(qs.toString());
  const [q, setQ] = useState(sp.get("q") ?? "");
  useSeo("Shop", "Browse our cakes, pastries and more.");
  useEffect(() => setQ(sp.get("q") ?? ""), [sp]);

  const set = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    v ? n.set(k, v) : n.delete(k);
    if (k !== "page") n.delete("page");
    setSp(n);
  };
  const page = Number(sp.get("page") || 1);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  const pill = (on: boolean) => `rounded-full border px-4 py-1.5 text-sm transition ${on ? "border-primary bg-primary text-white" : "border-primary/20 bg-surface hover:border-primary/50"}`;
  const hasFilters = ["q", "category", "min_price", "max_price"].some((k) => sp.get(k));
  return (
    <div>
      <PageBanner eyebrow="Our bakery" title="Shop">Freshly baked cakes, cupcakes and pastries - made to order.</PageBanner>
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Categories">
            <button className={pill(!sp.get("category"))} onClick={() => set("category", "")}>All</button>
            {(cats ?? []).map((c) => <button key={c.id} className={pill(sp.get("category") === c.slug)} onClick={() => set("category", c.slug)}>{c.name}</button>)}
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="sort" className="text-sm text-ink/60">Sort by</label>
            <select id="sort" value={sp.get("sort") ?? "latest"} onChange={(e) => set("sort", e.target.value)} className="rounded-full border border-primary/20 bg-surface px-4 py-2 text-sm focus:border-primary focus:outline-none">
              {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-[250px_1fr]">
          <aside className="h-fit space-y-6 rounded-3xl bg-surface p-5 shadow-card">
            <form onSubmit={(e) => { e.preventDefault(); set("q", q.trim()); }} role="search">
              <p className="mb-2 font-medium">Search</p>
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search cakes…" aria-label="Search products" />
            </form>
            <div>
              <p className="mb-2 font-medium">Price</p>
              <div className="flex gap-2">
                <Input type="number" min={0} placeholder="Min" aria-label="Minimum price" defaultValue={sp.get("min_price") ?? ""} key={`min${sp.get("min_price")}`} onBlur={(e) => set("min_price", e.target.value)} />
                <Input type="number" min={0} placeholder="Max" aria-label="Maximum price" defaultValue={sp.get("max_price") ?? ""} key={`max${sp.get("max_price")}`} onBlur={(e) => set("max_price", e.target.value)} />
              </div>
            </div>
            {hasFilters && <button className="w-full rounded-full border border-primary/30 py-2 text-sm text-primary transition hover:bg-primary/5" onClick={() => { setQ(""); setSp(new URLSearchParams()); }}>Clear filters</button>}
          </aside>

          <div className={isFetching && !isLoading ? "opacity-60 transition" : "transition"}>
            {isLoading ? <Spinner /> : isError ? <ErrorBox /> : !data?.items.length ? (
              <Empty title="No products found" hint="Try a different search or clear your filters." />
            ) : (
              <>
                <p className="mb-4 text-sm text-ink/60">{data.total} product{data.total === 1 ? "" : "s"}</p>
                <div className="grid grid-cols-2 gap-4 md:gap-6 xl:grid-cols-3">{data.items.map((p) => <ProductCard key={p.id} p={p} />)}</div>
                {pages > 1 && (
                  <nav className="mt-10 flex items-center justify-center gap-4" aria-label="Pagination">
                    <Button variant="ghost" disabled={page <= 1} onClick={() => set("page", String(page - 1))}>Previous</Button>
                    <span className="text-sm">Page {page} of {pages}</span>
                    <Button variant="ghost" disabled={page >= pages} onClick={() => set("page", String(page + 1))}>Next</Button>
                  </nav>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
