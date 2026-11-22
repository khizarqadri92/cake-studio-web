import { resizeImage } from "../lib/resizeImage";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { PageBanner } from "@/components/PageBanner";
import { Button, buttonClass } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { post } from "@/lib/api";
import { useSeo } from "@/lib/theme";

const schema = z.object({
  occasion: z.string().trim().min(1, "Tell us the occasion"),
  flavour: z.string().trim().min(1, "Choose or describe a flavour"),
  size_or_weight: z.string().trim().min(1, "Tell us the size or weight"),
  design_notes: z.string().max(2000).optional(),
  message: z.string().max(200).optional(),
  required_date: z.string().min(1, "Choose a date"),
  required_time: z.string().optional(),
  full_name: z.string().trim().min(1, "Please enter your name"),
  phone: z.string().trim().regex(/^\+?[\d\s\-().]{7,20}$/, "Enter a valid phone number"),
  email: z.string().email("Enter a valid email").or(z.literal("")),
  instructions: z.string().max(2000).optional(),
});
type Form = z.infer<typeof schema>;

async function uploadImage(file: File): Promise<string> {
  const fd = new FormData();
  fd.append("file", await resizeImage(file));
  const res = await fetch("/api/v1/public/uploads/image", { method: "POST", body: fd }); // browser sets the multipart boundary
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(res.status === 413 ? "Image is too large" : typeof body.detail === "string" ? body.detail : "Upload failed");
  return body.url as string;
}

export default function CustomCake() {
  useSeo("Custom cake request", "Tell us about your dream cake and we'll send you a quote.");
  const [images, setImages] = useState<string[]>([]);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const { register, handleSubmit, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema) });
  const minDate = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);

  const submit = useMutation({
    mutationFn: (v: Form) => post<{ reference: string }>("/custom-cakes", {
      ...v, email: v.email || null, required_time: v.required_time || null, message: v.message || null,
      design_notes: v.design_notes ?? "", instructions: v.instructions ?? "", reference_images: images,
    }),
  });

  const onFiles = async (files: FileList | null) => {
    if (!files) return;
    setUploadErr(null); setUploading(true);
    try {
      for (const f of Array.from(files)) {
        if (images.length >= 3) { setUploadErr("You can add up to 3 images."); break; }
        const url = await uploadImage(f);
        setImages((cur) => (cur.length < 3 ? [...cur, url] : cur));
      }
    } catch (e) { setUploadErr(e instanceof Error ? e.message : "Upload failed"); }
    finally { setUploading(false); }
  };

  if (submit.isSuccess) return (
    <div className="mx-auto max-w-xl px-4 py-20 text-center">
      <div className="rounded-3xl bg-surface p-8 shadow-card md:p-12">
      <h1 className="text-4xl">Request received 🎂</h1>
      <p className="mt-3 text-ink/70">We'll review your idea and send you a quote. Keep your reference number:</p>
      <p className="mt-4 font-heading text-3xl text-primary">{submit.data.reference}</p>
      <Link to={`/custom-cake/status?ref=${encodeURIComponent(submit.data.reference)}`} className={buttonClass("primary", "mt-8")}>Check request status</Link>
      </div>
    </div>
  );

  const err = (k: keyof Form) => errors[k] && <p role="alert" className="mt-1 text-xs text-red-700">{errors[k]?.message as string}</p>;
  const h = "mb-4 flex items-center gap-3 font-heading text-xl";
  const card = "rounded-3xl bg-surface p-5 shadow-card md:p-6";
  const num = (n: number) => <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-white">{n}</span>;
  return (
    <div>
      <PageBanner eyebrow="Made just for you" title="Request a custom cake">Describe your idea and we'll come back with a price. No payment is needed to request a quote.</PageBanner>
      <div className="mx-auto max-w-3xl px-4 py-10">
      <form onSubmit={handleSubmit((v) => submit.mutate(v))} noValidate className="space-y-6">
        <section className={card}>
          <h2 className={h}>{num(1)}Your cake</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div><Input placeholder="Occasion (birthday, wedding…)" aria-label="Occasion" {...register("occasion")} />{err("occasion")}</div>
            <div><Input placeholder="Flavour" aria-label="Flavour" {...register("flavour")} />{err("flavour")}</div>
            <div className="sm:col-span-2"><Input placeholder="Size or weight (e.g. 2 kg, 8 inch, serves 20)" aria-label="Size or weight" {...register("size_or_weight")} />{err("size_or_weight")}</div>
            <div className="sm:col-span-2"><Textarea rows={3} placeholder="Preferred design, colours, theme…" aria-label="Preferred design" {...register("design_notes")} />{err("design_notes")}</div>
            <div className="sm:col-span-2"><Input placeholder="Message on the cake (optional)" aria-label="Message on cake" maxLength={200} {...register("message")} /></div>
          </div>
        </section>

        <section className={card}>
          <h2 className={h}>{num(2)}Reference images <span className="text-sm font-normal text-ink/60">(up to 3)</span></h2>
          <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" multiple disabled={uploading || images.length >= 3}
            onChange={(e) => { void onFiles(e.target.files); e.target.value = ""; }} aria-label="Upload reference images" className="block w-full cursor-pointer rounded-2xl border-2 border-dashed border-primary/30 bg-cream/50 p-4 text-sm file:mr-3 file:rounded-full file:border-0 file:bg-primary file:px-4 file:py-1.5 file:text-white" />
          {uploading && <p role="status" className="mt-2 text-sm">Uploading…</p>}
          {uploadErr && <p role="alert" className="mt-2 text-sm text-red-700">{uploadErr}</p>}
          {images.length > 0 && (
            <ul className="mt-3 flex gap-3">
              {images.map((u) => (
                <li key={u} className="relative">
                  <img src={u} alt="Reference" className="h-24 w-24 rounded-2xl object-cover" />
                  <button type="button" aria-label="Remove image" onClick={() => setImages((c) => c.filter((x) => x !== u))} className="absolute -right-2 -top-2 h-6 w-6 rounded-full bg-primary text-xs text-white">×</button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={card}>
          <h2 className={h}>{num(3)}When do you need it?</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div><Input type="date" min={minDate} aria-label="Required date" {...register("required_date")} />{err("required_date")}</div>
            <div><Input type="time" aria-label="Preferred time" {...register("required_time")} /></div>
          </div>
        </section>

        <section className={card}>
          <h2 className={h}>{num(4)}Your contact details</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2"><Input placeholder="Full name" aria-label="Full name" autoComplete="name" {...register("full_name")} />{err("full_name")}</div>
            <div><Input placeholder="Phone" aria-label="Phone" autoComplete="tel" {...register("phone")} />{err("phone")}</div>
            <div><Input type="email" placeholder="Email (optional)" aria-label="Email" autoComplete="email" {...register("email")} />{err("email")}</div>
            <div className="sm:col-span-2"><Textarea rows={2} placeholder="Anything else we should know? (allergies, delivery…)" aria-label="Additional instructions" {...register("instructions")} /></div>
          </div>
        </section>

        <Button type="submit" className="w-full py-3.5 text-base" disabled={submit.isPending || uploading}>{submit.isPending ? "Sending…" : "Send request"}</Button>
        {submit.isError && <p role="alert" className="text-sm text-red-700">{(submit.error as Error).message}</p>}
      </form>
      </div>
    </div>
  );
}
