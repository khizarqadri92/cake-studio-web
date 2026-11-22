import { useEffect, useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { post } from "@/lib/api";
import { safeHref } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useCartCtx } from "@/lib/cart";
import { useNavigation, useSettings } from "@/lib/queries";
import type { NavItem } from "@/lib/types";

function NavLinkItem({ item, className, activeClass = "text-primary" }: { item: NavItem; className?: string; activeClass?: string }) {
  const href = safeHref(item.url);
  if (!href) return null;
  if (/^(https?:|mailto:|tel:)/i.test(href))
    return <a href={href} className={className} {...(item.new_tab ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{item.label}</a>;
  return <NavLink to={href} end={href === "/"} className={({ isActive }) => `${className ?? ""} ${isActive ? activeClass : ""}`}>{item.label}</NavLink>;
}

const hico = (d: ReactNode) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5" aria-hidden="true">{d}</svg>
);
const H_ICONS = {
  user: hico(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>),
  bag: hico(<><path d="M5 8h14l-1 12H6L5 8Z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /></>),
  menu: hico(<path d="M4 7h16M4 12h16M4 17h16" />),
  close: hico(<path d="M6 6l12 12M18 6 6 18" />),
  phone: hico(<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z" />),
};

/** Without this, following a link from the footer keeps the old scroll offset and the new page looks like it didn't open. */
function ScrollToTop() {
  const { pathname, hash } = useLocation();
  useEffect(() => { if (!hash) window.scrollTo({ top: 0, left: 0 }); }, [pathname, hash]);
  return null;
}

function Header() {
  const { data: s } = useSettings();
  const { data: nav } = useNavigation();
  const [open, setOpen] = useState(false);
  const { count } = useCartCtx();
  const { me, ready } = useAuth();
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
  const name = s?.general.site_name ?? "Cake Studio";
  const g = s?.general;
  const items = nav?.header ?? [];
  const link = "relative py-2 text-[15px] font-medium transition hover:text-primary after:absolute after:inset-x-0 after:-bottom-0.5 after:h-0.5 after:origin-left after:scale-x-0 after:rounded-full after:bg-primary after:transition-transform hover:after:scale-x-100";
  const iconBtn = "relative flex h-10 w-10 items-center justify-center rounded-full transition hover:bg-secondary/60 hover:text-primary";
  return (
    <header className="sticky top-0 z-30 bg-cream/95 shadow-[0_1px_0_0_rgba(0,0,0,0.06)] backdrop-blur">
      {(g?.phone || g?.tagline) && (
        <div className="hidden bg-primary text-xs text-white/90 md:block">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-1.5">
            <p>{g?.tagline}</p>
            {g?.phone && <a href={`tel:${g.phone}`} className="flex items-center gap-1.5 hover:text-white"><span className="[&>svg]:h-3.5 [&>svg]:w-3.5">{H_ICONS.phone}</span>{g.phone}</a>}
          </div>
        </div>
      )}
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-3">
        <Link to="/" className="flex shrink-0 items-center gap-3" aria-label={name}>
          {g?.logo_url ? <img src={g.logo_url} alt={name} className="h-10 w-auto" /> : <span className="font-heading text-2xl text-primary md:text-3xl">{name}</span>}
        </Link>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Main">
          {items.map((i) => (
            <div key={i.id} className="group relative">
              <NavLinkItem item={i} className={link} />
              {i.children.length > 0 && (
                <div className="invisible absolute left-0 top-full flex min-w-48 flex-col gap-2 rounded-2xl bg-surface p-4 opacity-0 shadow-card transition group-hover:visible group-hover:opacity-100">
                  {i.children.map((c) => <NavLinkItem key={c.id} item={c} className="text-sm font-medium transition hover:text-primary" />)}
                </div>
              )}
            </div>
          ))}
        </nav>

        <div className="flex items-center gap-1">
          {ready && <Link to={me ? "/account" : "/account/login"} className={iconBtn} aria-label={me ? "My account" : "Log in"} title={me ? "My account" : "Log in"}>{H_ICONS.user}</Link>}
          <Link to="/cart" className={iconBtn} aria-label={`Cart, ${count} item${count === 1 ? "" : "s"}`} title="Cart">
            {H_ICONS.bag}
            {count > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[11px] font-semibold text-white">{count}</span>}
          </Link>
          <Link to="/custom-cake" className="ml-2 hidden rounded-full bg-primary px-5 py-2 text-sm font-medium text-white transition hover:opacity-90 lg:inline-block">Order a custom cake</Link>
          <button className={`${iconBtn} md:hidden`} aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? H_ICONS.close : H_ICONS.menu}</button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-primary/10 bg-cream md:hidden" aria-label="Mobile">
          <div className="mx-auto flex max-w-6xl flex-col px-4 py-3">
            {items.map((i) => (
              <div key={i.id} className="border-b border-primary/10 py-3 last:border-0">
                <NavLinkItem item={i} className="block text-base font-medium" />
                {i.children.length > 0 && <div className="mt-2 flex flex-col gap-2 pl-4">{i.children.map((c) => <NavLinkItem key={c.id} item={c} className="text-sm" />)}</div>}
              </div>
            ))}
            <Link to="/custom-cake" className="mt-3 rounded-full bg-primary px-5 py-3 text-center text-sm font-medium text-white">Order a custom cake</Link>
          </div>
        </nav>
      )}
    </header>
  );
}

const SOCIAL_ICONS: Record<string, string> = {
  facebook: "M14 8h3V4h-3a4 4 0 0 0-4 4v2H7v4h3v8h4v-8h3l1-4h-4V8.5c0-.3.2-.5.5-.5Z",
  instagram: "M7 3h10a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V7a4 4 0 0 1 4-4Zm5 5a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm5.5-2.2a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z",
  tiktok: "M16 3c.3 2.4 1.8 4 4 4.2v3.3a7.5 7.5 0 0 1-4-1.2v6.2A5.5 5.5 0 1 1 10.5 10v3.4a2.2 2.2 0 1 0 2.2 2.2V3H16Z",
  youtube: "M21.6 7.2a2.5 2.5 0 0 0-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4A2.5 2.5 0 0 0 2.4 7.2 26 26 0 0 0 2 12a26 26 0 0 0 .4 4.8 2.5 2.5 0 0 0 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4a2.5 2.5 0 0 0 1.8-1.8A26 26 0 0 0 22 12a26 26 0 0 0-.4-4.8ZM10 15V9l5 3-5 3Z",
};

function FooterNewsletter() {
  const [email, setEmail] = useState("");
  const m = useMutation({ mutationFn: () => post("/public/newsletter", { email }), onSuccess: () => setEmail("") });
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (email) m.mutate(); }} className="mt-4">
      <div className="flex overflow-hidden rounded-full bg-white/10 ring-1 ring-white/20 focus-within:ring-white/60">
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Your email" aria-label="Email for newsletter"
          className="min-w-0 flex-1 bg-transparent px-4 py-2.5 text-sm text-white placeholder:text-white/50 focus:outline-none" />
        <button type="submit" disabled={m.isPending} className="m-1 rounded-full bg-white px-4 text-sm font-medium text-primary transition hover:bg-white/90 disabled:opacity-60">Join</button>
      </div>
      {m.isSuccess && <p role="status" className="mt-2 text-xs text-white">Thanks for subscribing!</p>}
      {m.isError && <p role="alert" className="mt-2 text-xs text-white">Couldn't subscribe. Please try again.</p>}
    </form>
  );
}

