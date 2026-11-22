import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { aapi, aput, apost } from "../api";
import { useStaff } from "../auth";
import { FieldInput, initial, toBody, type F } from "../Crud";
import { Badge, btn, Card, ErrLine, Failed, Field, ImageField, inputCls, label, Loading, PageHeader, Pager, Table, useAction } from "../kit";

/* ---------------- site settings (one tab per group) ---------------- */
const STATUS = ["pending_confirmation", "confirmed", "in_preparation", "ready_for_pickup", "out_for_delivery", "delivered", "cancelled"];
const GROUPS: Record<string, { label: string; fields: F[] }> = {
  general: { label: "General", fields: [
    { key: "site_name", label: "Site name", type: "text", required: true }, { key: "tagline", label: "Tagline", type: "text" }, { key: "logo_url", label: "Logo", type: "image" }, { key: "favicon_url", label: "Favicon", type: "image" },
    { key: "email", label: "Contact email", type: "text" }, { key: "phone", label: "Phone", type: "text" }, { key: "whatsapp", label: "WhatsApp number", type: "text" }, { key: "address", label: "Address", type: "text", span2: true },
    { key: "google_maps_embed_url", label: "Google Maps embed code", type: "text", span2: true, hint: "Google Maps > Share > Embed a map > copy HTML. Paste the whole <iframe> code." }, { key: "currency_code", label: "Currency code", type: "text", required: true, hint: "e.g. USD, PKR" }, { key: "currency_symbol", label: "Currency symbol", type: "text", required: true },
    { key: "tax_enabled", label: "Charge tax", type: "checkbox" }, { key: "tax_rate_percent", label: "Tax rate %", type: "decimal", step: "0.01" }, { key: "tax_inclusive", label: "Prices already include tax", type: "checkbox" }] },
  theme: { label: "Theme", fields: [
    { key: "primary_color", label: "Primary (buttons, headings)", type: "text", required: true }, { key: "secondary_color", label: "Secondary (accents)", type: "text", required: true }, { key: "background_color", label: "Background", type: "text", required: true },
    { key: "surface_color", label: "Cards", type: "text", required: true }, { key: "text_color", label: "Text", type: "text", required: true },
    { key: "heading_font", label: "Heading font", type: "text", required: true }, { key: "body_font", label: "Body font", type: "text", required: true },
    { key: "button_style", label: "Button style", type: "select", required: true, options: [{ value: "pill", label: "Pill" }, { value: "rounded", label: "Rounded" }, { value: "square", label: "Square" }] },
    { key: "header_layout", label: "Header layout", type: "select", required: true, options: [{ value: "centered", label: "Centered" }, { value: "left", label: "Left" }, { value: "split", label: "Split" }] },
    { key: "footer_layout", label: "Footer layout", type: "select", required: true, options: [{ value: "columns", label: "Columns" }, { value: "simple", label: "Simple" }] }] },
  social: { label: "Social", fields: ["facebook", "instagram", "tiktok", "youtube", "whatsapp"].map((k) => ({ key: k, label: label(k) + " URL", type: "text" as const })) },
  seo: { label: "SEO", fields: [{ key: "meta_title", label: "Default meta title", type: "text" }, { key: "meta_description", label: "Default meta description", type: "textarea" }, { key: "og_image_url", label: "Social share image", type: "image" }, { key: "robots_txt", label: "robots.txt", type: "textarea" }] },
  checkout: { label: "Checkout", fields: [
    { key: "delivery_fee", label: "Delivery fee", type: "decimal" }, { key: "free_delivery_over", label: "Free delivery over (blank = never)", type: "decimal" }, { key: "min_prep_hours", label: "Minimum preparation hours", type: "int", required: true },
    { key: "max_days_ahead", label: "Orders up to N days ahead", type: "int", required: true }, { key: "custom_cake_min_days", label: "Custom cake notice (days)", type: "int", required: true },
    { key: "timezone", label: "Store timezone", type: "text", required: true, hint: "IANA name, e.g. Asia/Karachi" }, { key: "pickup_address_note", label: "Pickup instructions", type: "textarea" }] },
  notifications: { label: "Notifications", fields: [
    { key: "email_enabled", label: "Send customer emails", type: "checkbox" }, { key: "whatsapp_enabled", label: "Send WhatsApp messages", type: "checkbox" }, { key: "admin_email", label: "Admin alert email", type: "text" }] },
  inventory: { label: "Inventory", fields: [{ key: "deduct_on", label: "Deduct recipe ingredients when order is", type: "select", required: true, options: [{ value: "never", label: "Never (manual stock only)" }, { value: "confirmed", label: "Confirmed" }, { value: "in_preparation", label: "In preparation" }] }] },
};
const NUMERIC = new Set(["delivery_fee", "free_delivery_over", "tax_rate_percent"]);  // these settings are JSON numbers, not strings


