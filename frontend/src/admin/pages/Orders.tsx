import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { aapi, apost, download } from "../api";
import { useStaff } from "../auth";
import { Badge, btn, Card, ErrLine, Failed, Field, inputCls, label, Loading, PageHeader, Pager, statusTone, Table, useAction } from "../kit";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";

const STATUSES = ["pending_confirmation", "confirmed", "in_preparation", "ready_for_pickup", "out_for_delivery", "delivered", "cancelled", "refunded"];

export function OrdersList() {
  const nav = useNavigate();
  const cur = useSettings().data?.general.currency_code;
  const [f, setF] = useState({ q: "", status: "", fulfillment: "", payment_status: "", delivery_on: "" });
  const [page, setPage] = useState(1);
  const qs = new URLSearchParams({ page: String(page), page_size: "20", ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) }).toString();
  const q = useQuery({ queryKey: ["admin", "orders", qs], queryFn: () => aapi<{ items: any[]; total: number }>(`/admin/orders?${qs}`), placeholderData: (p) => p });
  const set = (k: string, v: string) => { setF({ ...f, [k]: v }); setPage(1); };
  return (
    <>
      <PageHeader title="Orders" />
      <Card className="mb-4"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <input className={inputCls} placeholder="Search number, name, phone, email" aria-label="Search orders" value={f.q} onChange={(e) => set("q", e.target.value)} />
        <select className={inputCls} aria-label="Status" value={f.status} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
        <select className={inputCls} aria-label="Fulfillment" value={f.fulfillment} onChange={(e) => set("fulfillment", e.target.value)}><option value="">Delivery & pickup</option><option value="delivery">Delivery</option><option value="pickup">Pickup</option></select>
        <select className={inputCls} aria-label="Payment" value={f.payment_status} onChange={(e) => set("payment_status", e.target.value)}><option value="">Any payment</option><option value="unpaid">Unpaid</option><option value="partially_paid">Partially paid</option><option value="paid">Paid</option></select>
        <input className={inputCls} type="date" aria-label="Delivery date" value={f.delivery_on} onChange={(e) => set("delivery_on", e.target.value)} />
      </div></Card>
      <Card>
        {q.isLoading ? <Loading /> : q.isError ? <Failed error={q.error} /> : (<>
          <Table rows={q.data!.items} onRow={(r) => nav(`/admin/orders/${r.id}`)} empty="No orders match." cols={[
            { header: "Order", cell: (r) => <Link className="font-medium text-primary" to={`/admin/orders/${r.id}`}>{r.order_number}</Link> },
            { header: "Customer", cell: (r) => <>{r.customer_name}<br /><span className="text-xs text-ink/60">{r.customer_phone}</span></> },
            { header: "For", cell: (r) => <>{r.delivery_date}<br /><span className="text-xs text-ink/60">{label(r.fulfillment)} · {r.slot}</span></> },
            { header: "Status", cell: (r) => <Badge tone={statusTone(r.status)}>{label(r.status)}</Badge> },
            { header: "Payment", cell: (r) => <Badge tone={statusTone(r.payment_status)}>{label(r.payment_status)}</Badge> },
            { header: "Total", className: "text-right", cell: (r) => money(r.total, cur) }]} />
          <Pager page={page} pageSize={20} total={q.data!.total} onPage={setPage} />
        </>)}
      </Card>
    </>
  );
}