function Footer() {
  const { data: s } = useSettings();
  const { data: nav } = useNavigation();
  if (!s) return null;
  const g = s.general;
  const socials = (["facebook", "instagram", "tiktok", "youtube"] as const).filter((k) => safeHref(s.social[k]));
  const wa = g.whatsapp ? `https://wa.me/${g.whatsapp.replace(/\D/g, "")}` : undefined;
  const head = "mb-4 text-sm font-semibold uppercase tracking-wider text-white";
  const lnk = "transition hover:text-white hover:underline";
  const hours = (g.business_hours ?? []).slice(0, 7);
  return (
    <footer className="mt-24 bg-primary text-white/80">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:grid-cols-2 lg:grid-cols-12">
        <div className="lg:col-span-4">
          {g.logo_url ? <img src={g.logo_url} alt={g.site_name} className="h-10 w-auto brightness-0 invert" /> : <p className="font-heading text-3xl text-white">{g.site_name}</p>}
          <p className="mt-3 max-w-xs text-sm leading-relaxed">{g.tagline}</p>
          {socials.length > 0 && (
            <div className="mt-5 flex gap-3">
              {socials.map((k) => (
                <a key={k} href={safeHref(s.social[k])} target="_blank" rel="noopener noreferrer" aria-label={k}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 transition hover:bg-white hover:text-primary">
                  <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5" aria-hidden="true"><path d={SOCIAL_ICONS[k]} /></svg>
                </a>
              ))}
            </div>
          )}
          <p className="mt-6 text-sm font-medium text-white">Get offers & new flavours</p>
          <FooterNewsletter />
        </div>

        <div className="lg:col-span-2">
          <p className={head}>Quick links</p>
          <ul className="space-y-2 text-sm">
            {(nav?.header ?? []).map((i) => <li key={i.id}><NavLinkItem item={i} className={lnk} activeClass="font-semibold text-white underline" /></li>)}
          </ul>
        </div>

        <div className="lg:col-span-2">
          <p className={head}>Help</p>
          <ul className="space-y-2 text-sm">
            {(nav?.footer ?? []).map((i) => <li key={i.id}><NavLinkItem item={i} className={lnk} activeClass="font-semibold text-white underline" /></li>)}
          </ul>
        </div>

        <div className="text-sm lg:col-span-4">
          <p className={head}>Visit & contact</p>
          <ul className="space-y-3">
            {g.address && <li>{g.address}</li>}
            {g.phone && <li><a href={`tel:${g.phone}`} className={lnk}>{g.phone}</a></li>}
            {g.email && <li><a href={`mailto:${g.email}`} className={lnk}>{g.email}</a></li>}
            {wa && <li><a href={wa} target="_blank" rel="noopener noreferrer" className={lnk}>Chat on WhatsApp</a></li>}
          </ul>
          {hours.length > 0 && (
            <div className="mt-5">
              <p className="mb-2 font-medium text-white">Opening hours</p>
              <ul className="space-y-1 text-white/70">
                {hours.map((h) => <li key={h.day} className="flex justify-between gap-6"><span>{h.day}</span><span>{h.closed ? "Closed" : `${h.open ?? ""} – ${h.close ?? ""}`}</span></li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
      <div className="border-t border-white/15">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-5 text-xs sm:flex-row">
          <p>© {new Date().getFullYear()} {g.site_name}. All rights reserved.</p>
          <p className="text-white/70">Powered by <a href="https://www.zurikhtech.com" target="_blank" rel="noopener noreferrer" className="font-medium text-white underline-offset-2 hover:underline">Zurikh Technologies</a></p>
        </div>
      </div>
    </footer>
  );
}

export function Layout() {
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:p-2">Skip to content</a>
      <ScrollToTop />
      <Header />
      <main id="main"><Outlet /></main>
      <Footer />
    </>
  );
}
