import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";

type Data = { count: number; average: number | null; distribution: Record<string, number>; items: { id: number; name: string; rating: number; comment: string; at: string | null }[] };
const Stars = ({ n }: { n: number }) => <span aria-label={`${n} out of 5 stars`} className="text-amber-500">{"★".repeat(Math.round(n))}<span className="text-ink/20">{"★".repeat(5 - Math.round(n))}</span></span>;

export function Reviews({ slug, productId }: { slug: string; productId: number }) {
  const qc = useQueryClient();
  const { me } = useAuth();
  const q = useQuery({ queryKey: ["reviews", slug], queryFn: () => api<Data>(`/public/products/${encodeURIComponent(slug)}/reviews`) });
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ order_number: "", phone: "", rating: 5, comment: "" });
  const send = useMutation({
    mutationFn: () => post<{ message: string }>("/reviews", { product_id: productId, order_number: f.order_number, phone: me ? f.phone || null : f.phone, rating: f.rating, comment: f.comment }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["reviews", slug] }),
  });
  const d = q.data;
  const submit = (e: FormEvent) => { e.preventDefault(); send.mutate(); };
  return (
    <section aria-labelledby="reviews-h" className="mx-auto mt-16 max-w-3xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="reviews-h" className="font-heading text-2xl text-primary">Customer reviews</h2>
        {d && d.count > 0 && <p className="text-sm"><Stars n={d.average ?? 0} /> <b>{d.average}</b> from {d.count} review{d.count === 1 ? "" : "s"}</p>}
      </div>
      {q.isLoading ? <p className="mt-4 text-sm text-ink/60">Loading reviews…</p> : d && d.count === 0 ? <p className="mt-4 text-sm text-ink/60">No reviews yet.</p> : (
        <ul className="mt-4 divide-y divide-primary/10">
          {d?.items.map((r) => <li key={r.id} className="py-4"><div className="flex items-center gap-2 text-sm"><Stars n={r.rating} /><b>{r.name}</b><span className="text-ink/50">{r.at}</span></div>{r.comment && <p className="mt-1 text-sm">{r.comment}</p>}</li>)}
        </ul>
      )}
      <div className="mt-6">
        {!open ? <Button variant="ghost" onClick={() => setOpen(true)}>Write a review</Button> : send.isSuccess ? (
          <p role="status" className="rounded-xl bg-secondary/40 p-4 text-sm">{send.data.message}</p>
        ) : (
          <form onSubmit={submit} className="space-y-3 rounded-2xl bg-surface p-5 shadow-card">
            <p className="text-sm text-ink/70">Reviews are for delivered orders. Enter your order number{me ? "" : " and the phone number you ordered with"}.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input required placeholder="Order number (CS-…)" aria-label="Order number" value={f.order_number} onChange={(e) => setF({ ...f, order_number: e.target.value })} />
              {!me && <Input required type="tel" placeholder="Phone number" aria-label="Phone number" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />}
            </div>
            <fieldset><legend className="mb-1 text-sm font-medium">Your rating</legend>
              <div className="flex gap-3">{[1, 2, 3, 4, 5].map((n) => <label key={n} className="flex items-center gap-1 text-sm"><input type="radio" name="rating" checked={f.rating === n} onChange={() => setF({ ...f, rating: n })} />{n}★</label>)}</div></fieldset>
            <Textarea rows={3} maxLength={1500} placeholder="Tell others about the cake (optional)" aria-label="Review" value={f.comment} onChange={(e) => setF({ ...f, comment: e.target.value })} />
            {send.isError && <p role="alert" className="text-sm text-red-700">{send.error instanceof ApiError ? send.error.message : "Something went wrong"}</p>}
            <div className="flex gap-3"><Button type="submit" disabled={send.isPending}>{send.isPending ? "Sending…" : "Submit review"}</Button><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button></div>
          </form>
        )}
      </div>
    </section>
  );
}
