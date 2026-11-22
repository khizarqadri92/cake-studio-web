import { useState } from "react";
import { Link } from "react-router-dom";
import { PageBanner } from "@/components/PageBanner";
import { Button, buttonClass } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Empty, Spinner } from "@/components/states";
import { useCartActions, useCartCtx, useCartData } from "@/lib/cart";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";
import { useSeo } from "@/lib/theme";

export default function CartPage() {
  const { token } = useCartCtx();
  const { data: cart, isLoading } = useCartData();
  const cur = useSettings().data?.general.currency_code;
  const a = useCartActions();
  const [code, setCode] = useState("");
  useSeo("Your cart");

  if (!token) return <Wrap><Empty title="Your cart is empty" hint="Browse the shop to add something delicious." /><Shop /></Wrap>;
  if (isLoading) return <Spinner />;
  if (!cart || cart.items.length === 0) return <Wrap><Empty title="Your cart is empty" /><Shop /></Wrap>;

  const hasError = cart.items.some((i) => i.error);
  return (
    <Wrap>
      <div className="grid gap-8 md:grid-cols-[1fr_340px]">
        <ul className="space-y-4">
          {cart.items.map((i) => (
            <li key={i.id} className="flex gap-4 rounded-3xl bg-surface p-4 shadow-card">
              <div className="h-24 w-24 shrink-0 overflow-hidden rounded-2xl bg-secondary/30">{i.image && <img src={i.image} alt="" className="h-full w-full object-cover" />}</div>
              <div className="min-w-0 flex-1">
                <p className="font-heading text-lg">{i.slug ? <Link to={`/shop/${i.slug}`}>{i.name}</Link> : i.name}</p>
                {i.error ? <p role="alert" className="text-sm text-red-700">{i.error}</p> : (
                  <p className="text-sm text-ink/60">{[i.variant, ...(i.options ?? []), ...(i.addons ?? []).map((x) => `+ ${x}`)].filter(Boolean).join(" · ")}</p>
                )}
                {i.message && <p className="text-sm italic">“{i.message}”</p>}
                <div className="mt-2 flex items-center gap-3">
                  {!i.error && (
                    <label className="flex items-center gap-2 text-sm">
                      <span className="sr-only">Quantity</span>
                      <Input type="number" min={1} max={100} defaultValue={i.quantity} className="w-20 py-1.5"
                        onBlur={(e) => { const q = Math.max(1, Math.min(100, Number(e.target.value) || 1)); if (q !== i.quantity) a.setQty.mutate({ id: i.id, quantity: q }); }} />
                    </label>
                  )}
                  <button className="text-sm text-primary underline" onClick={() => a.remove.mutate(i.id)}>Remove</button>
                </div>
              </div>
              {i.line_total && <p className="font-medium text-primary">{money(i.line_total, cur)}</p>}
            </li>
          ))}
        </ul>

        <aside className="h-fit space-y-4 rounded-3xl bg-surface p-6 shadow-card md:sticky md:top-24">
          <h2 className="text-xl">Order summary</h2>
          <div>
            <p className="mb-2 font-medium">Coupon</p>
            {cart.coupon_code ? (
              <p className="flex items-center justify-between text-sm"><span>{cart.coupon_code} applied</span><button className="text-primary underline" onClick={() => a.removeCoupon.mutate()}>Remove</button></p>
            ) : (
              <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (code.trim()) a.applyCoupon.mutate(code.trim(), { onSuccess: () => setCode("") }); }}>
                <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Code" aria-label="Coupon code" className="uppercase" />
                <Button type="submit" variant="ghost" disabled={a.applyCoupon.isPending}>Apply</Button>
              </form>
            )}
            {a.applyCoupon.isError && <p role="alert" className="mt-1 text-xs text-red-700">{(a.applyCoupon.error as Error).message}</p>}
          </div>
          {cart.totals && (
            <dl className="space-y-2 border-t border-primary/10 pt-4 text-sm">
              <Row k="Subtotal" v={money(cart.totals.subtotal, cur)} />
              {Number(cart.totals.discount) > 0 && <Row k="Discount" v={`-${money(cart.totals.discount, cur)}`} />}
              <p className="pt-1 text-xs text-ink/50">Delivery and tax are calculated at checkout.</p>
            </dl>
          )}
          <Link to="/checkout" aria-disabled={hasError} className={buttonClass("primary", `w-full ${hasError ? "pointer-events-none opacity-50" : ""}`)}>Checkout</Link>
          {hasError && <p className="text-xs text-red-700">Remove unavailable items to continue.</p>}
        </aside>
      </div>
    </Wrap>
  );
}

const Row = ({ k, v }: { k: string; v: string }) => <div className="flex justify-between"><dt>{k}</dt><dd>{v}</dd></div>;
const Shop = () => <p className="mt-6 text-center"><Link to="/shop" className={buttonClass()}>Go to shop</Link></p>;
const Wrap = ({ children }: { children: React.ReactNode }) => (
  <div><PageBanner title="Your cart" /><div className="mx-auto max-w-5xl px-4 py-10">{children}</div></div>
);
