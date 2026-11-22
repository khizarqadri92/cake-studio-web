import { useState, type ChangeEvent } from "react";
import { Navigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useAuth, type Address } from "@/lib/auth";
import { api, ApiError, post } from "@/lib/api";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";
import { useSeo } from "@/lib/theme";
import { PageBanner } from "@/components/PageBanner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Empty, ErrorBox, Spinner } from "@/components/states";

type OrderRow = { order_number: string; status: string; total: string; delivery_date: string; created_at: string };
const blank = { label: "Home", line: "", city: "", postal_code: "", instructions: "", is_default: false };

function Profile() {
  const { me, reload, logout } = useAuth();
  const [name, setName] = useState(me!.full_name);
  const [phone, setPhone] = useState(me!.phone ?? "");
  const [msg, setMsg] = useState("");
  const save = useMutation({
    mutationFn: () => api("/account/me", { method: "PUT", body: JSON.stringify({ full_name: name, phone: phone || null }) }),
    onSuccess: async () => { await reload(); setMsg("Saved"); },
    onError: (e) => setMsg(e instanceof ApiError ? e.message : "Could not save"),
  });
  const resend = useMutation({ mutationFn: () => post("/auth/customer/resend-verification", {}), onSuccess: () => setMsg("Confirmation email sent"), onError: () => setMsg("Please wait a few minutes before asking again") });
  return (
    <section className="rounded-3xl bg-surface p-6 shadow-card md:p-8">
      <h2 className="font-heading text-2xl">Your details</h2>
      <p className="mt-1 text-sm text-ink/70">{me!.email} {me!.email_verified ? "· confirmed" : <>· <span className="text-amber-700">not confirmed</span> <button className="text-primary underline" onClick={() => resend.mutate()}>Resend email</button></>}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-sm">Full name<Input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="text-sm">Phone<Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={() => save.mutate()} disabled={save.isPending || !name.trim()}>Save</Button>
        <Button variant="ghost" onClick={() => void logout()}>Log out</Button>
        {msg && <span role="status" className="text-sm text-ink/70">{msg}</span>}
      </div>
    </section>
  );
}

function Addresses() {
  const { me, reload } = useAuth();
  const [edit, setEdit] = useState<(typeof blank & { id?: number }) | null>(null);
  const [err, setErr] = useState("");
  const clean = (a: typeof blank) => ({ ...a, postal_code: a.postal_code || null, instructions: a.instructions || null });
  const save = useMutation({
    mutationFn: (a: typeof blank & { id?: number }) => api(a.id ? `/account/addresses/${a.id}` : "/account/addresses", { method: a.id ? "PUT" : "POST", body: JSON.stringify(clean(a)) }),
    onSuccess: async () => { setEdit(null); setErr(""); await reload(); },
    onError: (e) => setErr(e instanceof ApiError ? e.message : "Could not save"),
  });
  const del = useMutation({ mutationFn: (id: number) => api(`/account/addresses/${id}`, { method: "DELETE" }), onSuccess: reload });
  const toForm = (a: Address) => ({ ...blank, ...a, postal_code: a.postal_code ?? "", instructions: a.instructions ?? "" });
  const up = (k: keyof typeof blank) => (e: ChangeEvent<HTMLInputElement>) => setEdit({ ...edit!, [k]: k === "is_default" ? e.target.checked : e.target.value });
  return (
    <section className="rounded-3xl bg-surface p-6 shadow-card md:p-8">
      <div className="flex items-center justify-between"><h2 className="font-heading text-2xl">Saved addresses</h2>{!edit && <Button variant="ghost" onClick={() => setEdit({ ...blank })}>Add address</Button>}</div>
      <ul className="mt-4 space-y-3">
        {me!.addresses.map((a) => (
          <li key={a.id} className="flex items-start justify-between gap-4 rounded-xl border border-primary/10 p-3 text-sm">
            <div><p className="font-medium">{a.label}{a.is_default && <span className="ml-2 rounded-full bg-secondary px-2 py-0.5 text-xs">Default</span>}</p><p>{a.line}, {a.city} {a.postal_code}</p>{a.instructions && <p className="text-ink/60">{a.instructions}</p>}</div>
            <div className="flex shrink-0 gap-3"><button className="text-primary underline" onClick={() => setEdit(toForm(a))}>Edit</button><button className="text-red-700 underline" onClick={() => { if (confirm("Delete this address?")) del.mutate(a.id); }}>Delete</button></div>
          </li>
        ))}
        {me!.addresses.length === 0 && !edit && <li className="text-sm text-ink/60">No saved addresses yet.</li>}
      </ul>
      {edit && (
        <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(edit); }}>
          <label className="text-sm">Label<Input value={edit.label} onChange={up("label")} required maxLength={50} /></label>
          <label className="text-sm">City<Input value={edit.city} onChange={up("city")} required /></label>
          <label className="text-sm sm:col-span-2">Address<Input value={edit.line} onChange={up("line")} required minLength={3} autoComplete="street-address" /></label>
          <label className="text-sm">Postal code<Input value={edit.postal_code} onChange={up("postal_code")} autoComplete="postal-code" /></label>
          <label className="text-sm">Delivery instructions<Input value={edit.instructions} onChange={up("instructions")} /></label>
          <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={edit.is_default} onChange={up("is_default")} /> Use as default</label>
          {err && <p role="alert" className="text-sm text-red-700 sm:col-span-2">{err}</p>}
          <div className="flex gap-3 sm:col-span-2"><Button type="submit" disabled={save.isPending}>Save address</Button><Button type="button" variant="ghost" onClick={() => setEdit(null)}>Cancel</Button></div>
        </form>
      )}
    </section>
  );
}

