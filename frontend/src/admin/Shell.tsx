import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { aapi, apost } from "./api";
import { useStaff } from "./auth";
import { btn, errMsg, inputCls, label } from "./kit";
import { useAction } from "./kit";

const NAV: { group: string; items: { to: string; label: string; perm: string }[] }[] = [
  { group: "Overview", items: [{ to: "/admin", label: "Dashboard", perm: "dashboard.read" }, { to: "/admin/reports", label: "Reports", perm: "reports.read" }] },
  { group: "Sales", items: [
    { to: "/admin/orders", label: "Orders", perm: "orders.read" }, { to: "/admin/custom-cakes", label: "Custom cakes", perm: "orders.read" },
    { to: "/admin/customers", label: "Customers", perm: "customers.read" }, { to: "/admin/coupons", label: "Coupons", perm: "coupons.read" }] },
  { group: "Catalog", items: [
    { to: "/admin/products", label: "Products", perm: "products.read" }, { to: "/admin/categories", label: "Categories", perm: "products.read" }, { to: "/admin/flavours", label: "Flavours", perm: "products.read" }, { to: "/admin/reviews", label: "Reviews", perm: "products.read" }] },
  { group: "Inventory", items: [
    { to: "/admin/inventory", label: "Ingredients & stock", perm: "inventory.read" }, { to: "/admin/suppliers", label: "Suppliers", perm: "inventory.read" },
    { to: "/admin/purchase-orders", label: "Purchase orders", perm: "inventory.read" }, { to: "/admin/stock-history", label: "Stock history", perm: "inventory.read" }] },
  { group: "Website", items: [
    { to: "/admin/homepage", label: "Homepage", perm: "cms.read" }, { to: "/admin/pages", label: "Pages", perm: "cms.read" }, { to: "/admin/navigation", label: "Navigation", perm: "cms.read" },
    { to: "/admin/banners", label: "Banners", perm: "cms.read" }, { to: "/admin/testimonials", label: "Testimonials", perm: "cms.read" }, { to: "/admin/inbox", label: "Messages", perm: "cms.read" }] },
  { group: "Settings", items: [
    { to: "/admin/settings", label: "Site settings", perm: "settings.read" }, { to: "/admin/delivery", label: "Delivery & slots", perm: "settings.read" },
    { to: "/admin/payment-methods", label: "Payment methods", perm: "settings.read" }, { to: "/admin/users", label: "Staff users", perm: "users.read" },
    { to: "/admin/roles", label: "Roles & permissions", perm: "roles.read" }, { to: "/admin/audit", label: "Audit log", perm: "audit.read" }] },
];

export function AdminLogin() {
  const { login, me, ready } = useStaff();
  const nav = useNavigate();
  const [email, setEmail] = useState(""); const [pw, setPw] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  if (ready && me) return <Navigate to="/admin" replace />;
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try { await login(email, pw); nav("/admin", { replace: true }); } catch (x) { setErr(errMsg(x)); } finally { setBusy(false); }
  }
  return (
    <div className="grid min-h-screen bg-cream lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-ink p-12 text-white lg:flex">
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-white/5" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-primary/40" aria-hidden="true" />
        <p className="relative font-heading text-3xl">Cake Studio</p>
        <div className="relative">
          <h2 className="font-heading text-4xl leading-tight text-white">Run your bakery,<br />beautifully.</h2>
          <p className="mt-4 max-w-sm text-white/70">Orders, products, stock and your website content - all in one place.</p>
        </div>
        <p className="relative text-xs text-white/50">Staff area · authorised users only</p>
      </div>
      <div className="grid place-items-center px-4 py-12">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5">
          <div>
            <p className="font-heading text-2xl text-primary lg:hidden">Cake Studio</p>
            <h1 className="mt-2 font-heading text-3xl">Welcome back</h1>
            <p className="mt-1 text-sm text-ink/60">Sign in to the admin dashboard.</p>
          </div>
          <label className="block text-sm font-medium">Email<input className={`${inputCls} mt-1 py-2.5`} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <label className="block text-sm font-medium">Password<input className={`${inputCls} mt-1 py-2.5`} type="password" autoComplete="current-password" required value={pw} onChange={(e) => setPw(e.target.value)} /></label>
          {err && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p>}
          <button className={`${btn()} w-full py-3`} disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          <Link to="/" className="block text-center text-sm text-ink/60 hover:text-primary">← Back to website</Link>
        </form>
      </div>
    </div>
  );
}

