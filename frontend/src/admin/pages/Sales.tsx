import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { aapi, apost, aput, download } from "../api";
import { useStaff } from "../auth";
import { Badge, btn, Card, ErrLine, Failed, Field, inputCls, label, Loading, PageHeader, Pager, statusTone, Table, useAction } from "../kit";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";

/* ---------------- custom cakes ---------------- */
export function CustomCakesList() {
  const nav = useNavigate(); const [status, setStatus] = useState(""); const [q, setQ] = useState(""); const [page, setPage] = useState(1);
  const qs = new URLSearchParams({ page: String(page), page_size: "25", ...(status ? { status } : {}), ...(q ? { q } : {}) }).toString();
  const list = useQuery({ queryKey: ["admin", "custom-cakes", qs], queryFn: () => aapi<{ items: any[]; total: number }>(`/admin/custom-cakes?${qs}`), placeholderData: (p) => p });
  return (<>
    <PageHeader title="Custom cake requests" />
    <Card className="mb-4"><div className="grid gap-3 sm:grid-cols-2">
      <input className={inputCls} placeholder="Search reference, name, phone" aria-label="Search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      <select className={inputCls} aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option>{["new", "quoted", "approved", "declined", "expired", "converted"].map((s) => <option key={s} value={s}>{label(s)}</option>)}</select>
    </div></Card>
    <Card>{list.isLoading ? <Loading /> : list.isError ? <Failed error={list.error} /> : (<>
      <Table rows={list.data!.items} onRow={(r) => nav(`/admin/custom-cakes/${r.id}`)} cols={[
        { header: "Reference", cell: (r) => <b className="text-primary">{r.reference}</b> }, { header: "Customer", cell: (r) => <>{r.customer.name}<br /><span className="text-xs text-ink/60">{r.customer.phone}</span></> },
        { header: "Occasion", cell: (r) => r.occasion || "—" }, { header: "Needed", cell: (r) => r.required_date }, { header: "Quote", cell: (r) => r.quoted_price ?? "—" },
        { header: "Status", cell: (r) => <Badge tone={statusTone(r.status)}>{label(r.status)}</Badge> }]} />
      <Pager page={page} pageSize={25} total={list.data!.total} onPage={setPage} /></>)}</Card>
  </>);
}

