import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { useAuth } from "@/lib/auth";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { PageBanner } from "@/components/PageBanner";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Empty, Spinner } from "@/components/states";
import { api } from "@/lib/api";
import { useCartCtx, useCartData } from "@/lib/cart";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";
import { useSeo } from "@/lib/theme";
import type { OrderPlaced, PayMethod, Slot } from "@/lib/types";
import { post } from "@/lib/api";

const schema = z.object({
  full_name: z.string().trim().min(1, "Please enter your name"),
  phone: z.string().trim().regex(/^\+?[\d\s\-().]{7,20}$/, "Enter a valid phone number"),
  email: z.string().email("Enter a valid email").or(z.literal("")),
  fulfillment: z.enum(["delivery", "pickup"]),
  line: z.string().trim().optional(),
  city: z.string().trim().optional(),
  postal_code: z.string().trim().optional(),
  instructions: z.string().max(500).optional(),
  day: z.string().min(1, "Choose a date"),
  slot_id: z.coerce.number({ invalid_type_error: "Choose a time slot" }).int().positive("Choose a time slot"),
  payment_method: z.string().min(1, "Choose a payment method"),
  notes: z.string().max(500).optional(),
}).superRefine((v, ctx) => {
  if (v.fulfillment === "delivery") {
    if (!v.line || v.line.length < 3) ctx.addIssue({ code: "custom", path: ["line"], message: "Enter your delivery address" });
    if (!v.city) ctx.addIssue({ code: "custom", path: ["city"], message: "Enter your city" });
  }
});
type Form = z.infer<typeof schema>;