export function OrderDetail() {
  const { id } = useParams();
  const { can } = useStaff();
  const cur = useSettings().data?.general.currency_code;
  const key = ["admin", "order", id];
  const q = useQuery({ queryKey: key, queryFn: () => aapi<any>(`/admin/orders/${id}`) });
  const staff = useQuery({ queryKey: ["admin", "staff"], queryFn: () => aapi<{ id: number; name: string }[]>("/admin/staff") });
  const done = (o: any) => { /* response is the fresh order */ void o; };
  const inv = [key, ["admin", "orders"]];
  const [note, setNote] = useState(""); const [internal, setInternal] = useState(""); 
  const [pay, setPay] = useState({ method: "cash", amount: "", reference: "" }); const [refund, setRefund] = useState({ amount: "", reference: "" });
  const status = useAction((s: string) => apost(`/admin/orders/${id}/status`, { status: s, note }), inv, () => setNote(""));
  const assign = useAction((u: number | null) => apost(`/admin/orders/${id}/assign`, { user_id: u }), inv, done);
  const notes = useAction((b: any) => apost(`/admin/orders/${id}/notes`, b), inv, () => { setInternal(""); });
  const addPay = useAction(() => apost(`/admin/orders/${id}/payments`, { method: pay.method, amount: pay.amount, reference: pay.reference || null }), inv, () => setPay({ ...pay, amount: "", reference: "" }));
  const verify = useAction((v: { pid: number; approve: boolean }) => apost(`/admin/orders/${id}/payments/${v.pid}/verify`, { approve: v.approve }), inv);
  const doRefund = useAction(() => apost(`/admin/orders/${id}/refunds`, { amount: refund.amount, reference: refund.reference || null }), inv, () => setRefund({ amount: "", reference: "" }));
  if (q.isLoading) return <Loading />;
  if (q.isError) return <Failed error={q.error} />;
  const o = q.data; const w = can("orders.write"); const pw = can("payments.write");
  return (
    <>
      <PageHeader title={`Order ${o.order_number}`}>
        <Link to="/admin/orders" className={btn("ghost")}>← All orders</Link>
        <button className={btn("ghost")} onClick={() => void download(`/admin/orders/${id}/invoice`, undefined, true)}>Print invoice</button>
        <button className={btn("ghost")} onClick={() => void download(`/admin/orders/${id}/invoice.pdf`, `invoice-${o.order_number}.pdf`)}>Invoice PDF</button>
      </PageHeader>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <div className="mb-3 flex flex-wrap items-center gap-2"><Badge tone={statusTone(o.status)}>{label(o.status)}</Badge><Badge tone={statusTone(o.payment_status)}>{label(o.payment_status)}</Badge><span className="text-sm text-ink/60">Placed {new Date(o.created_at).toLocaleString()}</span></div>
            <Table rows={o.items} empty="No items" cols={[
              { header: "Item", cell: (i: any) => <><b>{i.name}</b>{i.variant && <span className="text-ink/70"> · {i.variant}</span>}
                {(i.options ?? []).map((x: any) => <div key={x.label} className="text-xs text-ink/70">{x.group ? `${x.group}: ` : ""}{x.label}</div>)}
                {(i.addons ?? []).map((a: any) => <div key={a.name} className="text-xs text-ink/70">+ {a.name}</div>)}
                {i.message && <div className="text-xs">Message on cake: <b>"{i.message}"</b></div>}{i.instructions && <div className="text-xs">Note: {i.instructions}</div>}</> },
              { header: "Qty", cell: (i: any) => i.quantity }, { header: "Price", cell: (i: any) => money(i.unit_price, cur) }, { header: "Total", className: "text-right", cell: (i: any) => money(i.line_total, cur) }]} />
            <dl className="mt-4 ml-auto max-w-xs space-y-1 text-sm">
              {([["Subtotal", o.subtotal], ["Discount" + (o.coupon_code ? ` (${o.coupon_code})` : ""), `-${o.discount}`], ["Delivery", o.delivery_fee], ["Tax", o.tax]] as const).map(([k, v]) => <div key={k} className="flex justify-between"><dt>{k}</dt><dd>{money(v, cur)}</dd></div>)}
              <div className="flex justify-between border-t pt-1 font-semibold"><dt>Total</dt><dd>{money(o.total, cur)}</dd></div>
              <div className="flex justify-between"><dt>Paid</dt><dd>{money(o.paid, cur)}</dd></div><div className="flex justify-between font-medium"><dt>Balance</dt><dd>{money(o.balance, cur)}</dd></div>
            </dl>
          </Card>
          <Card>
            <h2 className="mb-3 font-heading text-lg text-primary">Payments</h2>
            <Table rows={o.payments} empty="No payments recorded." cols={[
              { header: "Method", cell: (p: any) => label(p.method) }, { header: "Amount", cell: (p: any) => money(p.amount, cur) }, { header: "Reference", cell: (p: any) => p.reference ?? "—" },
              { header: "Status", cell: (p: any) => <Badge tone={statusTone(p.status)}>{label(p.status)}</Badge> },
              { header: "", cell: (p: any) => pw && p.status === "pending" ? <span className="space-x-2"><button className="text-green-700 underline" onClick={() => verify.mutate({ pid: p.id, approve: true })}>Verify</button><button className="text-red-700 underline" onClick={() => verify.mutate({ pid: p.id, approve: false })}>Reject</button></span> : null }]} />
            {pw && (<>
              <form className="mt-4 grid gap-3 sm:grid-cols-4" onSubmit={(e) => { e.preventDefault(); addPay.mutate(); }}>
                <select className={inputCls} aria-label="Method" value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value })}>{["cash", "card_terminal", "bank_transfer", "cod", "pay_on_pickup", "online"].map((m) => <option key={m} value={m}>{label(m)}</option>)}</select>
                <input className={inputCls} type="number" step="0.01" min="0.01" required placeholder="Amount" aria-label="Amount" value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} />
                <input className={inputCls} placeholder="Reference / txn id" aria-label="Reference" value={pay.reference} onChange={(e) => setPay({ ...pay, reference: e.target.value })} />
                <button className={btn()} disabled={addPay.isPending}>Record payment</button>
              </form>
              <form className="mt-3 grid gap-3 sm:grid-cols-4" onSubmit={(e) => { e.preventDefault(); if (confirm("Record this refund?")) doRefund.mutate(); }}>
                <input className={inputCls} type="number" step="0.01" min="0.01" required placeholder="Refund amount" aria-label="Refund amount" value={refund.amount} onChange={(e) => setRefund({ ...refund, amount: e.target.value })} />
                <input className={inputCls} placeholder="Reference" aria-label="Refund reference" value={refund.reference} onChange={(e) => setRefund({ ...refund, reference: e.target.value })} />
                <button className={btn("ghost")} disabled={doRefund.isPending}>Record refund</button>
              </form>
              <ErrLine error={addPay.error ?? verify.error ?? doRefund.error} />
            </>)}
          </Card>
          <Card>
            <h2 className="mb-3 font-heading text-lg text-primary">Timeline</h2>
            <ol className="space-y-2 border-l-2 border-primary/20 pl-4 text-sm">
              {o.history.map((h: any, i: number) => <li key={i}><b>{label(h.to)}</b> <span className="text-ink/60">{new Date(h.at).toLocaleString()}</span>{h.note && <p className="text-ink/70">{h.note}</p>}</li>)}
            </ol>
          </Card>
        </div>
        <div className="space-y-6">
          <Card>
            <h2 className="mb-2 font-heading text-lg text-primary">Customer</h2>
            <p className="text-sm"><b>{o.customer_name}</b><br />{o.customer_phone}<br />{o.customer_email}</p>
            {o.customer_id && <Link className="text-sm text-primary underline" to={`/admin/customers/${o.customer_id}`}>View customer</Link>}
            <p className="mt-3 text-sm"><b>{label(o.fulfillment)}</b> on {o.delivery_date}, {o.slot}</p>
            {o.fulfillment === "delivery" && <p className="text-sm text-ink/80">{[o.address.line, o.address.city, o.address.postal_code].filter(Boolean).join(", ")}{o.address.instructions && <><br />Note: {o.address.instructions}</>}</p>}
            {o.customer_notes && <p className="mt-2 rounded-lg bg-cream p-2 text-sm">Customer note: {o.customer_notes}</p>}
          </Card>
          {w && (
            <Card>
              <h2 className="mb-2 font-heading text-lg text-primary">Update status</h2>
              {o.allowed_next.length === 0 ? <p className="text-sm text-ink/60">No further status changes.</p> : (<>
                <Field label="Note to customer (optional)"><input className={inputCls} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
                <div className="mt-3 flex flex-wrap gap-2">{o.allowed_next.map((s: string) => (
                  <button key={s} className={btn(s === "cancelled" || s === "refunded" ? "danger" : "primary")} disabled={status.isPending}
                    onClick={() => { if ((s === "cancelled" || s === "refunded") && !confirm(`Mark this order as ${label(s).toLowerCase()}?`)) return; status.mutate(s); }}>{label(s)}</button>))}</div>
                <ErrLine error={status.error} />
              </>)}
              <Field label="Assigned to"><select className={`${inputCls} mt-3`} value={o.assigned_to_id ?? ""} onChange={(e) => assign.mutate(e.target.value ? Number(e.target.value) : null)}><option value="">Unassigned</option>{(staff.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
              <ErrLine error={assign.error} />
            </Card>
          )}
          <Card>
            <h2 className="mb-2 font-heading text-lg text-primary">Internal notes</h2>
            <pre className="mb-3 whitespace-pre-wrap font-sans text-sm text-ink/80">{o.internal_notes || "No notes yet."}</pre>
            {w && (<form onSubmit={(e) => { e.preventDefault(); if (internal.trim()) notes.mutate({ internal_note: internal }); }}>
              <textarea className={inputCls} rows={2} aria-label="Add internal note" placeholder="Add a note (staff only)" value={internal} onChange={(e) => setInternal(e.target.value)} />
              <button className={`${btn("ghost")} mt-2`} disabled={notes.isPending}>Add note</button><ErrLine error={notes.error} />
            </form>)}
          </Card>
        </div>
      </div>
    </>
  );
}