export function CustomCakeDetail() {
  const { id } = useParams(); const { can } = useStaff(); const nav = useNavigate();
  const cur = useSettings().data?.general.currency_code;
  const key = ["admin", "custom-cake", id];
  const q = useQuery({ queryKey: key, queryFn: () => aapi<any>(`/admin/custom-cakes/${id}`) });
  const slots = useQuery({ queryKey: ["/admin/delivery-slots"], queryFn: () => aapi<any[]>("/admin/delivery-slots") });
  const pms = useQuery({ queryKey: ["/admin/payment-methods"], queryFn: () => aapi<any[]>("/admin/payment-methods") });
  const [quote, setQuote] = useState({ price: "", note: "", valid_until: "" }); const [note, setNote] = useState("");
  const [conv, setConv] = useState({ fulfillment: "pickup", line: "", city: "", day: "", slot_id: "", payment_method: "" }); const [showConv, setShowConv] = useState(false);
  const inv = [key, ["admin", "custom-cakes"]];
  const doQuote = useAction(() => apost(`/admin/custom-cakes/${id}/quote`, { price: quote.price, note: quote.note, valid_until: quote.valid_until || null }), inv);
  const decide = useAction((action: string) => apost(`/admin/custom-cakes/${id}/decision`, { action }), inv);
  const addNote = useAction(() => apost(`/admin/custom-cakes/${id}/notes`, { note }), inv, () => setNote(""));
  const convert = useAction(() => apost<{ order_id: number }>(`/admin/custom-cakes/${id}/convert`, { fulfillment: conv.fulfillment, address: conv.fulfillment === "delivery" ? { line: conv.line, city: conv.city } : null, day: conv.day, slot_id: Number(conv.slot_id), payment_method: conv.payment_method }), inv, (r: any) => nav(`/admin/orders/${r.order_id}`));
  if (q.isLoading) return <Loading />;
  if (q.isError) return <Failed error={q.error} />;
  const r = q.data; const w = can("orders.write");
  const rows: [string, any][] = [["Occasion", r.occasion], ["Flavour", r.flavour], ["Size / weight", r.size_or_weight], ["Needed on", `${r.required_date}${r.required_time ? " at " + r.required_time : ""}`], ["Message on cake", r.message], ["Design notes", r.design_notes], ["Instructions", r.instructions]];
  return (<>
    <PageHeader title={`Request ${r.reference}`}><Link to="/admin/custom-cakes" className={btn("ghost")}>← All requests</Link></PageHeader>
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card><div className="mb-3 flex items-center gap-2"><Badge tone={statusTone(r.status)}>{label(r.status)}</Badge>{r.order_id && <Link className="text-sm text-primary underline" to={`/admin/orders/${r.order_id}`}>View order</Link>}</div>
          <dl className="grid gap-3 sm:grid-cols-2 text-sm">{rows.filter(([, v]) => v).map(([k, v]) => <div key={k}><dt className="text-xs uppercase text-ink/60">{k}</dt><dd className="whitespace-pre-wrap">{v}</dd></div>)}</dl>
          {r.reference_images.length > 0 && <div className="mt-4 flex flex-wrap gap-3">{r.reference_images.map((u: string) => <a key={u} href={u} target="_blank" rel="noopener noreferrer"><img src={u} alt="Customer reference" className="h-28 w-28 rounded-lg object-cover" /></a>)}</div>}
        </Card>
        {r.quoted_price && <Card><h2 className="font-heading text-lg text-primary">Current quote</h2><p className="text-2xl font-semibold">{money(r.quoted_price, cur)}</p>{r.quote_note && <p className="text-sm">{r.quote_note}</p>}{r.quote_valid_until && <p className="text-xs text-ink/60">Valid until {r.quote_valid_until}</p>}</Card>}
        {w && r.status === "approved" && (
          <Card><div className="flex items-center justify-between"><h2 className="font-heading text-lg text-primary">Convert to order</h2><button className={btn("ghost")} onClick={() => setShowConv(!showConv)}>{showConv ? "Hide" : "Open"}</button></div>
            {showConv && <form className="mt-3 grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); convert.mutate(); }}>
              <Field label="Fulfillment"><select className={inputCls} value={conv.fulfillment} onChange={(e) => setConv({ ...conv, fulfillment: e.target.value })}><option value="pickup">Pickup</option><option value="delivery">Delivery</option></select></Field>
              <Field label="Date"><input className={inputCls} type="date" required value={conv.day} onChange={(e) => setConv({ ...conv, day: e.target.value })} /></Field>
              <Field label="Time slot"><select className={inputCls} required value={conv.slot_id} onChange={(e) => setConv({ ...conv, slot_id: e.target.value })}><option value="">Select…</option>{(slots.data ?? []).filter((s) => s.is_active).map((s) => <option key={s.id} value={s.id}>{String(s.start_time).slice(0, 5)}–{String(s.end_time).slice(0, 5)}</option>)}</select></Field>
              <Field label="Payment method"><select className={inputCls} required value={conv.payment_method} onChange={(e) => setConv({ ...conv, payment_method: e.target.value })}><option value="">Select…</option>{(pms.data ?? []).filter((m) => m.is_active).map((m) => <option key={m.id} value={m.code}>{m.name}</option>)}</select></Field>
              {conv.fulfillment === "delivery" && <><Field label="Address"><input className={inputCls} required value={conv.line} onChange={(e) => setConv({ ...conv, line: e.target.value })} /></Field><Field label="City"><input className={inputCls} required value={conv.city} onChange={(e) => setConv({ ...conv, city: e.target.value })} /></Field></>}
              <div className="flex items-center gap-3 sm:col-span-2"><button className={btn()} disabled={convert.isPending}>Create order</button><ErrLine error={convert.error} /></div></form>}
          </Card>)}
      </div>
      <div className="space-y-6">
        <Card><h2 className="mb-2 font-heading text-lg text-primary">Customer</h2><p className="text-sm"><b>{r.customer.name}</b><br />{r.customer.phone}<br />{r.customer.email}</p></Card>
        {w && ["new", "quoted"].includes(r.status) && <Card><h2 className="mb-2 font-heading text-lg text-primary">{r.status === "new" ? "Send quote" : "Revise quote"}</h2>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); doQuote.mutate(); }}>
            <Field label="Price"><input className={inputCls} type="number" step="0.01" min="0.01" required value={quote.price} onChange={(e) => setQuote({ ...quote, price: e.target.value })} /></Field>
            <Field label="Note to customer"><textarea className={inputCls} rows={3} maxLength={1000} value={quote.note} onChange={(e) => setQuote({ ...quote, note: e.target.value })} /></Field>
            <Field label="Valid until"><input className={inputCls} type="date" value={quote.valid_until} onChange={(e) => setQuote({ ...quote, valid_until: e.target.value })} /></Field>
            <button className={btn()} disabled={doQuote.isPending}>Send quote</button><ErrLine error={doQuote.error} /></form></Card>}
        {w && ["quoted", "approved"].includes(r.status) && <Card><h2 className="mb-2 font-heading text-lg text-primary">Record customer decision</h2>
          <p className="mb-2 text-xs text-ink/60">Use when the customer answered by phone or chat.</p>
          <div className="flex gap-2">{r.status === "quoted" && <button className={btn()} onClick={() => decide.mutate("approve")}>Approved</button>}<button className={btn("danger")} onClick={() => { if (confirm("Mark as declined?")) decide.mutate("decline"); }}>Declined</button></div><ErrLine error={decide.error} /></Card>}
        <Card><h2 className="mb-2 font-heading text-lg text-primary">Internal notes</h2><pre className="mb-3 whitespace-pre-wrap font-sans text-sm">{r.internal_notes || "No notes yet."}</pre>
          {w && <form onSubmit={(e) => { e.preventDefault(); if (note.trim()) addNote.mutate(); }}><textarea className={inputCls} rows={2} aria-label="Add note" value={note} onChange={(e) => setNote(e.target.value)} /><button className={`${btn("ghost")} mt-2`}>Add note</button><ErrLine error={addNote.error} /></form>}</Card>
      </div>
    </div></>);
}

