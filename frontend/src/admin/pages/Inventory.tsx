import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { aapi, adel, aput, apost } from "../api";
import { useStaff } from "../auth";
import { FormModal, type F } from "../Crud";
import { Badge, btn, Card, ErrLine, Failed, Field, inputCls, label, Loading, Modal, PageHeader, Pager, statusTone, Table, useAction } from "../kit";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";

const KINDS = [{ value: "ingredient", label: "Ingredient" }, { value: "raw_material", label: "Raw material" }, { value: "packaging", label: "Packaging" }];

export function InventoryItems() {
  const suppliers = useQuery({ queryKey: ["/admin/suppliers"], queryFn: () => aapi<any[]>("/admin/suppliers") }).data ?? [];
  const { can } = useStaff();
  const [adj, setAdj] = useState<any | null>(null);
  const [f, setF] = useState({ kind: "purchase", quantity: "", set_to: "", note: "" });
  const adjust = useAction(() => apost(`/admin/inventory/items/${adj.id}/adjust`, f.kind === "adjustment" ? { kind: "adjustment", set_to: f.set_to, note: f.note } : { kind: f.kind, quantity: f.quantity, note: f.note }),
    [["/admin/inventory/items"], ["admin", "stock-history"]], () => { setAdj(null); setF({ kind: "purchase", quantity: "", set_to: "", note: "" }); });
  // The list endpoint is paginated ({items,total}); CrudPage expects an array, so use a thin wrapper query.
  return (<>
    <InventoryList suppliers={suppliers} onAdjust={can("inventory.write") ? setAdj : undefined} />
    {adj && (
      <Modal title={`Adjust stock: ${adj.name}`} onClose={() => setAdj(null)}>
        <p className="mb-3 text-sm">Current stock: <b>{adj.stock_qty} {adj.unit}</b></p>
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); adjust.mutate(); }}>
          <Field label="Reason"><select className={inputCls} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="purchase">Purchase (add stock)</option><option value="usage">Usage (remove)</option><option value="waste">Waste / spoilage (remove)</option><option value="adjustment">Stock count (set exact amount)</option></select></Field>
          {f.kind === "adjustment" ? <Field label={`Counted stock (${adj.unit})`}><input className={inputCls} type="number" step="0.001" min="0" required value={f.set_to} onChange={(e) => setF({ ...f, set_to: e.target.value })} /></Field>
            : <Field label={`Quantity (${adj.unit})`}><input className={inputCls} type="number" step="0.001" min="0.001" required value={f.quantity} onChange={(e) => setF({ ...f, quantity: e.target.value })} /></Field>}
          <Field label="Note"><input className={inputCls} maxLength={300} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
          <div className="flex items-center gap-3"><button className={btn()} disabled={adjust.isPending}>Apply</button><ErrLine error={adjust.error} /></div>
        </form>
      </Modal>)}
  </>);
}

function InventoryList({ suppliers, onAdjust }: { suppliers: any[]; onAdjust?: (r: any) => void }) {
  const [q, setQ] = useState(""); const [low, setLow] = useState(false);
  const qs = new URLSearchParams({ page_size: "200", ...(q ? { q } : {}), ...(low ? { low_stock: "true" } : {}) }).toString();
  return <ItemsCrud qs={qs} q={q} setQ={setQ} low={low} setLow={setLow} suppliers={suppliers} onAdjust={onAdjust} />;
}

function ItemsCrud({ qs, q, setQ, low, setLow, suppliers, onAdjust }: any) {
  // Custom page: CrudPage can't paginate, and ingredient lists want search + low-stock filter.
  const list = useQuery({ queryKey: ["/admin/inventory/items", qs], queryFn: () => aapi<{ items: any[]; total: number }>(`/admin/inventory/items?${qs}`) });
  const { can } = useStaff();
  const [edit, setEdit] = useState<any | "new" | null>(null);
  return (<>
    <PageHeader title="Ingredients & stock">{can("inventory.write") && <button className={btn()} onClick={() => setEdit("new")}>Add item</button>}</PageHeader>
    <Card className="mb-4"><div className="flex flex-wrap items-center gap-4"><input className={`${inputCls} max-w-xs`} placeholder="Search name or SKU" aria-label="Search" value={q} onChange={(e) => setQ(e.target.value)} />
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={low} onChange={(e) => setLow(e.target.checked)} />Low stock only</label></div></Card>
    <Card>{list.isLoading ? <Loading /> : list.isError ? <Failed error={list.error} /> : <Table rows={list.data!.items} cols={[
      { header: "Item", cell: (r: any) => <><b>{r.name}</b><br /><span className="text-xs text-ink/60">{r.sku ?? ""} {label(r.kind)}</span></> },
      { header: "Stock", cell: (r: any) => <>{Number(r.stock_qty)} {r.unit} {Number(r.stock_qty) <= Number(r.low_stock_threshold) && <Badge tone="red">Low</Badge>}</> },
      { header: "Alert at", cell: (r: any) => `${Number(r.low_stock_threshold)} ${r.unit}` }, { header: "Cost/unit", cell: (r: any) => r.cost_per_unit },
      { header: "Supplier", cell: (r: any) => suppliers.find((s: any) => s.id === r.supplier_id)?.name ?? "—" },
      { header: "", className: "text-right whitespace-nowrap", cell: (r: any) => <span className="space-x-3">{onAdjust && <button className="text-primary underline" onClick={() => onAdjust(r)}>Adjust</button>}{can("inventory.write") && <button className="text-primary underline" onClick={() => setEdit(r)}>Edit</button>}</span> }]} />}</Card>
    {edit && <ItemForm row={edit === "new" ? null : edit} suppliers={suppliers} onClose={() => setEdit(null)} />}
  </>);
}

