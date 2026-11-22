import type { ReactNode } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { post } from "@/lib/api";
import { mapEmbedUrl } from "@/lib/format";
import { useSettings } from "@/lib/queries";
import { useSeo } from "@/lib/theme";

const schema = z.object({
  name: z.string().trim().min(1, "Please enter your name").max(120),
  email: z.string().email("Enter a valid email"),
  phone: z.string().max(40).optional(),
  message: z.string().trim().min(5, "Please write a few words").max(3000),
});
type Form = z.infer<typeof schema>;

const ico = (d: ReactNode) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5" aria-hidden="true">{d}</svg>
);
const ICONS = {
  pin: ico(<><path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21Z" /><circle cx="12" cy="9.5" r="2.5" /></>),
  phone: ico(<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z" />),
  mail: ico(<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>),
  chat: ico(<path d="M21 12a8 8 0 0 1-11.7 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z" />),
  clock: ico(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>),
};

function InfoCard({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-4 rounded-3xl bg-surface p-5 shadow-card">
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-secondary/60 text-primary">{icon}</span>
      <div className="min-w-0">
        <p className="text-sm font-medium text-ink/60">{title}</p>
        <div className="mt-0.5 break-words font-medium">{children}</div>
      </div>
    </div>
  );
}

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function Contact() {
  const { data: s } = useSettings();
  useSeo("Contact us", "Get in touch with us - questions, orders and custom cake enquiries.");
  const { register, handleSubmit, reset, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema) });
  const m = useMutation({ mutationFn: (v: Form) => post("/public/contact", { ...v, phone: v.phone || null }), onSuccess: () => reset() });
  const g = s?.general;
  const err = (k: keyof Form) => errors[k] && <p role="alert" className="mt-1 text-xs text-red-700">{errors[k]?.message}</p>;
  const wa = g?.whatsapp ? `https://wa.me/${g.whatsapp.replace(/\D/g, "")}` : undefined;
  const custom = mapEmbedUrl(g?.google_maps_embed_url);
  // Admin-pasted embed code wins; otherwise build one from the address so the map always shows.
  const map = custom ??
    (g?.address ? `https://www.google.com/maps?q=${encodeURIComponent(g.address)}&output=embed` : undefined);
  const today = DAYS[new Date().getDay()];
  const hours = g?.business_hours ?? [];

  return (
    <div>
      <section className="bg-secondary/40">
        <div className="mx-auto max-w-6xl px-4 py-14 text-center md:py-20">
          <p className="text-sm font-medium uppercase tracking-widest text-primary">Contact</p>
          <h1 className="mt-2 text-4xl md:text-5xl">We'd love to hear from you</h1>
          <p className="mx-auto mt-4 max-w-xl text-ink/70">Questions about an order, a custom cake or a special occasion? Send us a message and we'll reply as soon as we can.</p>
        </div>
      </section>

      <div className="mx-auto -mt-8 max-w-6xl px-4 pb-16 md:-mt-10">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {g?.address && <InfoCard icon={ICONS.pin} title="Visit us">{g.address}</InfoCard>}
          {g?.phone && <InfoCard icon={ICONS.phone} title="Call us"><a href={`tel:${g.phone}`} className="hover:text-primary">{g.phone}</a></InfoCard>}
          {g?.email && <InfoCard icon={ICONS.mail} title="Email us"><a href={`mailto:${g.email}`} className="hover:text-primary">{g.email}</a></InfoCard>}
          {wa && <InfoCard icon={ICONS.chat} title="WhatsApp"><a href={wa} target="_blank" rel="noopener noreferrer" className="hover:text-primary">Chat with us</a></InfoCard>}
        </div>

        <div className="mt-10 grid gap-8 lg:grid-cols-5">
          <form onSubmit={handleSubmit((v) => m.mutate(v))} noValidate className="space-y-4 rounded-3xl bg-surface p-6 shadow-card md:p-8 lg:col-span-3">
            <h2 className="text-2xl">Send us a message</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div><Input placeholder="Your name" aria-label="Name" autoComplete="name" {...register("name")} />{err("name")}</div>
              <div><Input type="email" placeholder="Email address" aria-label="Email" autoComplete="email" {...register("email")} />{err("email")}</div>
            </div>
            <div><Input placeholder="Phone (optional)" aria-label="Phone" autoComplete="tel" {...register("phone")} />{err("phone")}</div>
            <div><Textarea rows={6} placeholder="How can we help?" aria-label="Message" {...register("message")} />{err("message")}</div>
            <Button type="submit" disabled={m.isPending} className="w-full sm:w-auto">{m.isPending ? "Sending…" : "Send message"}</Button>
            {m.isSuccess && <p role="status" className="rounded-2xl bg-secondary/50 px-4 py-3 text-sm text-primary">Thank you! Your message is on its way - we'll get back to you soon.</p>}
            {m.isError && <p role="alert" className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">Couldn't send your message. Please try again.</p>}
          </form>

          <aside className="space-y-6 lg:col-span-2">
            {hours.length > 0 && (
              <div className="rounded-3xl bg-surface p-6 shadow-card">
                <div className="mb-4 flex items-center gap-3">
                  <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-secondary/60 text-primary">{ICONS.clock}</span>
                  <h2 className="text-xl">Opening hours</h2>
                </div>
                <ul className="divide-y divide-secondary/60 text-sm">
                  {hours.map((h) => {
                    const now = h.day.slice(0, 3).toLowerCase() === today.toLowerCase();
                    return (
                      <li key={h.day} className={`flex justify-between py-2 ${now ? "font-semibold text-primary" : ""}`}>
                        <span>{h.day}{now && <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs">Today</span>}</span>
                        <span>{h.closed ? "Closed" : `${h.open ?? ""} – ${h.close ?? ""}`}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </aside>
        </div>

        {map && (
          <section className="mt-12" aria-label="Find us on the map">
            <h2 className="mb-4 text-2xl">Find us</h2>
            <div className="overflow-hidden rounded-3xl bg-surface shadow-card">
              <iframe title="Map" src={map} loading="lazy" className="h-80 w-full border-0 md:h-[26rem]" referrerPolicy="no-referrer-when-downgrade" allowFullScreen />
              {g?.address && (
                <div className="flex flex-col items-start justify-between gap-3 p-4 sm:flex-row sm:items-center">
                  <p className="text-sm">{g.address}</p>
                  <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(g.address)}`} target="_blank" rel="noopener noreferrer"
                    className="rounded-full bg-primary px-5 py-2 text-sm font-medium text-white transition hover:opacity-90">Get directions</a>
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