/* ---------------- customers ---------------- */
export function CustomersList() {
  const nav = useNavigate(); const cur = useSettings().data?.general.currency_code; const [q, setQ] = useState(""); const [page, setPage] = useState(1);
  const list = useQuery({ queryKey: ["admin", "customers", q, page], queryFn: () => aapi<{ items: any[]; total: number }>(`/admin/customers?page=${page}&page_size=25${q ? `&q=${encodeURIComponent(q)}` : ""}`), placeholderData: (p) => p });
  return (<><PageHeader title="Customers" />
    <Card className="mb-4"><input className={`${inputCls} max-w-sm`} placeholder="Search name, phone, email" aria-label="Search customers" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></Card>
    <Card>{list.isLoading ? <Loading /> : list.isError ? <Failed error={list.error} /> : (<>
      <Table rows={list.data!.items} onRow={(c) => nav(`/admin/customers/${c.id}`)} cols={[{ header: "Name", cell: (c) => <b>{c.full_name}</b> }, { header: "Phone", cell: (c) => c.phone }, { header: "Email", cell: (c) => c.email ?? "—" }, { header: "Orders", cell: (c) => c.orders }, { header: "Spent", className: "text-right", cell: (c) => money(c.total_spent, cur) }]} />
      <Pager page={page} pageSize={25} total={list.data!.total} onPage={setPage} /></>)}</Card></>);
}

export function CustomerDetail() {
  const { id } = useParams(); const { can } = useStaff(); const cur = useSettings().data?.general.currency_code;
  const key = ["admin", "customer", id];
  const q = useQuery({ queryKey: key, queryFn: () => aapi<any>(`/admin/customers/${id}`) });
  const [f, setF] = useState<{ full_name: string; phone: string; email: string } | null>(null); const [note, setNote] = useState("");
  const save = useAction(() => aput(`/admin/customers/${id}`, { full_name: f!.full_name, phone: f!.phone, email: f!.email || null }), [key, ["admin", "customers"]], () => setF(null));
  const addNote = useAction(() => apost(`/admin/customers/${id}/notes`, { note }), [key], () => setNote(""));
  if (q.isLoading) return <Loading />;
  if (q.isError) return <Failed error={q.error} />;
  const c = q.data; const w = can("customers.write");
  return (<><PageHeader title={c.full_name}><Link to="/admin/customers" className={btn("ghost")}>← Customers</Link></PageHeader>
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6">
        <Card>{f ? <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <Field label="Name"><input className={inputCls} required value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field label="Phone"><input className={inputCls} required value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
          <Field label="Email"><input className={inputCls} type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <div className="flex gap-2"><button className={btn()}>Save</button><button type="button" className={btn("ghost")} onClick={() => setF(null)}>Cancel</button></div><ErrLine error={save.error} /></form>
          : <><p className="text-sm"><b>{c.full_name}</b><br />{c.phone}<br />{c.email}</p><p className="mt-2 text-sm">{c.orders} orders · {money(c.total_spent, cur)} spent</p>{w && <button className="mt-2 text-sm text-primary underline" onClick={() => setF({ full_name: c.full_name, phone: c.phone, email: c.email ?? "" })}>Edit details</button>}</>}</Card>
        <Card><h2 className="mb-2 font-heading text-lg text-primary">Notes</h2><pre className="mb-3 whitespace-pre-wrap font-sans text-sm">{c.internal_notes || "No notes yet."}</pre>
          {w && <form onSubmit={(e) => { e.preventDefault(); if (note.trim()) addNote.mutate(); }}><textarea className={inputCls} rows={2} aria-label="Add note" value={note} onChange={(e) => setNote(e.target.value)} /><button className={`${btn("ghost")} mt-2`}>Add note</button><ErrLine error={addNote.error} /></form>}</Card>
      </div>
      <Card className="lg:col-span-2"><h2 className="mb-3 font-heading text-lg text-primary">Orders</h2>
        <Table rows={c.orders_list} empty="No orders." cols={[{ header: "Order", cell: (o: any) => <Link className="text-primary" to={`/admin/orders/${o.id}`}>{o.order_number}</Link> }, { header: "For", cell: (o: any) => o.delivery_date }, { header: "Status", cell: (o: any) => <Badge tone={statusTone(o.status)}>{label(o.status)}</Badge> }, { header: "Total", className: "text-right", cell: (o: any) => money(o.total, cur) }]} /></Card>
    </div></>);
}

