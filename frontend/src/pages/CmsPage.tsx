import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorBox, NotFound, Spinner } from "@/components/states";
import { PageBanner } from "@/components/PageBanner";
import { buttonClass } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { useCmsPage, useHomepage, useSettings } from "@/lib/queries";
import { useSeo } from "@/lib/theme";

const ico = (d: ReactNode) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6" aria-hidden="true">{d}</svg>
);
const VALUES = [
  { t: "Baked fresh", d: "Every cake is made to order - never frozen, never rushed.", i: ico(<><path d="M4 17h16M6 17c0-5 2-8 6-8s6 3 6 8" /><path d="M12 9V6" /></>) },
  { t: "Quality ingredients", d: "Real butter, fresh cream and quality chocolate in every bite.", i: ico(<path d="M12 21s-7-4.5-7-11a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 6.5-7 11-7 11Z" />) },
  { t: "Made for you", d: "Custom designs and flavours for birthdays, weddings and every occasion.", i: ico(<path d="M12 3l2.5 5.5L20 9l-4 4 1 6-5-3-5 3 1-6-4-4 5.5-.5L12 3Z" />) },
  { t: "On time, every time", d: "Choose your delivery or pickup slot and we'll be there.", i: ico(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>) },
];

export default function CmsPage() {
  const { slug = "" } = useParams();
  const { data, isLoading, error } = useCmsPage(slug);
  const home = useHomepage().data;
  const g = useSettings().data?.general;
  useSeo(data?.meta_title || data?.title, data?.meta_description);
  if (isLoading) return <Spinner />;
  if (error instanceof ApiError && error.status === 404) return <NotFound />;
  if (error || !data) return <div className="mx-auto max-w-xl px-4 py-16"><ErrorBox /></div>;

  const isAbout = slug === "about";
  const aboutImg: string | undefined = home?.sections.find((s) => s.key === "about")?.content.image_url ?? undefined;

  if (!isAbout) {
    return (
      <div>
        <PageBanner title={data.title} />
        <article className="mx-auto max-w-3xl px-4 py-12">
          {/* body_html is allowlist-sanitised by the API on save (services/sanitize.py) */}
          <div className="cms-body rounded-3xl bg-surface p-6 shadow-card md:p-10" dangerouslySetInnerHTML={{ __html: data.body_html }} />
        </article>
      </div>
    );
  }

  return (
    <div>
      <PageBanner eyebrow="Our story" title={data.title}>{g?.tagline}</PageBanner>

      <section className="mx-auto max-w-6xl px-4 py-14 md:py-20">
        <div className={`grid items-center gap-10 md:gap-16 ${aboutImg ? "md:grid-cols-2" : ""}`}>
          {aboutImg && (
            <div className="relative">
              <div className="absolute -bottom-4 -right-4 h-full w-full rounded-3xl bg-secondary/60" aria-hidden="true" />
              <img src={aboutImg} alt="" className="relative aspect-[4/3] w-full rounded-3xl object-cover shadow-card" />
            </div>
          )}
          {/* body_html is allowlist-sanitised by the API on save (services/sanitize.py) */}
          <div className={`cms-body text-lg text-ink/80 [&>h2:first-child]:mt-0 ${aboutImg ? "" : "mx-auto max-w-3xl"}`} dangerouslySetInnerHTML={{ __html: data.body_html }} />
        </div>
      </section>

      <section className="bg-secondary/30 py-14 md:py-20">
        <div className="mx-auto max-w-6xl px-4">
          <div className="mb-10 text-center">
            <p className="text-sm font-medium uppercase tracking-widest text-primary">What we stand for</p>
            <h2 className="mt-1 text-3xl md:text-4xl">Baked with care</h2>
          </div>
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {VALUES.map((v) => (
              <li key={v.t} className="rounded-3xl bg-surface p-6 text-center shadow-card">
                <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary/60 text-primary">{v.i}</span>
                <h3 className="mt-4 text-lg">{v.t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink/70">{v.d}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="px-4 py-14 md:py-20">
        <div className="relative mx-auto max-w-5xl overflow-hidden rounded-[2rem] bg-primary px-6 py-12 text-center text-white shadow-card md:px-16 md:py-16">
          <div className="pointer-events-none absolute -left-16 -top-16 h-56 w-56 rounded-full bg-white/10" aria-hidden="true" />
          <div className="pointer-events-none absolute -bottom-20 -right-10 h-64 w-64 rounded-full bg-white/10" aria-hidden="true" />
          <h2 className="relative text-3xl text-white md:text-4xl">Ready to order your cake?</h2>
          <p className="relative mx-auto mt-3 max-w-lg text-white/80">Browse our cakes or tell us about your dream design - we'd love to bake it for you.</p>
          <div className="relative mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/shop" className={buttonClass("secondary", "px-8 py-3.5 text-base")}>Shop cakes</Link>
            <Link to="/contact" className="inline-flex items-center justify-center rounded-full border border-white/50 px-8 py-3.5 text-base font-medium text-white transition hover:bg-white/10">Contact us</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