export default function Checkout() {
  const nav = useNavigate();
  const { token, clear } = useCartCtx();
  const { me } = useAuth();
  const cur = useSettings().data?.general.currency_code;
  useSeo("Checkout");
  const [idem] = useState(() => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()));

  const { register, handleSubmit, watch, setValue, getValues, formState: { errors } } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { fulfillment: "delivery", full_name: "", phone: "", email: "", day: "", payment_method: "" },
  });
  // Prefill once from the signed-in customer's profile and default address (never overwrites what they typed).
  const prefilled = useRef(false);
  useEffect(() => {
    if (!me || prefilled.current) return;
    prefilled.current = true;
    const d = me.addresses.find((a) => a.is_default) ?? me.addresses[0];
    if (!getValues("full_name")) setValue("full_name", me.full_name);
    if (!getValues("phone") && me.phone) setValue("phone", me.phone);
    if (!getValues("email")) setValue("email", me.email);
    if (d && !getValues("line")) { setValue("line", d.line); setValue("city", d.city); if (d.postal_code) setValue("postal_code", d.postal_code); }
  }, [me]); // eslint-disable-line react-hooks/exhaustive-deps
  const fulfillment = watch("fulfillment");
  const day = watch("day");
  const { data: cart, isLoading } = useCartData(fulfillment);

  const slots = useQuery({
    queryKey: ["slots", day, token],
    enabled: !!day && !!token,
    queryFn: () => api<Slot[]>(`/public/delivery/slots?day=${day}&cart_token=${token}`),
  });
  const methods = useQuery({ queryKey: ["pm", fulfillment], queryFn: () => api<PayMethod[]>(`/public/payment-methods?fulfillment=${fulfillment}`) });
  const selectedPm = methods.data?.find((m) => m.code === watch("payment_method"));
  const minDay = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const place = useMutation({
    mutationFn: (v: Form) => post<OrderPlaced>("/checkout", {
      cart_token: token, full_name: v.full_name, phone: v.phone, email: v.email || null, fulfillment: v.fulfillment,
      address: v.fulfillment === "delivery" ? { line: v.line, city: v.city, postal_code: v.postal_code || null, instructions: v.instructions || null } : null,
      day: v.day, slot_id: v.slot_id, payment_method: v.payment_method, notes: v.notes ?? "",
    }, { "Idempotency-Key": idem }),
    onSuccess: (o) => { clear(); nav("/order-confirmation", { state: o, replace: true }); },
  });

  if (isLoading) return <Spinner />;
  if (!token || !cart || cart.items.length === 0) return <div className="mx-auto max-w-xl px-4 py-16"><Empty title="Your cart is empty" /></div>;
  if (cart.items.some((i) => i.error)) return <div className="mx-auto max-w-xl px-4 py-16"><Empty title="Please review your cart" hint="Some items are no longer available." /><p className="mt-4 text-center"><Link to="/cart" className="text-primary underline">Back to cart</Link></p></div>;

  const err = (k: keyof Form) => errors[k] && <p role="alert" className="mt-1 text-xs text-red-700">{errors[k]?.message as string}</p>;
  const t = cart.totals;
  const h = "mb-4 flex items-center gap-3 font-heading text-xl";
  const card = "rounded-3xl bg-surface p-5 shadow-card md:p-6";
  const num = (n: number) => <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-white">{n}</span>;

  return (
    <div>
      <PageBanner title="Checkout">Just a few details and your cake is on its way.</PageBanner>
      <div className="mx-auto max-w-5xl px-4 py-10">
      <form onSubmit={handleSubmit((v) => place.mutate(v))} noValidate className="grid gap-8 md:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <section className={card}>
            <h2 className={h}>{num(1)}Your details</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2"><Input placeholder="Full name" aria-label="Full name" autoComplete="name" {...register("full_name")} />{err("full_name")}</div>
              <div><Input placeholder="Phone" aria-label="Phone" autoComplete="tel" {...register("phone")} />{err("phone")}</div>
              <div><Input type="email" placeholder="Email (optional)" aria-label="Email" autoComplete="email" {...register("email")} />{err("email")}</div>
            </div>
          </section>

          <section className={card}>
            <h2 className={h}>{num(2)}Delivery or pickup</h2>
            <div className="mb-4 flex gap-3">
              {(["delivery", "pickup"] as const).map((f) => (
                <label key={f} className={`flex-1 cursor-pointer rounded-2xl border-2 px-5 py-3 text-center text-sm font-medium transition ${fulfillment === f ? "border-primary bg-primary/5 text-primary" : "border-primary/15 hover:border-primary/40"}`}>
                  <input type="radio" value={f} className="sr-only" {...register("fulfillment", { onChange: () => { setValue("payment_method", ""); } })} />
                  {f === "delivery" ? "Home delivery" : "Store pickup"}
                </label>
              ))}
            </div>
            {fulfillment === "delivery" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="sm:col-span-2"><Input placeholder="Delivery address" aria-label="Delivery address" autoComplete="street-address" {...register("line")} />{err("line")}</div>
                <div><Input placeholder="City" aria-label="City" autoComplete="address-level2" {...register("city")} />{err("city")}</div>
                <div><Input placeholder="Postal code" aria-label="Postal code" autoComplete="postal-code" {...register("postal_code")} /></div>
                <div className="sm:col-span-2"><Textarea rows={2} placeholder="Delivery instructions (optional)" aria-label="Delivery instructions" {...register("instructions")} /></div>
              </div>
            )}
          </section>

          <section className={card}>
            <h2 className={h}>{num(3)}When?</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Input type="date" min={minDay} aria-label="Date" {...register("day", { onChange: () => setValue("slot_id", "" as unknown as number) })} />
                {err("day")}
              </div>
              <div>
                <select aria-label="Time slot" disabled={!day || slots.isLoading} className="w-full rounded-xl border border-primary/20 bg-surface px-3 py-2.5 text-sm" {...register("slot_id")}>
                  <option value="">{!day ? "Pick a date first" : slots.isLoading ? "Loading…" : "Choose a time slot"}</option>
                  {(slots.data ?? []).map((s) => <option key={s.slot_id} value={s.slot_id}>{s.start}–{s.end} ({s.remaining} left)</option>)}
                </select>
                {err("slot_id")}
              </div>
            </div>
            {day && slots.data?.length === 0 && <p role="status" className="mt-2 text-sm text-ink/70">No slots are available on this date. Some cakes need extra preparation time, so try a later day.</p>}
          </section>

          <section className={card}>
            <h2 className={h}>{num(4)}Payment</h2>
            <div className="space-y-2">
              {(methods.data ?? []).map((m) => (
                <label key={m.code} className={`flex cursor-pointer items-center gap-3 rounded-2xl border-2 px-4 py-3 text-sm transition ${watch("payment_method") === m.code ? "border-primary bg-primary/5" : "border-primary/15 hover:border-primary/40"}`}>
                  <input type="radio" value={m.code} className="accent-primary" {...register("payment_method")} />{m.name}
                </label>
              ))}
              {methods.data?.length === 0 && <p className="text-sm text-red-700">No payment methods are available right now.</p>}
            </div>
            {selectedPm?.instructions && <p className="mt-3 whitespace-pre-line rounded-2xl bg-secondary/30 p-4 text-sm">{selectedPm.instructions}</p>}
            {err("payment_method")}
          </section>

          <section className={card}><Textarea rows={2} placeholder="Notes for the bakery (optional)" aria-label="Order notes" {...register("notes")} /></section>
        </div>

        <aside className="h-fit space-y-3 rounded-3xl bg-surface p-6 shadow-card md:sticky md:top-24">
          <h2 className="font-heading text-xl">Order summary</h2>
          <ul className="space-y-1 text-sm">{cart.items.map((i) => <li key={i.id} className="flex justify-between gap-2"><span>{i.quantity}× {i.name}</span><span>{money(i.line_total ?? 0, cur)}</span></li>)}</ul>
          {t && (
            <dl className="space-y-1 border-t border-primary/10 pt-3 text-sm">
              <Line k="Subtotal" v={money(t.subtotal, cur)} />
              {Number(t.discount) > 0 && <Line k={`Discount${cart.coupon_code ? ` (${cart.coupon_code})` : ""}`} v={`-${money(t.discount, cur)}`} />}
              <Line k="Delivery" v={Number(t.delivery_fee) > 0 ? money(t.delivery_fee, cur) : "Free"} />
              {Number(t.tax) > 0 && <Line k="Tax" v={money(t.tax, cur)} />}
              <div className="flex justify-between border-t border-primary/10 pt-2 font-heading text-xl text-primary"><dt>Total</dt><dd>{money(t.total, cur)}</dd></div>
            </dl>
          )}
          {cart.coupon_error && <p role="alert" className="text-xs text-red-700">{cart.coupon_error}</p>}
          <Button type="submit" className="w-full py-3.5 text-base" disabled={place.isPending}>{place.isPending ? "Placing order…" : "Place order"}</Button>
          {place.isError && <p role="alert" className="text-sm text-red-700">{(place.error as Error).message}</p>}
        </aside>
      </form>
      </div>
    </div>
  );
}
const Line = ({ k, v }: { k: string; v: string }) => <div className="flex justify-between"><dt>{k}</dt><dd>{v}</dd></div>;