type Detail = { status_label: string; slot: string | null; payment_status: string; items: { name: string; detail: string; quantity: number; line_total: string }[] };
function OrderDetail({ number, cur }: { number: string; cur?: string }) {
  const q = useQuery({ queryKey: ["account", "order", number], queryFn: () => api<Detail>(`/account/orders/${encodeURIComponent(number)}`) });
  if (q.isLoading) return <p className="w-full text-ink/60">Loading…</p>;
  if (q.isError || !q.data) return <p role="alert" className="w-full text-red-700">Could not load this order.</p>;
  const d = q.data;
  return (
    <div className="w-full rounded-xl bg-cream p-3">
      <p>{d.status_label}{d.slot ? ` · ${d.slot}` : ""} · payment: {d.payment_status}</p>
      <ul className="mt-2 space-y-1">{d.items.map((i, n) => <li key={n} className="flex justify-between gap-3"><span>{i.quantity} × {i.name}{i.detail && <span className="text-ink/60"> ({i.detail})</span>}</span><span>{money(i.line_total, cur)}</span></li>)}</ul>
    </div>
  );
}

function Orders() {
  const [open, setOpen] = useState<string | null>(null);
  const cur = useSettings().data?.general.currency_code;
  const q = useQuery({ queryKey: ["account", "orders"], queryFn: () => api<{ total: number; items: OrderRow[] }>("/account/orders") });
  if (q.isLoading) return <Spinner />;
  if (q.isError) return <ErrorBox />;
  return (
    <section className="rounded-3xl bg-surface p-6 shadow-card md:p-8">
      <h2 className="font-heading text-2xl">Your orders</h2>
      {q.data!.items.length === 0 ? <Empty title="No orders yet" hint="Orders you place while logged in will appear here." /> : (
        <ul className="mt-4 divide-y divide-primary/10 text-sm">
          {q.data!.items.map((o) => (
            <li key={o.order_number} className="flex flex-wrap items-center justify-between gap-2 py-3">
              <div><p className="font-medium">{o.order_number}</p><p className="text-ink/60">For {o.delivery_date} · {o.status.replace(/_/g, " ")}</p></div>
              <div className="flex items-center gap-4"><span>{money(o.total, cur)}</span><button className="text-primary underline" aria-expanded={open === o.order_number} onClick={() => setOpen(open === o.order_number ? null : o.order_number)}>{open === o.order_number ? "Hide" : "Details"}</button></div>
              {open === o.order_number && <OrderDetail number={o.order_number} cur={cur} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function Account() {
  useSeo("My account");
  const { me, ready } = useAuth();
  if (!ready) return <Spinner />;
  if (!me) return <Navigate to="/account/login" replace />;
  return (
    <div>
      <PageBanner eyebrow="My account" title={`Hello, ${me.full_name.split(" ")[0]}`}>Manage your details, addresses and orders.</PageBanner>
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-10"><Profile /><Addresses /><Orders /></div>
    </div>
  );
}
