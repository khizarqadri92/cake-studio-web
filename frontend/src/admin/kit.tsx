import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { uploadImage } from "./api";

export const inputCls = "w-full rounded-xl border border-primary/20 bg-white px-3 py-2 text-sm placeholder:text-ink/40 transition focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20";
export const btn = (v: "primary" | "ghost" | "danger" = "primary") =>
  `inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${v === "primary" ? "bg-primary text-white shadow-sm hover:opacity-90" : v === "danger" ? "bg-red-700 text-white hover:opacity-90" : "border border-primary/30 text-primary hover:bg-primary/5"}`;

export const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong");

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="mb-6 flex flex-wrap items-center justify-between gap-3"><h1 className="font-heading text-3xl text-ink">{title}</h1><div className="flex flex-wrap gap-2">{children}</div></div>;
}
export const Card = ({ children, className = "" }: { children: ReactNode; className?: string }) => <section className={`rounded-2xl border border-primary/5 bg-white p-5 shadow-card md:p-6 ${className}`}>{children}</section>;
export const Loading = () => <p className="py-8 text-center text-sm text-ink/60" role="status">Loading…</p>;
export const Failed = ({ error }: { error: unknown }) => <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{errMsg(error)}</p>;

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="block text-sm"><span className="mb-1 block font-medium">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-ink/60">{hint}</span>}</label>;
}
export const Badge = ({ children, tone = "gray" }: { children: ReactNode; tone?: "gray" | "green" | "amber" | "red" | "blue" }) => (
  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${{ gray: "bg-gray-100 text-gray-700", green: "bg-green-100 text-green-800", amber: "bg-amber-100 text-amber-800", red: "bg-red-100 text-red-800", blue: "bg-blue-100 text-blue-800" }[tone]}`}>{children}</span>
);
export const statusTone = (s: string): "gray" | "green" | "amber" | "red" | "blue" =>
  ({ delivered: "green", paid: "green", confirmed: "blue", in_preparation: "blue", out_for_delivery: "blue", ready_for_pickup: "blue", approved: "green", converted: "green", cancelled: "red", refunded: "red", declined: "red", pending_confirmation: "amber", unpaid: "amber", partially_paid: "amber", quoted: "amber", pending: "amber" } as const)[s] ?? "gray";
export const label = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => { const h = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h); }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={`mt-10 w-full ${wide ? "max-w-3xl" : "max-w-lg"} rounded-2xl bg-white p-6 shadow-2xl`}>
        <div className="mb-4 flex items-center justify-between"><h2 className="font-heading text-2xl text-ink">{title}</h2><button aria-label="Close" onClick={onClose} className="text-2xl leading-none text-ink/50">×</button></div>
        {children}
      </div>
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-ink/70">
      <span>{total} total</span>
      <div className="flex items-center gap-2"><button className={btn("ghost")} disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button><span>Page {page} of {pages}</span><button className={btn("ghost")} disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button></div>
    </div>
  );
}

export type Col<T> = { header: string; cell: (r: T) => ReactNode; className?: string };
export function Table<T = any>({ rows, cols, onRow, empty = "Nothing here yet." }: { rows: T[]; cols: Col<T>[]; onRow?: (r: T) => void; empty?: string }) {
  if (rows.length === 0) return <p className="py-8 text-center text-sm text-ink/60">{empty}</p>;
  return (
    <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead><tr className="border-b border-primary/10 bg-cream/60 text-xs uppercase tracking-wide text-ink/60">{cols.map((c) => <th key={c.header} className={`px-3 py-3 font-medium first:rounded-l-xl last:rounded-r-xl ${c.className ?? ""}`}>{c.header}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={(r as any)?.id ?? i} className={`border-b border-primary/5 transition last:border-0 ${onRow ? "cursor-pointer hover:bg-cream" : "hover:bg-cream/50"}`} onClick={() => onRow?.(r)}>
          {cols.map((c) => <td key={c.header} className={`px-3 py-3 align-top ${c.className ?? ""}`}>{c.cell(r)}</td>)}
        </tr>
      ))}</tbody>
    </table></div>
  );
}

export function ImageField({ value, onChange }: { value: string | null | undefined; onChange: (url: string | null) => void }) {
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  return (
    <div className="flex items-center gap-3">
      {value ? <img src={value} alt="" className="h-16 w-16 rounded-lg object-cover" /> : <div className="h-16 w-16 rounded-lg bg-cream" />}
      <div className="space-y-1">
        <input type="file" accept="image/png,image/jpeg,image/webp" aria-label="Upload image" className="text-xs" disabled={busy}
          onChange={async (e) => { const f = e.target.files?.[0]; if (!f) return; setBusy(true); setErr(""); try { onChange(await uploadImage(f)); } catch (x) { setErr(errMsg(x)); } finally { setBusy(false); e.target.value = ""; } }} />
        {value && <button type="button" className="text-xs text-red-700 underline" onClick={() => onChange(null)}>Remove</button>}
        {err && <p role="alert" className="text-xs text-red-700">{err}</p>}
      </div>
    </div>
  );
}

/** Mutation helper that invalidates query keys and surfaces the server's error message. */
export function useAction<V = void, R = unknown>(fn: (v: V) => Promise<R>, invalidate: unknown[][], onDone?: (r: R) => void) {
  const qc = useQueryClient();
  const m = useMutation({ mutationFn: fn, onSuccess: async (r) => { await Promise.all(invalidate.map((k) => qc.invalidateQueries({ queryKey: k }))); onDone?.(r); } });
  return m;
}
export const ErrLine = ({ error }: { error: unknown }) => (error ? <p role="alert" className="text-sm text-red-700">{errMsg(error)}</p> : null);
export const today = () => new Date().toISOString().slice(0, 10);
