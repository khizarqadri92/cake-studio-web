import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { aapi, apost, aput, adel, uploadImage } from "../api";
import { useStaff } from "../auth";
import { Badge, btn, Card, ErrLine, errMsg, Failed, Field, inputCls, Loading, PageHeader, Pager, Table, useAction } from "../kit";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";

export function ProductsList() {
  const nav = useNavigate(); const { can } = useStaff();
  const cur = useSettings().data?.general.currency_code;
  const [q, setQ] = useState(""); const [cat, setCat] = useState(""); const [page, setPage] = useState(1);
  const cats = useQuery({ queryKey: ["/admin/categories"], queryFn: () => aapi<any[]>("/admin/categories") });
  const qs = new URLSearchParams({ page: String(page), page_size: "20", ...(q ? { q } : {}), ...(cat ? { category_id: cat } : {}) }).toString();
  const list = useQuery({ queryKey: ["admin", "products", qs], queryFn: () => aapi<{ items: any[]; total: number }>(`/admin/products?${qs}`), placeholderData: (p) => p });
  return (
    <>
      <PageHeader title="Products">{can("products.write") && <Link to="/admin/products/new" className={btn()}>Add product</Link>}</PageHeader>
      <Card className="mb-4"><div className="grid gap-3 sm:grid-cols-2">
        <input className={inputCls} placeholder="Search name or SKU" aria-label="Search products" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <select className={inputCls} aria-label="Category" value={cat} onChange={(e) => { setCat(e.target.value); setPage(1); }}><option value="">All categories</option>{(cats.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
      </div></Card>
      <Card>{list.isLoading ? <Loading /> : list.isError ? <Failed error={list.error} /> : (<>
        <Table rows={list.data!.items} onRow={(p) => nav(`/admin/products/${p.id}`)} cols={[
          { header: "Product", cell: (p) => <div className="flex items-center gap-3">{p.images?.[0] ? <img src={p.images[0].url} alt="" className="h-10 w-10 rounded object-cover" /> : <div className="h-10 w-10 rounded bg-cream" />}<b>{p.name}</b></div> },
          { header: "Type", cell: (p) => p.product_type }, { header: "Price", cell: (p) => p.product_type === "variable" ? "From variants" : money(p.sale_price ?? p.base_price, cur) },
          { header: "Stock", cell: (p) => (p.track_stock ? (p.stock_qty <= p.low_stock_threshold ? <Badge tone="red">{p.stock_qty} low</Badge> : p.stock_qty) : "—") },
          { header: "Status", cell: (p) => <Badge tone={p.is_available ? "green" : "gray"}>{p.is_available ? "Available" : "Hidden"}</Badge> }]} />
        <Pager page={page} pageSize={20} total={list.data!.total} onPage={setPage} /></>)}</Card>
    </>
  );
}

const blank = { name: "", slug: "", description: "", category_id: "", product_type: "simple", base_price: "0", sale_price: "", sku: "", track_stock: false, stock_qty: 0, low_stock_threshold: 5,
  is_available: true, is_featured: false, is_bestseller: false, allows_message: false, message_max_length: 40, prep_time_hours: 24, meta_title: "", meta_description: "", images: [], variants: [], option_groups: [], addons: [] } as Record<string, any>;

function toForm(p: any) {
  const f = { ...blank, ...p };
  for (const k of ["category_id", "sale_price", "sku", "slug", "meta_title", "meta_description"]) f[k] = p[k] ?? "";
  f.variants = (p.variants ?? []).map((v: any) => ({ ...v, sale_price: v.sale_price ?? "", sku: v.sku ?? "" }));
  return f;
}
function toBody(f: Record<string, any>) {
  const n = (v: any) => (v === "" || v == null ? null : v);
  return {
    ...f, category_id: f.category_id ? Number(f.category_id) : null, slug: n(f.slug), sku: n(f.sku), meta_title: n(f.meta_title), meta_description: n(f.meta_description),
    base_price: String(f.base_price || 0), sale_price: f.product_type === "simple" ? n(f.sale_price) : null,
    stock_qty: Number(f.stock_qty), low_stock_threshold: Number(f.low_stock_threshold), message_max_length: Number(f.message_max_length), prep_time_hours: Number(f.prep_time_hours),
    variants: f.product_type === "variable" ? f.variants.map((v: any) => ({ ...v, sku: n(v.sku), sale_price: n(v.sale_price), price: String(v.price), stock_qty: Number(v.stock_qty) })) : [],
    option_groups: f.option_groups.map((g: any) => ({ ...g, choices: g.choices.map((c: any) => ({ ...c, flavour_id: c.flavour_id ? Number(c.flavour_id) : null, price_delta: String(c.price_delta || 0) })) })),
    addons: f.addons.map((a: any) => ({ ...a, price: String(a.price || 0) })),
  };
}

const Rows = ({ title, onAdd, children }: { title: string; onAdd: () => void; children: ReactNode }) => (
  <Card><div className="mb-3 flex items-center justify-between"><h2 className="font-heading text-lg text-primary">{title}</h2><button type="button" className={btn("ghost")} onClick={onAdd}>Add</button></div><div className="space-y-3">{children}</div></Card>
);
const x = (onClick: () => void) => <button type="button" aria-label="Remove" className="text-xl text-red-700" onClick={onClick}>×</button>;

export function ProductEditor() {
  const { id } = useParams(); const isNew = !id || id === "new"; const nav = useNavigate(); const { can } = useStaff();
  const cats = useQuery({ queryKey: ["/admin/categories"], queryFn: () => aapi<any[]>("/admin/categories") });
  const flavours = useQuery({ queryKey: ["/admin/flavours"], queryFn: () => aapi<any[]>("/admin/flavours") });
  const p = useQuery({ queryKey: ["admin", "product", id], enabled: !isNew, queryFn: () => aapi<any>(`/admin/products/${id}`) });
  if (!isNew && p.isLoading) return <Loading />;
  if (!isNew && p.isError) return <Failed error={p.error} />;
  return <Editor key={id} initial={isNew ? blank : toForm(p.data)} id={isNew ? null : Number(id)} cats={cats.data ?? []} flavours={flavours.data ?? []} canWrite={can("products.write")} canRecipe={can("inventory.read")} onSaved={(pid) => nav(`/admin/products/${pid}`, { replace: true })} />;
}

function Editor({ initial, id, cats, flavours, canWrite, canRecipe, onSaved }: { initial: Record<string, any>; id: number | null; cats: any[]; flavours: any[]; canWrite: boolean; canRecipe: boolean; onSaved: (id: number) => void }) {
  const nav = useNavigate();
  const [f, setF] = useState(initial); const [upErr, setUpErr] = useState("");
  const set = (k: string, v: any) => setF((s) => ({ ...s, [k]: v }));
  const setIn = (k: string, i: number, patch: Record<string, any>) => set(k, f[k].map((r: any, j: number) => (j === i ? { ...r, ...patch } : r)));
  const del = (k: string, i: number) => set(k, f[k].filter((_: any, j: number) => j !== i));
  const save = useAction(() => (id ? aput(`/admin/products/${id}`, toBody(f)) : apost("/admin/products", toBody(f))), [["admin", "products"], ["admin", "product", String(id)]], (r: any) => onSaved(r.id));
  const remove = useAction(() => adel(`/admin/products/${id}`), [["admin", "products"]], () => nav("/admin/products"));
  const variable = f.product_type === "variable";
  const dis = !canWrite;
  return (
    <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <PageHeader title={id ? `Edit: ${initial.name}` : "New product"}>
        <Link to="/admin/products" className={btn("ghost")}>← Products</Link>
        {id && canWrite && <button type="button" className={btn("danger")} onClick={() => { if (confirm("Delete this product? Existing orders keep their copy.")) remove.mutate(); }}>Delete</button>}
        {canWrite && <button className={btn()} disabled={save.isPending}>{save.isPending ? "Saving…" : "Save product"}</button>}
      </PageHeader>
      <ErrLine error={save.error ?? remove.error} />
      <fieldset disabled={dis} className="space-y-6">
        <Card><div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name *"><input className={inputCls} required value={f.name} onChange={(e) => set("name", e.target.value)} /></Field>
          <Field label="URL slug" hint="Blank = generated from the name"><input className={inputCls} value={f.slug} onChange={(e) => set("slug", e.target.value)} /></Field>
          <Field label="Category"><select className={inputCls} value={f.category_id} onChange={(e) => set("category_id", e.target.value)}><option value="">—</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <Field label="Type"><select className={inputCls} value={f.product_type} onChange={(e) => set("product_type", e.target.value)}><option value="simple">Simple (one price)</option><option value="variable">Variable (sizes / weights)</option></select></Field>
          <div className="sm:col-span-2"><Field label="Description"><textarea className={inputCls} rows={4} value={f.description} onChange={(e) => set("description", e.target.value)} /></Field></div>
          {!variable && <><Field label="Price *"><input className={inputCls} type="number" step="0.01" min="0" required value={f.base_price} onChange={(e) => set("base_price", e.target.value)} /></Field>
            <Field label="Sale price"><input className={inputCls} type="number" step="0.01" min="0" value={f.sale_price} onChange={(e) => set("sale_price", e.target.value)} /></Field></>}
          <Field label="SKU"><input className={inputCls} value={f.sku} onChange={(e) => set("sku", e.target.value)} /></Field>
          <Field label="Preparation time (hours)" hint="Customers can't order sooner than this"><input className={inputCls} type="number" min="0" value={f.prep_time_hours} onChange={(e) => set("prep_time_hours", e.target.value)} /></Field>
          <div className="flex flex-wrap gap-x-6 gap-y-2 sm:col-span-2">
            {([["is_available", "Available in shop"], ["is_featured", "Featured"], ["is_bestseller", "Bestseller"], ["allows_message", "Allow message on cake"], ["track_stock", "Track stock"]] as const).map(([k, l]) =>
              <label key={k} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f[k]} onChange={(e) => set(k, e.target.checked)} />{l}</label>)}
          </div>
          {f.allows_message && <Field label="Max message length"><input className={inputCls} type="number" min="1" max="200" value={f.message_max_length} onChange={(e) => set("message_max_length", e.target.value)} /></Field>}
          {f.track_stock && !variable && <><Field label="Stock quantity"><input className={inputCls} type="number" min="0" value={f.stock_qty} onChange={(e) => set("stock_qty", e.target.value)} /></Field>
            <Field label="Low-stock alert at"><input className={inputCls} type="number" min="0" value={f.low_stock_threshold} onChange={(e) => set("low_stock_threshold", e.target.value)} /></Field></>}
        </div></Card>

        <Rows title="Images" onAdd={() => document.getElementById("img-up")?.click()}>
          <input id="img-up" type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={async (e) => { const file = e.target.files?.[0]; e.target.value = ""; if (!file) return; setUpErr(""); try { set("images", [...f.images, { url: await uploadImage(file), alt: "" }]); } catch (x2) { setUpErr(errMsg(x2)); } }} />
          {upErr && <p role="alert" className="text-sm text-red-700">{upErr}</p>}
          <div className="grid gap-3 sm:grid-cols-3">{f.images.map((im: any, i: number) => (
            <div key={im.url + i} className="rounded-lg border border-primary/10 p-2"><img src={im.url} alt={im.alt} className="h-28 w-full rounded object-cover" />
              <input className={`${inputCls} mt-2`} placeholder="Alt text" aria-label="Alt text" value={im.alt} onChange={(e) => setIn("images", i, { alt: e.target.value })} />
              <div className="mt-1 flex justify-between text-xs">{i > 0 ? <button type="button" className="text-primary underline" onClick={() => set("images", [im, ...f.images.filter((_: any, j: number) => j !== i)])}>Make main</button> : <span>Main image</span>}<button type="button" className="text-red-700 underline" onClick={() => del("images", i)}>Remove</button></div></div>))}</div>
          {f.images.length === 0 && <p className="text-sm text-ink/60">No images yet. The first image is the main one.</p>}
        </Rows>

        {variable && <Rows title="Variants (sizes / weights)" onAdd={() => set("variants", [...f.variants, { name: "", kind: "size", sku: "", price: "0", sale_price: "", stock_qty: 0, is_active: true }])}>
          {f.variants.map((v: any, i: number) => (
            <div key={v.id ?? `n${i}`} className="grid items-end gap-2 sm:grid-cols-7">
              <Field label="Name"><input className={inputCls} required value={v.name} onChange={(e) => setIn("variants", i, { name: e.target.value })} /></Field>
              <Field label="Kind"><select className={inputCls} value={v.kind} onChange={(e) => setIn("variants", i, { kind: e.target.value })}><option value="size">Size</option><option value="weight">Weight</option></select></Field>
              <Field label="Price"><input className={inputCls} type="number" step="0.01" min="0" required value={v.price} onChange={(e) => setIn("variants", i, { price: e.target.value })} /></Field>
              <Field label="Sale"><input className={inputCls} type="number" step="0.01" min="0" value={v.sale_price} onChange={(e) => setIn("variants", i, { sale_price: e.target.value })} /></Field>
              <Field label="Stock"><input className={inputCls} type="number" min="0" value={v.stock_qty} onChange={(e) => setIn("variants", i, { stock_qty: e.target.value })} /></Field>
              <label className="flex items-center gap-1 pb-2 text-sm"><input type="checkbox" checked={v.is_active} onChange={(e) => setIn("variants", i, { is_active: e.target.checked })} />Active</label>
              {x(() => del("variants", i))}
            </div>))}
          {f.variants.length === 0 && <p className="text-sm text-ink/60">Add at least one variant.</p>}
        </Rows>}

        <Rows title="Option groups (e.g. Flavour, Filling)" onAdd={() => set("option_groups", [...f.option_groups, { name: "", is_required: true, choices: [{ label: "", flavour_id: "", price_delta: "0", is_active: true }] }])}>
          {f.option_groups.map((g: any, gi: number) => (
            <div key={g.id ?? `g${gi}`} className="rounded-lg border border-primary/10 p-3">
              <div className="flex items-end gap-3"><div className="flex-1"><Field label="Group name"><input className={inputCls} required value={g.name} onChange={(e) => setIn("option_groups", gi, { name: e.target.value })} /></Field></div>
                <label className="flex items-center gap-1 pb-2 text-sm"><input type="checkbox" checked={g.is_required} onChange={(e) => setIn("option_groups", gi, { is_required: e.target.checked })} />Required</label>{x(() => del("option_groups", gi))}</div>
              <div className="mt-3 space-y-2">{g.choices.map((c: any, ci: number) => (
                <div key={c.id ?? `c${ci}`} className="grid items-end gap-2 sm:grid-cols-5">
                  <Field label="Choice"><input className={inputCls} required value={c.label} onChange={(e) => setIn("option_groups", gi, { choices: g.choices.map((z: any, k: number) => (k === ci ? { ...z, label: e.target.value } : z)) })} /></Field>
                  <Field label="Flavour"><select className={inputCls} value={c.flavour_id ?? ""} onChange={(e) => setIn("option_groups", gi, { choices: g.choices.map((z: any, k: number) => (k === ci ? { ...z, flavour_id: e.target.value } : z)) })}><option value="">—</option>{flavours.map((fl) => <option key={fl.id} value={fl.id}>{fl.name}</option>)}</select></Field>
                  <Field label="Price +/−"><input className={inputCls} type="number" step="0.01" value={c.price_delta} onChange={(e) => setIn("option_groups", gi, { choices: g.choices.map((z: any, k: number) => (k === ci ? { ...z, price_delta: e.target.value } : z)) })} /></Field>
                  <label className="flex items-center gap-1 pb-2 text-sm"><input type="checkbox" checked={c.is_active} onChange={(e) => setIn("option_groups", gi, { choices: g.choices.map((z: any, k: number) => (k === ci ? { ...z, is_active: e.target.checked } : z)) })} />Active</label>
                  {g.choices.length > 1 && x(() => setIn("option_groups", gi, { choices: g.choices.filter((_: any, k: number) => k !== ci) }))}
                </div>))}
                <button type="button" className="text-sm text-primary underline" onClick={() => setIn("option_groups", gi, { choices: [...g.choices, { label: "", flavour_id: "", price_delta: "0", is_active: true }] })}>+ Add choice</button></div>
            </div>))}
        </Rows>

        <Rows title="Add-ons (candles, toppers…)" onAdd={() => set("addons", [...f.addons, { name: "", price: "0", is_active: true }])}>
          {f.addons.map((a: any, i: number) => (
            <div key={a.id ?? `a${i}`} className="grid items-end gap-2 sm:grid-cols-5">
              <div className="sm:col-span-2"><Field label="Name"><input className={inputCls} required value={a.name} onChange={(e) => setIn("addons", i, { name: e.target.value })} /></Field></div>
              <Field label="Price"><input className={inputCls} type="number" step="0.01" min="0" value={a.price} onChange={(e) => setIn("addons", i, { price: e.target.value })} /></Field>
              <label className="flex items-center gap-1 pb-2 text-sm"><input type="checkbox" checked={a.is_active} onChange={(e) => setIn("addons", i, { is_active: e.target.checked })} />Active</label>{x(() => del("addons", i))}
            </div>))}
        </Rows>

        <Card><div className="grid gap-4 sm:grid-cols-2"><h2 className="font-heading text-lg text-primary sm:col-span-2">SEO</h2>
          <Field label="Meta title"><input className={inputCls} value={f.meta_title} onChange={(e) => set("meta_title", e.target.value)} /></Field>
          <Field label="Meta description"><input className={inputCls} value={f.meta_description} onChange={(e) => set("meta_description", e.target.value)} /></Field></div></Card>
      </fieldset>
      {id && canRecipe && <Recipe productId={id} variants={initial.variants} />}
    </form>
  );
}

function Recipe({ productId, variants }: { productId: number; variants: any[] }) {
  const { can } = useStaff();
  const items = useQuery({ queryKey: ["admin", "inv-items-all"], queryFn: () => aapi<{ items: any[] }>("/admin/inventory/items?page_size=200") });
  const r = useQuery({ queryKey: ["admin", "recipe", productId], queryFn: () => aapi<any[]>(`/admin/products/${productId}/recipe`) });
  const [lines, setLines] = useState<any[] | null>(null);
  const cur = lines ?? r.data ?? [];
  const save = useAction(() => aput(`/admin/products/${productId}/recipe`, { lines: cur.map((l) => ({ variant_id: l.variant_id ? Number(l.variant_id) : null, item_id: Number(l.item_id), qty_per_unit: String(l.qty_per_unit) })) }), [["admin", "recipe", String(productId)]], () => setLines(null));
  const edit = (i: number, patch: any) => setLines(cur.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const w = can("inventory.write");
  return (
    <Card className="mt-6">
      <div className="mb-3 flex items-center justify-between"><h2 className="font-heading text-lg text-primary">Recipe (ingredients per unit)</h2>
        {w && <button type="button" className={btn("ghost")} onClick={() => setLines([...cur, { variant_id: "", item_id: items.data?.items[0]?.id ?? "", qty_per_unit: "1" }])}>Add ingredient</button>}</div>
      <p className="mb-3 text-xs text-ink/60">Stock of these ingredients is deducted when an order reaches the status set in Site settings → Inventory. Recipes are saved separately from the product.</p>
      {r.isLoading ? <Loading /> : cur.length === 0 ? <p className="text-sm text-ink/60">No recipe defined.</p> : cur.map((l, i) => (
        <div key={i} className="mb-2 grid items-end gap-2 sm:grid-cols-4">
          <select className={inputCls} aria-label="Ingredient" value={l.item_id} disabled={!w} onChange={(e) => edit(i, { item_id: e.target.value })}>{(items.data?.items ?? []).map((it) => <option key={it.id} value={it.id}>{it.name} ({it.unit})</option>)}</select>
          <select className={inputCls} aria-label="Variant" value={l.variant_id ?? ""} disabled={!w} onChange={(e) => edit(i, { variant_id: e.target.value })}><option value="">All variants</option>{variants.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select>
          <input className={inputCls} type="number" step="0.0001" min="0.0001" aria-label="Quantity per unit" value={l.qty_per_unit} disabled={!w} onChange={(e) => edit(i, { qty_per_unit: e.target.value })} />
          {w && <button type="button" className="text-red-700 underline" onClick={() => setLines(cur.filter((_, j) => j !== i))}>Remove</button>}
        </div>))}
      {w && lines && <div className="mt-3"><button type="button" className={btn()} disabled={save.isPending} onClick={() => save.mutate()}>Save recipe</button> <ErrLine error={save.error} /></div>}
    </Card>
  );
}