/* ---------------- colour palettes (theme tab) ---------------- */
type Palette = { name: string; primary: string; secondary: string; background: string; surface: string; text: string };
const COLOR_KEYS = ["primary_color", "secondary_color", "background_color", "surface_color", "text_color"] as const;
const PALETTES: Palette[] = [
  { name: "Chocolate & Cream", primary: "#8B5A3C", secondary: "#F4C2C2", background: "#FFF8F0", surface: "#FFFFFF", text: "#3E2723" },
  { name: "Strawberry Blush", primary: "#B8455F", secondary: "#FADADD", background: "#FFF5F6", surface: "#FFFFFF", text: "#3B1F27" },
  { name: "Raspberry Rose", primary: "#A63A63", secondary: "#F7CADB", background: "#FFF6FA", surface: "#FFFFFF", text: "#361A28" },
  { name: "Vanilla Gold", primary: "#9A6B1F", secondary: "#F6E3B4", background: "#FFFAEE", surface: "#FFFFFF", text: "#3A2B12" },
  { name: "Caramel Latte", primary: "#A0622D", secondary: "#EBD2B4", background: "#FBF4EA", surface: "#FFFFFF", text: "#3B2616" },
  { name: "Mocha Espresso", primary: "#5D4037", secondary: "#D7C0B0", background: "#F7F1EB", surface: "#FFFFFF", text: "#2B1B16" },
  { name: "Mint Fresh", primary: "#2E7D6B", secondary: "#CDEBDD", background: "#F3FBF7", surface: "#FFFFFF", text: "#1D3A33" },
  { name: "Pistachio", primary: "#5F7F3A", secondary: "#DDE9C2", background: "#F8FBEF", surface: "#FFFFFF", text: "#27341A" },
  { name: "Blueberry", primary: "#4A5FA8", secondary: "#D5DCF5", background: "#F5F7FE", surface: "#FFFFFF", text: "#1E2447" },
  { name: "Sky Macaron", primary: "#2F7FA8", secondary: "#CDE7F4", background: "#F3FAFE", surface: "#FFFFFF", text: "#173646" },
  { name: "Lavender Dream", primary: "#7A57A6", secondary: "#E3D6F3", background: "#FAF6FE", surface: "#FFFFFF", text: "#2D1F42" },
  { name: "Lemon Zest", primary: "#B58900", secondary: "#FFF0A8", background: "#FFFDEB", surface: "#FFFFFF", text: "#3A3000" },
  { name: "Orange Cream", primary: "#C4592A", secondary: "#FBD9BF", background: "#FFF7F0", surface: "#FFFFFF", text: "#401F0E" },
  { name: "Cherry Red", primary: "#B3262E", secondary: "#F8CFCF", background: "#FFF6F5", surface: "#FFFFFF", text: "#3D1416" },
  { name: "Peach Sorbet", primary: "#C8664F", secondary: "#FFD9C9", background: "#FFF6F1", surface: "#FFFFFF", text: "#43211A" },
  { name: "Charcoal & Gold", primary: "#2F2F36", secondary: "#E7D3A2", background: "#F7F5F0", surface: "#FFFFFF", text: "#1C1C21" },
  { name: "Midnight Berry", primary: "#4B2A5E", secondary: "#F0C9E0", background: "#FBF5FA", surface: "#FFFFFF", text: "#25122F" },
  { name: "Ocean Teal", primary: "#17717A", secondary: "#C7E9EC", background: "#F1FAFB", surface: "#FFFFFF", text: "#12363A" },
];
const matches = (p: Palette, f: Record<string, any>) =>
  [p.primary, p.secondary, p.background, p.surface, p.text].every((c, i) => String(f[COLOR_KEYS[i]] ?? "").toLowerCase() === c.toLowerCase());

