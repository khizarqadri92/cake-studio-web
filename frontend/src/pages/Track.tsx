import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { PageBanner } from "@/components/PageBanner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";
import { useSeo } from "@/lib/theme";

interface Tracked {
  order_number: string; status: string; status_label: string; fulfillment: string; delivery_date: string; slot: string;
  payment_status: string; customer_note: string;
  items: { name: string; detail: string; quantity: number; line_total: string }[];
  totals: { subtotal: string; discount: string; delivery_fee: string; tax: string; total: string };
  timeline: { status: string; label: string; at: string; note: string }[];
}
const schema = z.object({ order_number: z.string().trim().min(3, "Enter your order number"), phone: z.string().trim().min(7, "Enter the phone number used for the order") });
type Form = z.infer<typeof schema>;

export default function Track() {
  const cur = useSettings().data?.general.currency_code;
  useSeo("Track your order");
  const { register, handleSubmit, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema) });
  const m = useMutation({ mutationFn: (v: Form) => api<Tracked>(`/orders/track?order_number=${encodeURIComponent(v.order_number)}&phone=${encodeURIComponent(v.phone)}`) });
  const o = m.data;
  return (
    <div>
    <PageBanner eyebrow="Order status" title="Track your order">Enter your order number and the phone number you ordered with.</PageBanner>
    <div className="mx-auto max-w-2xl px-4 py-10">
      <form onSubmit={handleSubmit((v) => m.mutate(v))} className="grid gap-3 rounded-3xl bg-surface p-5 shadow-card sm:grid-cols-[1fr_1fr_auto]" noValidate>
        <div><Input placeholder="Order number (CS-…)" aria-label="Order number" {...register("order_number")} />{errors.order_number && <p role="alert" className="mt-1 text-xs text-red-700">{errors.order_number.message}</p>}</div>
        <div><Input placeholder="Phone number" aria-label="Phone number" {...register("phone")} />{errors.phone && <p role="alert" className="mt-1 text-xs text-red-700">{errors.phone.message}</p>}</div>
        <Button type="submit" disabled={m.isPending}>{m.isPending ? "Searching…" : "Track"}</Button>
      </form>
      {m.isError && <p role="alert" className="mt-4 text-sm text-red-700">{(m.error as Error).message}</p>}
      {o && (
        <div className="mt-8 space-y-6 rounded-3xl bg-surface p-6 shadow-card">
          <div>
            <p className="text-sm text-ink/60">Order {o.order_number}</p>
            <p className="font-heading text-3xl text-primary">{o.status_label}</p>
            <p className="text-sm">{o.fulfillment === "pickup" ? "Pickup" : "Delivery"}: {o.delivery_date} · {o.slot}</p>
            {o.customer_note && <p className="mt-2 rounded-2xl bg-secondary/30 p-3 text-sm">{o.customer_note}</p>}
          </div>
          <ol className="ml-2 space-y-5 border-l-2 border-primary/20 pl-6">
            {o.timeline.map((t, i) => (
              <li key={i} className="relative"><span className={`absolute -left-[33px] top-1 h-3 w-3 rounded-full ring-4 ring-surface ${i === o.timeline.length - 1 ? "bg-primary" : "bg-primary/40"}`} aria-hidden="true" /><p className="font-medium">{t.label}</p><p className="text-xs text-ink/60">{new Date(t.at).toLocaleString()}</p>{t.note && <p className="text-sm">{t.note}</p>}</li>
            ))}
          </ol>
          <ul className="space-y-1 border-t border-primary/10 pt-4 text-sm">
            {o.items.map((i, k) => <li key={k} className="flex justify-between gap-2"><span>{i.quantity}× {i.name}{i.detail && <span className="text-ink/60"> — {i.detail}</span>}</span><span>{money(i.line_total, cur)}</span></li>)}
            <li className="flex justify-between pt-2 font-medium"><span>Total ({o.payment_status.replace("_", " ")})</span><span>{money(o.totals.total, cur)}</span></li>
          </ul>
        </div>
      )}
    </div>
    </div>
  );
}
