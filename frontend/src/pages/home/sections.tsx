import type { ComponentType } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { z } from "zod";
import { ProductCard } from "@/components/ProductCard";
import { buttonClass } from "@/components/ui/button";
import { post } from "@/lib/api";
import { mapEmbedUrl, safeHref } from "@/lib/format";
import { useCategories, useProducts, useSettings } from "@/lib/queries";
import type { Homepage, HomeSection } from "@/lib/types";

interface Props { section: HomeSection; home: Homepage }

type Tone = "plain" | "pink";
const Wrap = ({ title, eyebrow, action, children, tone = "plain" }: { title?: string; eyebrow?: string; action?: React.ReactNode; children: React.ReactNode; tone?: Tone }) => (
  <section className={tone === "pink" ? "bg-secondary/30 py-16 md:py-20" : "py-16 md:py-20"}>
    <div className="mx-auto max-w-6xl px-4">
      {title && (
        <div className="mb-10 flex flex-col items-center gap-3 text-center md:flex-row md:items-end md:justify-between md:text-left">
          <div>
            {eyebrow && <p className="text-sm font-medium uppercase tracking-widest text-primary">{eyebrow}</p>}
            <h2 className="mt-1 text-3xl md:text-4xl">{title}</h2>
            <span className="mx-auto mt-3 block h-1 w-12 rounded-full bg-primary/60 md:mx-0" aria-hidden="true" />
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  </section>
);

function CtaLink({ label, url, variant = "primary", extra = "" }: { label?: string; url?: string; variant?: "primary" | "secondary" | "ghost"; extra?: string }) {
  const href = safeHref(url);
  if (!label || !href) return null;
  return href.startsWith("/") ? <Link to={href} className={buttonClass(variant, extra)}>{label}</Link> : <a href={href} className={buttonClass(variant, extra)}>{label}</a>;
}

const sIco = (d: React.ReactNode) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6" aria-hidden="true">{d}</svg>
);
const FEATURES = [
  { t: "Baked fresh daily", d: "Made to order, never frozen", i: sIco(<><path d="M4 17h16M6 17c0-5 2-8 6-8s6 3 6 8" /><path d="M12 9V6" /></>) },
  { t: "Custom designs", d: "Your idea, our craft", i: sIco(<><path d="M12 3l2.5 5.5L20 9l-4 4 1 6-5-3-5 3 1-6-4-4 5.5-.5L12 3Z" /></>) },
  { t: "Choose your slot", d: "Delivery or pickup, your time", i: sIco(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>) },
  { t: "Quality ingredients", d: "Real butter, cream & chocolate", i: sIco(<path d="M12 21s-7-4.5-7-11a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 6.5-7 11-7 11Z" />) },
];

function Hero({ section: s }: Props) {
  const c = s.content;
  return (
    <>
      <section className="relative overflow-hidden bg-secondary/40">
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          <div className="absolute -left-32 top-1/3 h-96 w-96 rounded-full bg-white/50 blur-3xl" />
          <div className="absolute -right-24 -top-24 h-[28rem] w-[28rem] rounded-full bg-primary/15 blur-3xl" />
          <div className="absolute bottom-10 left-[46%] hidden h-3 w-3 rounded-full bg-primary/40 md:block" />
          <div className="absolute left-[8%] top-16 hidden h-2 w-2 rounded-full bg-primary/30 md:block" />
        </div>
        <div className="relative mx-auto grid min-h-[34rem] max-w-6xl items-center gap-12 px-4 pb-24 pt-12 md:grid-cols-[1.05fr_1fr] md:pb-32 md:pt-16">
          <div className="fade-in text-center md:text-left">
            <span className="inline-flex items-center gap-2 rounded-full bg-surface/90 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-primary shadow-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />Handcrafted bakery
            </span>
            <h1 className="mt-6 text-5xl leading-[1.05] tracking-tight md:text-7xl">{s.title}</h1>
            {c.description && <p className="mx-auto mt-6 max-w-lg text-lg leading-relaxed text-ink/75 md:mx-0 md:text-xl">{c.description}</p>}
            <div className="mt-9 flex flex-wrap justify-center gap-3 md:justify-start">
              <CtaLink label={c.cta_label} url={c.cta_url} extra="px-9 py-4 text-base shadow-lg" />
              <CtaLink label="Order a custom cake" url="/custom-cake" variant="ghost" extra="bg-surface/70 px-9 py-4 text-base" />
            </div>
            <ul className="mt-9 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-ink/70 md:justify-start">
              {["Made to order", "Choose your delivery slot", "Real butter & cream"].map((t) => (
                <li key={t} className="flex items-center gap-2">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4 text-primary" aria-hidden="true"><path d="m5 12 5 5 9-10" /></svg>{t}
                </li>
              ))}
            </ul>
          </div>

          <div className="relative mx-auto w-full max-w-md md:max-w-none">
            <div className="absolute inset-4 rounded-full bg-gradient-to-br from-primary/25 to-white/40 md:inset-0" aria-hidden="true" />
            {c.image_url ? (
              <img src={c.image_url} alt="" className="relative mx-auto aspect-square w-[88%] rounded-full border-[10px] border-surface object-cover shadow-2xl" />
            ) : (
              <div className="relative mx-auto flex aspect-square w-[88%] items-center justify-center rounded-full border-[10px] border-surface bg-secondary/60 font-heading text-3xl text-primary/50 shadow-2xl">{s.title}</div>
            )}
            <div className="absolute -left-2 bottom-10 hidden items-center gap-3 rounded-2xl bg-surface px-4 py-3 shadow-xl sm:flex md:-left-6">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary/60 text-primary">{sIco(<><path d="M4 17h16M6 17c0-5 2-8 6-8s6 3 6 8" /><path d="M12 9V6" /></>)}</span>
              <div><p className="text-sm font-semibold">Baked fresh</p><p className="text-xs text-ink/60">Every single day</p></div>
            </div>
            <div className="absolute -right-2 top-8 hidden items-center gap-3 rounded-2xl bg-surface px-4 py-3 shadow-xl sm:flex md:-right-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary/60 text-primary">{sIco(<path d="M12 21s-7-4.5-7-11a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 6.5-7 11-7 11Z" />)}</span>
              <div><p className="text-sm font-semibold">Made with love</p><p className="text-xs text-ink/60">For every occasion</p></div>
            </div>
          </div>
        </div>
        <svg viewBox="0 0 1440 80" preserveAspectRatio="none" className="absolute inset-x-0 bottom-0 h-12 w-full text-cream md:h-20" aria-hidden="true"><path fill="currentColor" d="M0 80V40c240 40 480 40 720 0s480-40 720 0v40H0Z" /></svg>
      </section>

      <section className="relative z-10 mx-auto -mt-4 max-w-6xl px-4 md:-mt-8">
        <ul className="grid grid-cols-2 gap-x-4 gap-y-6 rounded-3xl bg-surface p-6 shadow-card md:grid-cols-4 md:p-8">
          {FEATURES.map((f, i) => (
            <li key={f.t} className={`flex items-center gap-3 ${i > 0 ? "md:border-l md:border-primary/10 md:pl-6" : ""}`}>
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-secondary/50 text-primary">{f.i}</span>
              <div><p className="text-sm font-semibold">{f.t}</p><p className="text-xs text-ink/60">{f.d}</p></div>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

function Categories({ section: s }: Props) {
  const { data } = useCategories();
  if (!data?.length) return null;
  return (
    <Wrap title={s.title} eyebrow="Browse">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 md:gap-6">
        {data.filter((c) => c.parent_id === null).map((c) => (
          <Link key={c.id} to={`/shop?category=${c.slug}`} className="group relative block aspect-[4/5] overflow-hidden rounded-3xl bg-secondary/40 shadow-card">
            {c.image_url && <img src={c.image_url} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-110" />}
            <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-black/10 to-transparent" aria-hidden="true" />
            <div className="absolute inset-x-0 bottom-0 p-4 text-white md:p-5">
              <p className="font-heading text-xl">{c.name}</p>
              <p className="mt-1 text-xs opacity-0 transition group-hover:opacity-100">Shop now →</p>
            </div>
          </Link>
        ))}
      </div>
    </Wrap>
  );
}

function ProductRow({ section: s, query, tone }: Props & { query: string; tone?: Tone }) {
  const limit = Math.min(Number(s.content.limit) || 8, 12);
  const { data } = useProducts(`${query}&page_size=${limit}`);
  if (!data?.items.length) return null; // hide empty sections instead of showing a blank block
  return (
    <Wrap title={s.title} tone={tone} eyebrow="Our cakes" action={<Link to="/shop" className={buttonClass("ghost")}>View all →</Link>}>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 md:gap-6">{data.items.map((p) => <ProductCard key={p.id} p={p} />)}</div>
    </Wrap>
  );
}

function Promotions({ home }: Props) {
  const banners = home.banners.filter((b) => b.placement === "home_promo");
  if (!banners.length) return null;
  return (
    <Wrap eyebrow="Offers">
      <div className="grid gap-5 md:grid-cols-2">
        {banners.map((b) => {
          const href = safeHref(b.link_url);
          const inner = (
            <div className="group relative flex min-h-64 items-end overflow-hidden rounded-3xl bg-primary p-7 text-white shadow-card md:min-h-72">
              {b.image_url && <img src={b.image_url} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105" />}
              <div className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/30 to-transparent" aria-hidden="true" />
              <div className="relative max-w-xs">
                <p className="font-heading text-3xl leading-tight text-white">{b.title}</p>
                {b.subtitle && <p className="mt-2 text-sm text-white/85">{b.subtitle}</p>}
                {href && <span className="mt-4 inline-block rounded-full bg-white px-5 py-2 text-sm font-medium text-primary transition group-hover:bg-secondary">Shop now →</span>}
              </div>
            </div>
          );
          return href ? (href.startsWith("/") ? <Link key={b.id} to={href}>{inner}</Link> : <a key={b.id} href={href}>{inner}</a>) : <div key={b.id}>{inner}</div>;
        })}
      </div>
    </Wrap>
  );
}

function CustomCake({ section: s }: Props) {
  const c = s.content;
  return (
    <section className="px-4 py-12 md:py-16">
      <div className="relative mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-gradient-to-br from-secondary/70 to-secondary/30 px-6 py-14 text-center shadow-card md:px-16 md:py-20">
        <div className="pointer-events-none absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/40" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-16 -left-10 h-56 w-56 rounded-full bg-primary/10" aria-hidden="true" />
        <div className="relative mx-auto max-w-2xl">
          <p className="text-sm font-medium uppercase tracking-widest text-primary">Made just for you</p>
          <h2 className="mt-2 text-3xl md:text-5xl">{s.title}</h2>
          {c.description && <p className="mt-4 text-lg text-ink/75">{c.description}</p>}
          <ol className="mx-auto mt-8 grid max-w-xl gap-3 text-sm sm:grid-cols-3">
            {["Share your idea", "Get a quote", "We bake & deliver"].map((t, i) => (
              <li key={t} className="flex items-center justify-center gap-2 rounded-full bg-surface/80 px-4 py-2"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">{i + 1}</span>{t}</li>
            ))}
          </ol>
          <div className="mt-8"><CtaLink label={c.cta_label} url={c.cta_url} extra="px-8 py-3.5 text-base" /></div>
        </div>
      </div>
    </section>
  );
}

function About({ section: s }: Props) {
  const c = s.content;
  return (
    <Wrap>
      <div className="mx-auto grid max-w-5xl items-center gap-10 md:grid-cols-2 md:gap-14">
        {c.image_url && (
          <div className="relative">
            <div className="absolute -bottom-4 -left-4 h-full w-full rounded-3xl bg-secondary/60" aria-hidden="true" />
            <img src={c.image_url} alt="" loading="lazy" className="relative aspect-[4/3] w-full rounded-3xl object-cover shadow-card" />
          </div>
        )}
        <div className={c.image_url ? "" : "text-center md:col-span-2"}>
          <p className="text-sm font-medium uppercase tracking-widest text-primary">Our story</p>
          <h2 className="mt-1 text-3xl md:text-4xl">{s.title}</h2>
          {c.description && <p className="mt-4 text-lg leading-relaxed text-ink/75">{c.description}</p>}
          <ul className="mt-6 grid grid-cols-3 gap-4 text-center">
            {[["100%", "Made to order"], ["Real", "Butter & cream"], ["Fresh", "Every single day"]].map(([k, v]) => (
              <li key={k} className="rounded-2xl bg-secondary/30 px-2 py-4"><p className="font-heading text-2xl text-primary">{k}</p><p className="text-xs text-ink/70">{v}</p></li>
            ))}
          </ul>
          <Link to="/p/about" className={buttonClass("primary", "mt-8")}>Read our story</Link>
        </div>
      </div>
    </Wrap>
  );
}

function Testimonials({ section: s, home }: Props) {
  if (!home.testimonials.length) return null;
  return (
    <Wrap title={s.title} tone="pink" eyebrow="Reviews">
      <div className="grid gap-5 md:grid-cols-3">
        {home.testimonials.slice(0, 6).map((t) => (
          <figure key={t.id} className="relative flex flex-col rounded-3xl bg-surface p-7 shadow-card">
            <span className="absolute right-6 top-3 font-heading text-6xl leading-none text-primary/15" aria-hidden="true">“</span>
            <div aria-label={`${t.rating} out of 5 stars`} className="text-lg tracking-wide text-amber-500">{"★".repeat(t.rating)}<span className="text-ink/20">{"★".repeat(5 - t.rating)}</span></div>
            <blockquote className="mt-3 flex-1 leading-relaxed text-ink/85">{t.quote}</blockquote>
            <figcaption className="mt-5 flex items-center gap-3 border-t border-primary/10 pt-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-sm font-semibold text-white">{t.name.trim()[0]?.toUpperCase()}</span>
              <span className="text-sm font-medium">{t.name}<span className="block text-xs font-normal text-ink/50">Verified customer</span></span>
            </figcaption>
          </figure>
        ))}
      </div>
    </Wrap>
  );
}

function SocialGallery({ section: s }: Props) {
  const { data } = useSettings();
  const images: string[] = Array.isArray(s.content.images) ? s.content.images.filter((u: unknown) => typeof u === "string") : [];
  if (!images.length) return null;
  const ig = safeHref(data?.social.instagram);
  return (
    <Wrap title={s.title} eyebrow="Instagram">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">{images.slice(0, 8).map((u) => <div key={u} className="group overflow-hidden rounded-3xl shadow-card"><img src={u} alt="" loading="lazy" className="aspect-square w-full object-cover transition duration-500 group-hover:scale-110" /></div>)}</div>
      {ig && <p className="mt-6 text-center"><a href={ig} target="_blank" rel="noopener noreferrer" className={buttonClass("ghost")}>Follow on Instagram</a></p>}
    </Wrap>
  );
}

const emailSchema = z.object({ email: z.string().email("Enter a valid email") });
function Newsletter({ section: s }: Props) {
  const { register, handleSubmit, reset, formState: { errors } } = useForm<{ email: string }>({ resolver: zodResolver(emailSchema) });
  const m = useMutation({ mutationFn: (v: { email: string }) => post("/public/newsletter", v), onSuccess: () => reset() });
  return (
    <section className="px-4 py-12 md:py-16">
      <div className="relative mx-auto max-w-5xl overflow-hidden rounded-[2rem] bg-primary px-6 py-12 text-center text-white shadow-card md:px-16 md:py-16">
        <div className="pointer-events-none absolute -left-16 -top-16 h-56 w-56 rounded-full bg-white/10" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-20 -right-10 h-64 w-64 rounded-full bg-white/10" aria-hidden="true" />
        <div className="relative mx-auto max-w-xl">
          <p className="text-sm font-medium uppercase tracking-widest text-white/70">Newsletter</p>
          <h2 className="mt-2 text-3xl text-white md:text-4xl">{s.title}</h2>
          {s.content.description && <p className="mt-3 text-white/80">{s.content.description}</p>}
          <form onSubmit={handleSubmit((v) => m.mutate(v))} className="mt-8" noValidate>
            <div className="flex overflow-hidden rounded-full bg-white p-1.5 shadow-lg">
              <input type="email" placeholder="Enter your email address" aria-label="Email" aria-invalid={!!errors.email} {...register("email")}
                className="min-w-0 flex-1 bg-transparent px-4 text-sm text-ink placeholder:text-ink/40 focus:outline-none" />
              <button type="submit" disabled={m.isPending} className="rounded-full bg-primary px-6 py-3 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-60">
                {m.isPending ? "Subscribing…" : "Subscribe"}
              </button>
            </div>
            {errors.email && <p role="alert" className="mt-2 text-sm text-white">{errors.email.message}</p>}
          </form>
          {m.isSuccess && <p role="status" className="mt-4 rounded-full bg-white/15 px-4 py-2 text-sm">Thank you for subscribing!</p>}
          {m.isError && <p role="alert" className="mt-4 text-sm">Couldn't subscribe. Please try again.</p>}
          <p className="mt-4 text-xs text-white/60">No spam - just offers and new flavours. Unsubscribe anytime.</p>
        </div>
      </div>
    </section>
  );
}

const cIco = (d: React.ReactNode) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5" aria-hidden="true">{d}</svg>
);

function ContactBlock({ section: s }: Props) {
  const { data } = useSettings();
  if (!data) return null;
  const g = data.general;
  if (!g.phone && !g.email && !g.address) return null;
  const today = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][new Date().getDay()];
  const todayHours = (g.business_hours ?? []).find((h) => h.day.slice(0, 3).toLowerCase() === today.toLowerCase());
  const rows = [
    g.address && { icon: cIco(<><path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21Z" /><circle cx="12" cy="9.5" r="2.5" /></>), label: "Address", node: g.address },
    g.phone && { icon: cIco(<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z" />), label: "Phone", node: <a href={`tel:${g.phone}`} className="hover:text-primary">{g.phone}</a> },
    g.email && { icon: cIco(<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>), label: "Email", node: <a href={`mailto:${g.email}`} className="hover:text-primary">{g.email}</a> },
    todayHours && { icon: cIco(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>), label: "Open today", node: todayHours.closed ? "Closed today" : `${todayHours.open ?? ""} – ${todayHours.close ?? ""}` },
  ].filter(Boolean) as { icon: React.ReactNode; label: string; node: React.ReactNode }[];
  const map = mapEmbedUrl(g.google_maps_embed_url) ?? (g.address ? `https://www.google.com/maps?q=${encodeURIComponent(g.address)}&output=embed` : undefined);
  return (
    <section className="mx-auto max-w-6xl px-4 py-12 md:py-16">
      <div className="mb-10 text-center">
        <p className="text-sm font-medium uppercase tracking-widest text-primary">Find us</p>
        <h2 className="mt-2 text-3xl md:text-4xl">{s.title}</h2>
      </div>
      <div className="grid overflow-hidden rounded-[2rem] bg-surface shadow-card lg:grid-cols-5">
        <div className="space-y-5 p-6 md:p-10 lg:col-span-2">
          {rows.map((r) => (
            <div key={r.label} className="flex items-start gap-4">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-secondary/60 text-primary">{r.icon}</span>
              <div className="min-w-0"><p className="text-sm text-ink/60">{r.label}</p><p className="break-words font-medium">{r.node}</p></div>
            </div>
          ))}
          <div className="flex flex-wrap gap-3 pt-2">
            <Link to="/contact" className={buttonClass("primary")}>Get in touch</Link>
            {g.address && <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(g.address)}`} target="_blank" rel="noopener noreferrer" className={buttonClass("ghost")}>Directions</a>}
          </div>
        </div>
        <div className="min-h-72 lg:col-span-3">
          {map ? <iframe title="Map" src={map} loading="lazy" className="h-full min-h-72 w-full border-0" referrerPolicy="no-referrer-when-downgrade" />
            : <div className="flex h-full min-h-72 items-center justify-center bg-secondary/30 text-ink/50">Map coming soon</div>}
        </div>
      </div>
    </section>
  );
}

/** Section key (set in admin) -> component. Unknown keys are ignored, so new sections can be added safely. */
export const SECTION_COMPONENTS: Record<string, ComponentType<Props>> = {
  hero: Hero,
  categories: Categories,
  featured_products: (p) => <ProductRow {...p} query="featured=true&sort=popular" />,
  best_sellers: (p) => <ProductRow {...p} query="bestseller=true&sort=popular" tone="pink" />,
  new_arrivals: (p) => <ProductRow {...p} query="sort=latest" />,
  promotions: Promotions,
  custom_cake: CustomCake,
  about: About,
  testimonials: Testimonials,
  social_gallery: SocialGallery,
  newsletter: Newsletter,
  contact: ContactBlock,
};