function ItemForm({ row, suppliers, onClose }: { row: any | null; suppliers: any[]; onClose: () => void }) {
  const fields: F[] = [
    { key: "name", label: "Name", type: "text", required: true }, { key: "sku", label: "SKU", type: "text" }, { key: "kind", label: "Type", type: "select", required: true, default: "ingredient", options: KINDS },
    { key: "unit", label: "Unit (kg, g, l, pcs…)", type: "text", required: true, default: "kg" },
    { key: "low_stock_threshold", label: "Low-stock alert at", type: "decimal", step: "0.001", required: true, default: "0" }, { key: "cost_per_unit", label: "Cost per unit", type: "decimal", required: true, default: "0" },
    { key: "supplier_id", label: "Supplier", type: "select", options: suppliers.map((s) => ({ value: s.id, label: s.name })) },
    ...(row ? [] : [{ key: "opening_stock", label: "Opening stock", type: "decimal" as const, step: "0.001", default: "0" }]),
    { key: "is_active", label: "Active", type: "checkbox", default: true },
  ];
  const save = useAction((b: any) => (row ? aput(`/admin/inventory/items/${row.id}`, b) : apost("/admin/inventory/items", b)), [["/admin/inventory/items"]], onClose);
  const del = useAction(() => adel(`/admin/inventory/items/${row.id}`), [["/admin/inventory/items"]], onClose);
  return (<>
    <FormModal title={row ? "Edit item" : "Add item"} fields={fields} row={row ?? undefined} onSave={(b) => save.mutate(b)} onClose={onClose} pending={save.isPending} error={save.error ?? del.error} />
    {row && <div className="fixed bottom-4 right-4 z-[60]"><button className={btn("danger")} onClick={() => { if (confirm("Delete this item? It will be removed from all recipes.")) del.mutate(); }}>Delete item</button></div>}
  </>);
}

export function StockHistory() {
  const [page, setPage] = useState(1);
  const items = useQuery({ queryKey: ["admin", "inv-items-all"], queryFn: () => aapi<{ items: any[] }>("/admin/inventory/items?page_size=200") }).data?.items ?? [];
  const q = useQuery({ queryKey: ["admin", "stock-history", page], queryFn: () => aapi<{ total: number; items: any[] }>(`/admin/inventory/transactions?page=${page}&page_size=50`), placeholderData: (p) => p });
  if (q.isLoading) return <Loading />;
  if (q.isError) return <Failed error={q.error} />;
  return (<><PageHeader title="Stock history" /><Card><Table rows={q.data!.items} empty="No stock movements yet." cols={[
    { header: "When", cell: (t) => new Date(t.at).toLocaleString() }, { header: "Item", cell: (t) => items.find((i) => i.id === t.item_id)?.name ?? `#${t.item_id}` }, { header: "Type", cell: (t) => label(t.kind) },
    { header: "Change", cell: (t) => <span className={Number(t.change) < 0 ? "text-red-700" : "text-green-700"}>{Number(t.change) > 0 ? "+" : ""}{Number(t.change)}</span> }, { header: "Balance", cell: (t) => Number(t.balance) },
    { header: "Reference", cell: (t) => [t.reference, t.note].filter(Boolean).join(" · ") || "—" }]} />
    <Pager page={page} pageSize={50} total={q.data!.total} onPage={setPage} /></Card></>);
}

