import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, post } from "@/lib/api";
import { money } from "@/lib/format";
import { useSeo } from "@/lib/theme";

interface View {
  reference: string; status: string; occasion: string; flavour: string; size_or_weight: string; required_date: string;
  quoted_price: string | null; currency: string; quote_note: string; quote_valid_until: string | null;
}
const LABEL: Record<string, string> = {
  new: "Waiting for our quote", quoted: "Quote ready", approved: "Quote approved — we'll be in touch to arrange your order",
  declined: "Declined", expired: "Quote expired", converted: "Converted to an order",
};

export default function CustomCakeStatus() {
  useSeo("Custom cake status");
  const [sp] = useSearchParams();
  const [ref, setRef] = useState(sp.get("ref") ?? "");
  const [phone, setPhone] = useState("");
  const look = useMutation({ mutationFn: () => api<View>(`/custom-cakes/status?reference=${encodeURIComponent(ref.trim())}&phone=${encodeURIComponent(phone.trim())}`) });
  const respond = useMutation({ mutationFn: (accept: boolean) => post<View>("/custom-cakes/respond", { reference: ref.trim(), phone: phone.trim(), accept }), onSuccess: (v) => { look.reset(); setOverride(v); } });
  const [override, setOverride] = useState<View | null>(null);
  const v = override ?? look.data;

  return (
    <div className="mx-auto max-w-xl px-4 py-12">
      <h1 className="mb-6 text-4xl">Custom cake request</h1>
      <form className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]" onSubmit={(e) => { e.preventDefault(); setOverride(null); look.mutate(); }}>
        <Input placeholder="Reference (CC-…)" aria-label="Reference" value={ref} onChange={(e) => setRef(e.target.value)} required />
        <Input placeholder="Phone number" aria-label="Phone number" value={phone} onChange={(e) => setPhone(e.target.value)} required />
        <Button type="submit" disabled={look.isPending}>{look.isPending ? "Searching…" : "Check"}</Button>
      </form>
      {look.isError && !v && <p role="alert" className="mt-4 text-sm text-red-700">{(look.error as Error).message}</p>}
      {v && (
        <div className="mt-8 space-y-4 rounded-3xl bg-surface p-6 shadow-card">
          <div>
            <p className="text-sm text-ink/60">{v.reference} · {v.occasion} · {v.size_or_weight} · {v.flavour}</p>
            <p className="font-heading text-2xl text-primary">{LABEL[v.status] ?? v.status}</p>
            <p className="text-sm">Needed by {v.required_date}</p>
          </div>
          {v.quoted_price && (
            <div className="rounded-2xl bg-secondary/30 p-4">
              <p className="text-sm">Our quote</p>
              <p className="font-heading text-3xl text-primary">{money(v.quoted_price, v.currency)}</p>
              {v.quote_valid_until && <p className="text-xs text-ink/60">Valid until {v.quote_valid_until}</p>}
              {v.quote_note && <p className="mt-2 whitespace-pre-line text-sm">{v.quote_note}</p>}
            </div>
          )}
          {v.status === "quoted" && (
            <div className="flex gap-3">
              <Button disabled={respond.isPending} onClick={() => respond.mutate(true)}>Approve quote</Button>
              <Button variant="ghost" disabled={respond.isPending} onClick={() => respond.mutate(false)}>Decline</Button>
            </div>
          )}
          {respond.isError && <p role="alert" className="text-sm text-red-700">{(respond.error as Error).message}</p>}
        </div>
      )}
    </div>
  );
}
