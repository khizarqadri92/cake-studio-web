import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { useCartCtx } from "@/lib/cart";
import { ErrorBox, NotFound, Spinner } from "@/components/states";
import { ApiError, post } from "@/lib/api";
import { money } from "@/lib/format";
import { useProduct, useSettings } from "@/lib/queries";
import { useSeo } from "@/lib/theme";
import type { ProductDetail as PD, Quote } from "@/lib/types";
import { Reviews } from "@/components/Reviews";

export default function ProductDetail() {
  const { slug = "" } = useParams();
  const { data: p, isLoading, error } = useProduct(slug);
  useSeo(p?.meta_title ?? null, p?.meta_description ?? null);
  if (isLoading) return <Spinner />;
  if (error instanceof ApiError && error.status === 404) return <NotFound />;
  if (error || !p) return <div className="mx-auto max-w-xl px-4 py-16"><ErrorBox /></div>;
  return <Detail key={p.id} p={p} />;
}

function Detail({ p }: { p: PD }) {
  const cur = useSettings().data?.general.currency_code;
  const [img, setImg] = useState(0);
  const [variantId, setVariantId] = useState<number | null>(p.variants.find((v) => v.in_stock)?.id ?? p.variants[0]?.id ?? null);
  const [choices, setChoices] = useState<Record<number, number>>(() =>
    Object.fromEntries(p.option_groups.filter((g) => g.is_required && g.choices.length).map((g) => [g.id, g.choices[0].id])));
  const [addons, setAddons] = useState<number[]>([]);
  const [qty, setQty] = useState(1);
  const [message, setMessage] = useState("");
  const [instructions, setInstructions] = useState("");
  const [added, setAdded] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const cart = useCartCtx();

  useEffect(() => { if (img >= p.images.length) setImg(0); }, [img, p.images.length]);

  const ready = (p.product_type === "simple" || variantId !== null) &&
    p.option_groups.every((g) => !g.is_required || g.choices.length === 0 || choices[g.id] !== undefined);
  const body = { variant_id: variantId, choice_ids: Object.values(choices), addon_ids: addons, quantity: qty };
  const quote = useQuery({
    queryKey: ["quote", p.id, body],
    queryFn: () => post<Quote>(`/public/products/${p.id}/price`, body),
    enabled: ready && p.is_available,
    placeholderData: (prev) => prev,
    retry: false,
  });

  const toggleAddon = (id: number) => setAddons((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));
  const legend = "mb-2 font-medium";
  const addToCart = async () => {
    setAdding(true); setAddError(null); setAdded(false);
    try {
      await cart.add({ product_id: p.id, variant_id: variantId, choice_ids: Object.values(choices), addon_ids: addons, quantity: qty, message: message.trim() || null, instructions: instructions.trim() || null });
      setAdded(true);
    } catch (e) { setAddError(e instanceof Error ? e.message : "Couldn't add to cart"); }
    finally { setAdding(false); }
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <nav className="mb-6 text-sm text-ink/60" aria-label="Breadcrumb">
        <Link to="/shop" className="hover:text-primary">Shop</Link>
        {p.category && <> / <Link to={`/shop?category=${p.category.slug}`} className="hover:text-primary">{p.category.name}</Link></>}
      </nav>
      <div className="grid gap-10 md:grid-cols-2">
        <div>
          <div className="aspect-square overflow-hidden rounded-3xl bg-secondary/30 shadow-card">
            {p.images[img] ? <img src={p.images[img].url} alt={p.images[img].alt || p.name} className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center font-heading text-2xl text-primary/40">{p.name}</div>}
          </div>
          {p.images.length > 1 && (
            <div className="mt-3 flex gap-3 overflow-x-auto">
              {p.images.map((im, i) => (
                <button key={im.url} onClick={() => setImg(i)} aria-label={`Show image ${i + 1}`} aria-current={i === img} className={`h-16 w-16 shrink-0 overflow-hidden rounded-xl border-2 ${i === img ? "border-primary" : "border-transparent"}`}>
                  <img src={im.url} alt="" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div>
            <h1 className="text-4xl md:text-5xl">{p.name}</h1>
            <p className="mt-2 text-sm text-ink/60">Ready in about {p.prep_time_hours >= 24 && p.prep_time_hours % 24 === 0 ? `${p.prep_time_hours / 24} day${p.prep_time_hours === 24 ? "" : "s"}` : `${p.prep_time_hours} hours`}</p>
          </div>
          {p.description && <p className="whitespace-pre-line leading-relaxed text-ink/80">{p.description}</p>}

          {p.variants.length > 0 && (
            <fieldset>
              <legend className={legend}>Size / weight</legend>
              <div className="flex flex-wrap gap-2">
                {p.variants.map((v) => (
                  <label key={v.id} className={`cursor-pointer rounded-full border px-4 py-2 text-sm ${variantId === v.id ? "border-primary bg-primary text-white" : "border-primary/30"} ${!v.in_stock ? "cursor-not-allowed opacity-40" : ""}`}>
                    <input type="radio" name="variant" className="sr-only" disabled={!v.in_stock} checked={variantId === v.id} onChange={() => setVariantId(v.id)} />
                    {v.name} · {money(v.sale_price ?? v.price, cur)}
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          {p.option_groups.map((g) => (
            <fieldset key={g.id}>
              <legend className={legend}>{g.name}{g.is_required ? "" : " (optional)"}</legend>
              <div className="flex flex-wrap gap-2">
                {!g.is_required && (
                  <label className={`cursor-pointer rounded-full border px-4 py-2 text-sm ${choices[g.id] === undefined ? "border-primary bg-primary text-white" : "border-primary/30"}`}>
                    <input type="radio" className="sr-only" name={`g${g.id}`} checked={choices[g.id] === undefined} onChange={() => setChoices(({ [g.id]: _, ...rest }) => rest)} />None
                  </label>
                )}
                {g.choices.map((c) => (
                  <label key={c.id} className={`cursor-pointer rounded-full border px-4 py-2 text-sm ${choices[g.id] === c.id ? "border-primary bg-primary text-white" : "border-primary/30"}`}>
                    <input type="radio" className="sr-only" name={`g${g.id}`} checked={choices[g.id] === c.id} onChange={() => setChoices((s) => ({ ...s, [g.id]: c.id }))} />
                    {c.label}{Number(c.price_delta) !== 0 && ` (${Number(c.price_delta) > 0 ? "+" : ""}${money(c.price_delta, cur)})`}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}

          {p.addons.length > 0 && (
            <fieldset>
              <legend className={legend}>Add-ons</legend>
              <div className="space-y-2">
                {p.addons.map((a) => (
                  <label key={a.id} className="flex cursor-pointer items-center gap-3 text-sm">
                    <input type="checkbox" className="h-4 w-4 accent-primary" checked={addons.includes(a.id)} onChange={() => toggleAddon(a.id)} />
                    {a.name} <span className="text-ink/60">+{money(a.price, cur)}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          {p.allows_message && (
            <div>
              <label htmlFor="msg" className={`${legend} block`}>Message on cake (optional)</label>
              <Input id="msg" value={message} maxLength={p.message_max_length} onChange={(e) => setMessage(e.target.value)} placeholder="Happy Birthday!" />
              <p className="mt-1 text-xs text-ink/50">{message.length}/{p.message_max_length}</p>
            </div>
          )}

          <div className="flex items-center gap-3">
            <label htmlFor="qty" className="font-medium">Quantity</label>
            <Input id="qty" type="number" min={1} max={100} value={qty} className="w-24" onChange={(e) => setQty(Math.max(1, Math.min(100, Number(e.target.value) || 1)))} />
          </div>

          <div>
            <label htmlFor="instr" className={`${legend} block`}>Special instructions (optional)</label>
            <Textarea id="instr" rows={2} maxLength={500} value={instructions} onChange={(e) => setInstructions(e.target.value)} placeholder="Allergies, design notes…" />
          </div>

          <div className="rounded-3xl bg-surface p-5 shadow-card" aria-live="polite">
            {!p.is_available ? <p className="text-ink/70">This product is currently unavailable.</p>
              : quote.isError ? <p role="alert" className="text-sm text-red-700">{quote.error instanceof ApiError ? quote.error.message : "Couldn't calculate the price."}</p>
              : quote.data ? (
                <>
                  <p className="text-sm text-ink/60">{money(quote.data.unit_price, cur)} each</p>
                  <p className="font-heading text-3xl text-primary">{money(quote.data.line_total, cur)}</p>
                </>
              ) : <p className="text-sm text-ink/60">Select your options to see the price.</p>}
          </div>

          <Button className="w-full py-3.5 text-base" disabled={!p.is_available || !p.in_stock || !ready || adding} onClick={addToCart}>
            {!p.is_available || !p.in_stock ? "Sold out" : adding ? "Adding…" : "Add to cart"}
          </Button>
          {added && <p role="status" className="text-sm text-primary">Added to your cart. <Link to="/cart" className="underline">View cart</Link></p>}
          {addError && <p role="alert" className="text-sm text-red-700">{addError}</p>}
          <ul className="grid grid-cols-3 gap-2 border-t border-primary/10 pt-5 text-center text-xs text-ink/70">
            <li className="rounded-2xl bg-secondary/30 px-2 py-3">Baked fresh to order</li>
            <li className="rounded-2xl bg-secondary/30 px-2 py-3">Choose your delivery slot</li>
            <li className="rounded-2xl bg-secondary/30 px-2 py-3">Real butter &amp; cream</li>
          </ul>
        </div>
      </div>
      <Reviews slug={p.slug} productId={p.id} />
    </div>
  );
}