export function PurchaseOrders() {
  const { can } = useStaff(); const cur = useSettings().data?.general.currency_code;
  const pos = useQuery({ queryKey: ["/admin/purchase-orders"], queryFn: () => aapi<any[]>("/admin/purchase-orders") });
  const suppliers = useQuery({ queryKey: ["/admin/suppliers"], queryFn: () => aapi<any[]>("/admin/suppliers") }).data ?? [];
  const items = useQuery({ queryKey: ["admin", "inv-items-all"], queryFn: () => aapi<{ items: any[] }>("/admin/inventory/items?page_size=200") }).data?.items ?? [];
  const [open, setOpen] = useState(false);
  const [po, setPo] = useState<{ supplier_id: string; notes: string; items: { item_id: string; quantity: string; unit_cost: string }[] }>({ supplier_id: "", notes: "", items: [{ item_id: "", quantity: "1", unit_cost: "0" }] });
  const inv = [["/admin/purchase-orders"], ["/admin/inventory/items"], ["admin", "stock-history"]];
  const create = useAction(() => apost("/admin/purchase-orders", { supplier_id: po.supplier_id ? Number(po.supplier_id) : null, notes: po.notes, items: po.items.map((l) => ({ item_id: Number(l.item_id), quantity: l.quantity, unit_cost: l.unit_cost })) }), inv, () => { setOpen(false); setPo({ supplier_id: "", notes: "", items: [{ item_id: "", quantity: "1", unit_cost: "0" }] }); });
  const receive = useAction((id: number) => apost(`/admin/purchase-orders/${id}/receive`), inv);
  const cancel = useAction((id: number) => apost(`/admin/purchase-orders/${id}/cancel`), inv);
  const name = (id: number) => items.find((i) => i.id === id)?.name ?? `#${id}`;
  const setLine = (i: number, patch: any) => setPo({ ...po, items: po.items.map((l, j) => (j === i ? { ...l, ...patch } : l)) });
  return (<>
    <PageHeader title="Purchase orders">{can("inventory.write") && <button className={btn()} onClick={() => setOpen(true)}>New purchase order</button>}</PageHeader>
    <Card>{pos.isLoading ? <Loading /> : pos.isError ? <Failed error={pos.error} /> : <Table rows={pos.data!} empty="No purchase orders." cols={[
      { header: "Number", cell: (p) => <b>{p.number}</b> }, { header: "Supplier", cell: (p) => suppliers.find((s) => s.id === p.supplier_id)?.name ?? "—" },
      { header: "Items", cell: (p) => p.items.map((l: any) => `${l.quantity} × ${name(l.item_id)}`).join(", ") }, { header: "Total", cell: (p) => money(p.total_cost, cur) },
      { header: "Status", cell: (p) => <Badge tone={p.status === "received" ? "green" : p.status === "cancelled" ? "red" : statusTone(p.status)}>{label(p.status)}</Badge> },
      { header: "", className: "text-right whitespace-nowrap", cell: (p) => can("inventory.write") && p.status === "ordered" ? <span className="space-x-3"><button className="text-green-700 underline" onClick={() => { if (confirm("Mark as received and add the quantities to stock?")) receive.mutate(p.id); }}>Receive</button><button className="text-red-700 underline" onClick={() => { if (confirm("Cancel this purchase order?")) cancel.mutate(p.id); }}>Cancel</button></span> : null }]} />}
      <ErrLine error={receive.error ?? cancel.error} /></Card>
    {open && <Modal wide title="New purchase order" onClose={() => setOpen(false)}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
        <Field label="Supplier"><select className={inputCls} value={po.supplier_id} onChange={(e) => setPo({ ...po, supplier_id: e.target.value })}><option value="">—</option>{suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
        {po.items.map((l, i) => (<div key={i} className="grid items-end gap-2 sm:grid-cols-4">
          <Field label="Item"><select className={inputCls} required value={l.item_id} onChange={(e) => setLine(i, { item_id: e.target.value })}><option value="">Select…</option>{items.map((it) => <option key={it.id} value={it.id}>{it.name} ({it.unit})</option>)}</select></Field>
          <Field label="Quantity"><input className={inputCls} type="number" step="0.001" min="0.001" required value={l.quantity} onChange={(e) => setLine(i, { quantity: e.target.value })} /></Field>
          <Field label="Unit cost"><input className={inputCls} type="number" step="0.01" min="0" required value={l.unit_cost} onChange={(e) => setLine(i, { unit_cost: e.target.value })} /></Field>
          {po.items.length > 1 && <button type="button" className="pb-2 text-red-700 underline" onClick={() => setPo({ ...po, items: po.items.filter((_, j) => j !== i) })}>Remove</button>}</div>))}
        <button type="button" className="text-sm text-primary underline" onClick={() => setPo({ ...po, items: [...po.items, { item_id: "", quantity: "1", unit_cost: "0" }] })}>+ Add line</button>
        <Field label="Notes"><input className={inputCls} maxLength={1000} value={po.notes} onChange={(e) => setPo({ ...po, notes: e.target.value })} /></Field>
        <div className="flex items-center gap-3"><button className={btn()} disabled={create.isPending}>Create</button><ErrLine error={create.error} /></div>
      </form></Modal>}
  </>);
}

