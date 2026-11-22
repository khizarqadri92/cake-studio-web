import { Link, useLocation } from "react-router-dom";
import { buttonClass } from "@/components/ui/button";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";
import { useSeo } from "@/lib/theme";
import type { OrderPlaced } from "@/lib/types";

export default function OrderConfirmation() {
  const o = useLocation().state as OrderPlaced | null;
  const cur = useSettings().data?.general.currency_code;
  useSeo("Order confirmed");
  if (!o) return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <h1 className="text-3xl">Thank you!</h1>
      <p className="mt-3 text-ink/70">If you just placed an order, you'll receive a confirmation shortly.</p>
      <Link to="/shop" className={buttonClass("primary", "mt-6")}>Continue shopping</Link>
    </div>
  );
  return (
    <div className="mx-auto max-w-xl px-4 py-16 text-center">
      <h1 className="text-4xl">Order placed 🎂</h1>
      <p className="mt-3 text-ink/70">We'll confirm your order shortly. Keep your order number handy.</p>
      <div className="mt-8 rounded-3xl bg-surface p-6 text-left shadow-card">
        <p className="text-sm text-ink/60">Order number</p>
        <p className="font-heading text-2xl text-primary">{o.order_number}</p>
        <dl className="mt-4 space-y-1 text-sm">
          <div className="flex justify-between"><dt>Date</dt><dd>{o.delivery_date} · {o.slot}</dd></div>
          <div className="flex justify-between"><dt>Total</dt><dd>{money(o.total, cur)}</dd></div>
        </dl>
        {o.payment_instructions && <p className="mt-4 whitespace-pre-line rounded-2xl bg-secondary/30 p-4 text-sm">{o.payment_instructions}</p>}
      </div>
      <Link to="/shop" className={buttonClass("primary", "mt-8")}>Continue shopping</Link>
    </div>
  );
}