function PalettePicker({ f, set, disabled }: { f: Record<string, any>; set: (patch: Record<string, any>) => void; disabled: boolean }) {
  const apply = (p: Palette) => set({ primary_color: p.primary, secondary_color: p.secondary, background_color: p.background, surface_color: p.surface, text_color: p.text });
  const labels: [typeof COLOR_KEYS[number], string][] = [["primary_color", "Primary (buttons, headings)"], ["secondary_color", "Secondary (accents)"], ["background_color", "Page background"], ["surface_color", "Cards"], ["text_color", "Text"]];
  const bg = f.background_color, sf = f.surface_color, tx = f.text_color, pr = f.primary_color, sc = f.secondary_color;
  return (
    <div className="space-y-6 sm:col-span-2">
      <div>
        <h3 className="mb-1 font-heading text-lg">Colour palettes</h3>
        <p className="mb-3 text-sm text-ink/60">Pick a palette, check the preview, then press Save to apply it across the whole website.</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="radiogroup" aria-label="Colour palettes">
          {PALETTES.map((p) => {
            const on = matches(p, f);
            return (
              <button type="button" key={p.name} role="radio" aria-checked={on} disabled={disabled} onClick={() => apply(p)}
                className={`rounded-2xl border-2 p-3 text-left transition ${on ? "border-primary bg-primary/5 shadow-sm" : "border-primary/10 hover:border-primary/40"} disabled:opacity-60`}>
                <div className="flex h-10 overflow-hidden rounded-xl ring-1 ring-black/5">
                  {[p.primary, p.secondary, p.background, p.surface, p.text].map((c, i) => <span key={i} className="flex-1" style={{ background: c }} />)}
                </div>
                <p className="mt-2 flex items-center justify-between text-sm font-medium">{p.name}{on && <span className="text-xs text-primary">✓ Selected</span>}</p>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <h3 className="mb-2 font-heading text-lg">Live preview</h3>
        <div className="overflow-hidden rounded-2xl border border-black/10" style={{ background: bg, color: tx }}>
          <div className="flex items-center justify-between px-5 py-3" style={{ background: pr, color: "#fff" }}>
            <span className="font-heading text-lg">{f._site ?? "Cake Studio"}</span>
            <span className="text-xs opacity-80">Home · Shop · Contact</span>
          </div>
          <div className="grid gap-4 p-5 sm:grid-cols-[1fr_auto] sm:items-center" style={{ background: sc + "66" }}>
            <div><p className="font-heading text-2xl" style={{ color: tx }}>Freshly Baked. Beautifully Crafted.</p><p className="mt-1 text-sm opacity-80">Celebration cakes, pastries and more.</p></div>
            <span className="inline-block rounded-full px-5 py-2 text-center text-sm font-medium" style={{ background: pr, color: "#fff" }}>Shop now</span>
          </div>
          <div className="grid gap-3 p-5 sm:grid-cols-2">
            {["Chocolate Cake", "Red Velvet"].map((n) => (
              <div key={n} className="rounded-xl p-4 shadow-sm" style={{ background: sf }}>
                <div className="mb-2 h-10 rounded-lg" style={{ background: sc }} />
                <p className="font-medium">{n}</p><p className="text-sm font-semibold" style={{ color: pr }}>1,800</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <h3 className="mb-2 font-heading text-lg">Fine-tune colours</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {labels.map(([k, l]) => (
            <label key={k} className="block text-sm"><span className="mb-1 block font-medium">{l}</span>
              <span className="flex items-center gap-2">
                <input type="color" disabled={disabled} value={/^#[0-9a-fA-F]{6}$/.test(f[k] ?? "") ? f[k] : "#000000"} onChange={(e) => set({ [k]: e.target.value.toUpperCase() })} className="h-10 w-12 cursor-pointer rounded-lg border border-primary/20 bg-white p-1" aria-label={l} />
                <input className={inputCls} value={f[k] ?? ""} maxLength={7} onChange={(e) => set({ [k]: e.target.value })} aria-label={`${l} hex`} />
              </span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

function GroupForm({ group }: { group: string }) {
  const { can } = useStaff(); const spec = GROUPS[group];
  const key = ["admin", "settings", group];
  const q = useQuery({ queryKey: key, queryFn: () => aapi<Record<string, any>>(`/admin/settings/${group}`) });
  const [f, setF] = useState<Record<string, any> | null>(null); const [saved, setSaved] = useState(false);
  useEffect(() => { if (q.data) { const d: Record<string, any> = { ...q.data }; if (group === "seo") d.keywords = d.keywords ?? []; setF({ ...initial(spec.fields, d), _raw: d }); } }, [q.data, group, spec.fields]);
  const save = useAction(() => {
    const raw = f!._raw as Record<string, any>; const body: Record<string, any> = { ...raw, ...toBody(spec.fields, f!) };
    for (const k of NUMERIC) if (k in body) body[k] = body[k] === null || body[k] === "" ? null : Number(body[k]);
    if (group === "checkout" && body.delivery_fee == null) body.delivery_fee = 0;
    if (group === "general" && body.tax_rate_percent == null) body.tax_rate_percent = 0;
    if (group === "seo") body.keywords = String(f!._keywords ?? (raw.keywords ?? []).join(", ")).split(",").map((s) => s.trim()).filter(Boolean);
    return aput(`/admin/settings/${group}`, body);
  }, [key, ["settings"]], () => setSaved(true));
  if (q.isLoading || !f) return <Loading />;
  if (q.isError) return <Failed error={q.error} />;
  const set = (k: string, v: any) => { setSaved(false); setF({ ...f, [k]: v }); };
  const patch = (p: Record<string, any>) => { setSaved(false); setF({ ...f, ...p }); };
  const w = can("settings.write");
  return (
    <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <fieldset disabled={!w} className="grid gap-4 sm:grid-cols-2">
        {group === "theme" && <PalettePicker f={f} set={patch} disabled={!w} />}
        {spec.fields.filter((x) => !(group === "theme" && (COLOR_KEYS as readonly string[]).includes(x.key))).map((x) => <div key={x.key} className={x.span2 || ["textarea", "image"].includes(x.type) ? "sm:col-span-2" : ""}><FieldInput x={x} f={f} set={set} editing /></div>)}
        {group === "seo" && <div className="sm:col-span-2"><Field label="Keywords (comma separated)"><input className={inputCls} value={f._keywords ?? (f._raw.keywords ?? []).join(", ")} onChange={(e) => set("_keywords", e.target.value)} /></Field></div>}
        {group === "general" && <HoursEditor value={f._raw.business_hours ?? []} onChange={(v) => { setSaved(false); setF({ ...f, _raw: { ...f._raw, business_hours: v } }); }} />}
        {group === "notifications" && <div className="sm:col-span-2"><p className="mb-1 text-sm font-medium">Notify the customer when an order becomes</p><div className="flex flex-wrap gap-4">{STATUS.map((s) => {
          const cur: string[] = f._raw.notify_statuses ?? [];
          return <label key={s} className="flex items-center gap-1 text-sm"><input type="checkbox" checked={cur.includes(s)} onChange={(e) => { setSaved(false); setF({ ...f, _raw: { ...f._raw, notify_statuses: e.target.checked ? [...cur, s] : cur.filter((x) => x !== s) } }); }} />{label(s)}</label>; })}</div>
          <p className="mt-2 text-xs text-ink/60">SMTP and WhatsApp credentials are set on the server (environment variables), never here.</p></div>}
      </fieldset>
      {w && <div className="mt-6 flex items-center gap-3"><button className={btn()} disabled={save.isPending}>{save.isPending ? "Saving…" : "Save changes"}</button>{saved && <span role="status" className="text-sm text-green-700">Saved</span>}<ErrLine error={save.error} /></div>}
    </form>
  );
}

function HoursEditor({ value, onChange }: { value: any[]; onChange: (v: any[]) => void }) {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const rows = days.map((d) => value.find((r) => r.day === d) ?? { day: d, open: "09:00", close: "18:00", closed: false });
  const set = (i: number, p: any) => onChange(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  return (<div className="sm:col-span-2"><p className="mb-1 text-sm font-medium">Business hours</p>
    {rows.map((r, i) => <div key={r.day} className="mb-1 flex items-center gap-3 text-sm"><span className="w-10">{r.day}</span>
      <input type="time" aria-label={`${r.day} opens`} className={`${inputCls} w-32`} disabled={r.closed} value={r.open} onChange={(e) => set(i, { open: e.target.value })} />
      <input type="time" aria-label={`${r.day} closes`} className={`${inputCls} w-32`} disabled={r.closed} value={r.close} onChange={(e) => set(i, { close: e.target.value })} />
      <label className="flex items-center gap-1"><input type="checkbox" checked={r.closed} onChange={(e) => set(i, { closed: e.target.checked })} />Closed</label></div>)}</div>);
}

export function SiteSettings() {
  const { can } = useStaff();
  const tabs = can("settings.read") ? Object.keys(GROUPS) : [];
  const [tab, setTab] = useState("general");
  return (<><PageHeader title="Site settings" />
    <div role="tablist" className="mb-4 flex flex-wrap gap-2">{tabs.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`rounded-lg px-4 py-2 text-sm ${tab === t ? "bg-primary text-white" : "bg-white hover:bg-primary/5"}`}>{GROUPS[t].label}</button>)}</div>
    <Card><GroupForm key={tab} group={tab} /></Card></>);
}

/* ---------------- homepage sections ---------------- */
function SectionEditor({ s, onClose }: { s: any; onClose: () => void }) {
  const [title, setTitle] = useState(s.title); const [visible, setVisible] = useState(s.is_visible); const [content, setContent] = useState<Record<string, any>>(s.content ?? {});
  const save = useAction(() => aput(`/admin/homepage/sections/${s.id}`, { title, is_visible: visible, content }), [["admin", "sections"], ["home"]], onClose);
  const set = (k: string, v: any) => setContent({ ...content, [k]: v });
  return (
    <form className="mt-3 space-y-3 rounded-lg bg-cream p-4" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <Field label="Heading"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
      {(Object.entries(content) as [string, any][]).map(([k, v]) => (
        <div key={k}>{Array.isArray(v) ? (<><p className="mb-1 text-sm font-medium">{label(k)}</p><div className="space-y-2">{v.map((u: string, i: number) => <div key={i} className="flex items-center gap-2"><ImageField value={u} onChange={(n) => set(k, n ? v.map((z: string, j: number) => (j === i ? n : z)) : v.filter((_: string, j: number) => j !== i))} /></div>)}
          <ImageField value={null} onChange={(n) => n && set(k, [...v, n])} /></div></>)
          : k.endsWith("image_url") ? <Field label={label(k)}><ImageField value={v} onChange={(n) => set(k, n)} /></Field>
          : typeof v === "number" ? <Field label={label(k)}><input className={inputCls} type="number" min="1" max="24" value={v} onChange={(e) => set(k, Number(e.target.value))} /></Field>
          : k === "description" ? <Field label="Description"><textarea className={inputCls} rows={3} value={v ?? ""} onChange={(e) => set(k, e.target.value)} /></Field>
          : <Field label={label(k)}><input className={inputCls} value={v ?? ""} onChange={(e) => set(k, e.target.value)} /></Field>}</div>))}
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={visible} onChange={(e) => setVisible(e.target.checked)} />Show on homepage</label>
      <div className="flex items-center gap-3"><button className={btn()} disabled={save.isPending}>Save section</button><button type="button" className={btn("ghost")} onClick={onClose}>Cancel</button><ErrLine error={save.error} /></div>
    </form>
  );
}

export function Homepage() {
  const { can } = useStaff(); const w = can("cms.write");
  const q = useQuery({ queryKey: ["admin", "sections"], queryFn: () => aapi<any[]>("/admin/homepage/sections") });
  const [open, setOpen] = useState<number | null>(null);
  const move = useAction((ids: number[]) => aput("/admin/homepage/sections/reorder", { ids }), [["admin", "sections"], ["home"]]);
  const toggle = useAction((s: any) => aput(`/admin/homepage/sections/${s.id}`, { title: s.title, content: s.content, is_visible: !s.is_visible }), [["admin", "sections"], ["home"]]);
  if (q.isLoading) return <Loading />;
  if (q.isError) return <Failed error={q.error} />;
  const rows = q.data!;
  const swap = (i: number, d: number) => { const ids = rows.map((r) => r.id); [ids[i], ids[i + d]] = [ids[i + d], ids[i]]; move.mutate(ids); };
  return (<><PageHeader title="Homepage sections" />
    <p className="mb-4 text-sm text-ink/70">Reorder, hide or edit the sections shown on your homepage.</p>
    <div className="space-y-3">{rows.map((s, i) => (
      <Card key={s.id}><div className="flex flex-wrap items-center justify-between gap-2"><div><b>{s.title || label(s.key)}</b> <span className="text-xs text-ink/50">({label(s.key)})</span> {!s.is_visible && <Badge>Hidden</Badge>}</div>
        {w && <div className="flex items-center gap-3 text-sm"><button aria-label="Move up" disabled={i === 0} className="text-primary disabled:opacity-30" onClick={() => swap(i, -1)}>↑</button><button aria-label="Move down" disabled={i === rows.length - 1} className="text-primary disabled:opacity-30" onClick={() => swap(i, 1)}>↓</button>
          <button className="text-primary underline" onClick={() => toggle.mutate(s)}>{s.is_visible ? "Hide" : "Show"}</button><button className="text-primary underline" onClick={() => setOpen(open === s.id ? null : s.id)}>{open === s.id ? "Close" : "Edit"}</button></div>}</div>
        {open === s.id && <SectionEditor s={s} onClose={() => setOpen(null)} />}</Card>))}</div>
    <ErrLine error={move.error ?? toggle.error} /></>);
}

/* ---------------- inbox (contact + newsletter) ---------------- */
export function Inbox() {
  const { can } = useStaff(); const [tab, setTab] = useState<"messages" | "newsletter">("messages"); const [page, setPage] = useState(1); const [unread, setUnread] = useState(false);
  const msgs = useQuery({ queryKey: ["admin", "contact", page, unread], queryFn: () => aapi<{ items: any[]; total: number }>(`/admin/contact-messages?page=${page}&unread=${unread}`), enabled: tab === "messages", placeholderData: (p) => p });
  const subs = useQuery({ queryKey: ["admin", "newsletter"], queryFn: () => aapi<any[]>("/admin/newsletter"), enabled: tab === "newsletter" });
  const mark = useAction((v: { id: number; is_read: boolean }) => aput(`/admin/contact-messages/${v.id}`, { is_read: v.is_read }), [["admin", "contact"]]);
  return (<><PageHeader title="Messages & subscribers" />
    <div role="tablist" className="mb-4 flex gap-2">{(["messages", "newsletter"] as const).map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`rounded-lg px-4 py-2 text-sm ${tab === t ? "bg-primary text-white" : "bg-white"}`}>{t === "messages" ? "Contact messages" : "Newsletter"}</button>)}</div>
    <Card>{tab === "messages" ? (msgs.isLoading ? <Loading /> : msgs.isError ? <Failed error={msgs.error} /> : (<>
      <label className="mb-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={unread} onChange={(e) => { setUnread(e.target.checked); setPage(1); }} />Unread only</label>
      <ul className="divide-y divide-primary/10">{msgs.data!.items.map((m) => (<li key={m.id} className={`py-3 text-sm ${m.is_read ? "" : "font-medium"}`}>
        <div className="flex flex-wrap justify-between gap-2"><span>{m.name} · <a className="text-primary" href={`mailto:${m.email}`}>{m.email}</a>{m.phone && ` · ${m.phone}`}</span><span className="text-xs text-ink/60">{m.at ? new Date(m.at).toLocaleString() : ""}</span></div>
        <p className="mt-1 whitespace-pre-wrap font-normal">{m.message}</p>{can("cms.write") && <button className="mt-1 text-xs text-primary underline" onClick={() => mark.mutate({ id: m.id, is_read: !m.is_read })}>Mark as {m.is_read ? "unread" : "read"}</button>}</li>))}
        {msgs.data!.items.length === 0 && <li className="py-6 text-center text-ink/60">No messages.</li>}</ul>
      <Pager page={page} pageSize={25} total={msgs.data!.total} onPage={setPage} /></>))
      : subs.isLoading ? <Loading /> : subs.isError ? <Failed error={subs.error} /> : <Table rows={subs.data!} empty="No subscribers yet." cols={[{ header: "Email", cell: (s) => s.email }, { header: "Subscribed", cell: (s) => (s.at ? new Date(s.at).toLocaleDateString() : "") }, { header: "Status", cell: (s) => <Badge tone={s.is_active ? "green" : "gray"}>{s.is_active ? "Active" : "Unsubscribed"}</Badge> }]} />}</Card></>);
}
void apost;