function Bell() {
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["admin", "notif"], queryFn: () => aapi<{ unread: number; items: { id: number; title: string; body: string; order_id: number | null; is_read: boolean; at: string }[] }>("/admin/notifications"), refetchInterval: 60_000 });
  const readAll = useAction(() => apost("/admin/notifications/read-all"), [["admin", "notif"]]);
  const n = q.data?.unread ?? 0;
  return (
    <div className="relative">
      <button aria-label={`Notifications, ${n} unread`} aria-expanded={open} className="relative flex h-10 w-10 items-center justify-center rounded-full text-ink/70 transition hover:bg-primary/10 hover:text-primary" onClick={() => setOpen(!open)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5" aria-hidden="true"><path d="M6 9a6 6 0 0 1 12 0c0 6 2 7 2 7H4s2-1 2-7Z" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>{n > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-semibold text-white">{n}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 max-w-[90vw] rounded-2xl border border-primary/10 bg-white p-4 shadow-xl">
          <div className="mb-2 flex justify-between text-sm"><b>Notifications</b>{n > 0 && <button className="text-primary underline" onClick={() => readAll.mutate()}>Mark all read</button>}</div>
          <ul className="max-h-80 space-y-2 overflow-y-auto text-sm">
            {(q.data?.items ?? []).map((i) => (
              <li key={i.id} className={`rounded-lg p-2 ${i.is_read ? "" : "bg-cream"}`}>
                {i.order_id ? <Link onClick={() => setOpen(false)} to={`/admin/orders/${i.order_id}`} className="font-medium text-primary">{i.title}</Link> : <b>{i.title}</b>}
                <p className="text-ink/70">{i.body}</p>
              </li>
            ))}
            {(q.data?.items.length ?? 0) === 0 && <li className="text-ink/60">No notifications.</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

const GROUP_ICONS: Record<string, string> = {"Overview": "M3 12 12 4l9 8M5 10v10h14V10", "Sales": "M3 3h2l2 12h11l2-8H6", "Catalog": "M4 7l8-4 8 4v10l-8 4-8-4V7Zm8 4v10M4 7l8 4 8-4", "Inventory": "M4 8h16v12H4V8Zm2-4h12l2 4H4l2-4Zm4 8h4", "Website": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm-9 9h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18", "Settings": "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7-3a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2-1.2L14 3h-4l-.6 2.6a7 7 0 0 0-2 1.2l-2.3-.9-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2 1.2L10 21h4l.6-2.6a7 7 0 0 0 2-1.2l2.3.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2Z"};

export function AdminShell() {
  const { me, ready, logout, can } = useStaff();
  const [menu, setMenu] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => { setMenu(false); window.scrollTo({ top: 0 }); }, [pathname]);
  if (!ready) return <p className="p-10 text-center" role="status">Loading…</p>;
  if (!me) return <Navigate to="/admin/login" replace />;
  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => can(i.perm)) })).filter((g) => g.items.length);
  const current = groups.flatMap((g) => g.items).filter((i) => i.to === pathname || (i.to !== "/admin" && pathname.startsWith(i.to + "/"))).sort((a, b) => b.to.length - a.to.length)[0];
  const initials = me.full_name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const sidebar = (
    <div className="flex h-full flex-col">
      <Link to="/admin" className="flex items-center gap-2 px-5 py-5 font-heading text-2xl text-white">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 text-lg" aria-hidden="true">🎂</span>Cake Studio
      </Link>
      <nav aria-label="Admin" className="flex-1 space-y-5 overflow-y-auto px-3 pb-6">
        {groups.map((g) => (
          <div key={g.group}>
            <p className="mb-1.5 flex items-center gap-2 px-3 text-[11px] font-semibold uppercase tracking-widest text-white/40">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5" aria-hidden="true"><path d={GROUP_ICONS[g.group]} /></svg>{g.group}
            </p>
            {g.items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.to === "/admin"} className={({ isActive }) => `block rounded-xl px-3 py-2 text-sm transition ${isActive ? "bg-white font-medium text-primary shadow-sm" : "text-white/75 hover:bg-white/10 hover:text-white"}`}>{i.label}</NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="border-t border-white/10 p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/15 text-sm font-semibold text-white">{initials}</span>
          <div className="min-w-0"><p className="truncate text-sm font-medium text-white">{me.full_name}</p><p className="truncate text-xs text-white/50">{label(me.roles[0] ?? "")}</p></div>
        </div>
        <button className="mt-3 w-full rounded-xl border border-white/20 py-2 text-sm text-white/80 transition hover:bg-white/10" onClick={() => void logout()}>Sign out</button>
      </div>
    </div>
  );
  return (
    <div className="min-h-screen bg-cream">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-ink md:block">{sidebar}</aside>
      {menu && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMenu(false)} aria-hidden="true" />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-ink shadow-xl">{sidebar}</aside>
        </div>
      )}
      <div className="md:pl-64">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-primary/10 bg-cream/90 px-4 py-3 backdrop-blur md:px-8">
          <button className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-primary/10 md:hidden" aria-label="Open menu" aria-expanded={menu} onClick={() => setMenu(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" className="h-5 w-5" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
          </button>
          <p className="font-heading text-lg text-ink">{current?.label ?? "Admin"}</p>
          <div className="ml-auto flex items-center gap-2">
            <Link to="/" target="_blank" className="hidden rounded-full border border-primary/25 px-4 py-1.5 text-sm text-primary transition hover:bg-primary/5 sm:inline-block">View website ↗</Link>
            <Bell />
          </div>
        </header>
        <main className="mx-auto max-w-7xl p-4 md:p-8"><Outlet /></main>
      </div>
    </div>
  );
}

export const Forbidden = () => <p role="alert" className="rounded-lg bg-amber-50 p-4 text-sm">You don't have permission to view this page.</p>;
export function Guard({ perm, children }: { perm: string; children: ReactNode }) {
  const { can } = useStaff();
  return can(perm) ? <>{children}</> : <Forbidden />;
}