/* ---------------- reports ---------------- */
const REPORTS = [["daily_sales", "Daily sales"], ["weekly_sales", "Weekly sales"], ["monthly_sales", "Monthly sales"], ["annual_sales", "Annual sales"], ["product_sales", "Product-wise sales"], ["category_sales", "Category-wise sales"],
  ["best_sellers", "Best-selling products"], ["order_status", "Order status"], ["payment_methods", "Payment methods"], ["customer_purchases", "Customer purchases"], ["cancelled_orders", "Cancelled orders"], ["inventory", "Inventory"]];
export function Reports() {
  const [type, setType] = useState("daily_sales"); const d = new Date(); const iso = (x: Date) => x.toISOString().slice(0, 10);
  const [from, setFrom] = useState(iso(new Date(d.getTime() - 29 * 864e5))); const [to, setTo] = useState(iso(d));
  const qs = `date_from=${from}&date_to=${to}`;
  const q = useQuery({ queryKey: ["admin", "report", type, qs], queryFn: () => aapi<{ title: string; range: string; columns: { key: string; label: string }[]; rows: any[] }>(`/admin/reports/${type}?${qs}`) });
  const [busy, setBusy] = useState(""); const [err, setErr] = useState("");
  const exp = async (fmt: "xlsx" | "pdf") => { setBusy(fmt); setErr(""); try { await download(`/admin/reports/${type}?${qs}&format=${fmt}`, `${type}_${from}_${to}.${fmt}`); } catch (e) { setErr(e instanceof Error ? e.message : "Export failed"); } finally { setBusy(""); } };
  return (<><PageHeader title="Reports">
      <button className={btn("ghost")} disabled={!!busy} onClick={() => void exp("xlsx")}>{busy === "xlsx" ? "Exporting…" : "Export Excel"}</button>
      <button className={btn("ghost")} disabled={!!busy} onClick={() => void exp("pdf")}>{busy === "pdf" ? "Exporting…" : "Export PDF"}</button></PageHeader>
    <Card className="mb-4"><div className="grid gap-3 sm:grid-cols-3">
      <select className={inputCls} aria-label="Report" value={type} onChange={(e) => setType(e.target.value)}>{REPORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      <input className={inputCls} type="date" aria-label="From" value={from} max={to} onChange={(e) => setFrom(e.target.value)} /><input className={inputCls} type="date" aria-label="To" value={to} min={from} onChange={(e) => setTo(e.target.value)} /></div></Card>
    {err && <p role="alert" className="mb-3 text-sm text-red-700">{err}</p>}
    <Card>{q.isLoading ? <Loading /> : q.isError ? <Failed error={q.error} /> : (<><h2 className="mb-1 font-heading text-lg text-primary">{q.data!.title}</h2><p className="mb-3 text-xs text-ink/60">{q.data!.range}</p>
      <Table rows={q.data!.rows.map((r, i) => ({ ...r, id: i }))} empty="No data for this period." cols={q.data!.columns.map((c) => ({ header: c.label, cell: (r: any) => String(r[c.key] ?? "") }))} /></>)}</Card></>);
}
