import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { aapi, adel, apost, aput } from "./api";
import { useStaff } from "./auth";
import { btn, Card, Col, ErrLine, Failed, Field, ImageField, inputCls, Loading, Modal, PageHeader, Table, useAction } from "./kit";

export type Opt = { value: string | number; label: string };
export type F = {
  key: string; label: string; hint?: string; required?: boolean; default?: unknown;
  type: "text" | "textarea" | "int" | "decimal" | "checkbox" | "select" | "date" | "time" | "datetime" | "image" | "weekdays" | "multi";
  options?: Opt[]; step?: string; show?: (f: Record<string, any>) => boolean; readOnlyOnEdit?: boolean; span2?: boolean;
};
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const toLocalDT = (iso?: string | null) => (iso ? new Date(new Date(iso).getTime() - new Date(iso).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "");

/** Form state -> request body: blank optional fields become null, numbers are numbers, datetimes become ISO. */
export function toBody(fields: F[], f: Record<string, any>) {
  const out: Record<string, any> = {};
  for (const x of fields) {
    if (x.show && !x.show(f)) continue;
    let v = f[x.key];
    if (x.type === "int") v = v === "" || v == null ? (x.required ? 0 : null) : Number(v);
    else if (x.type === "decimal") v = v === "" || v == null ? (x.required ? "0" : null) : String(v);
    else if (x.type === "datetime") v = v ? new Date(v).toISOString() : null;
    else if (x.type === "select" && x.options?.length && typeof x.options[0].value === "number") v = v === "" || v == null ? null : Number(v);
    else if (x.type === "text" || x.type === "textarea" || x.type === "date" || x.type === "time") v = v === "" || v == null ? (x.required || x.type === "textarea" ? "" : null) : v;
    else if (x.type === "select") v = v === "" ? null : v;
    out[x.key] = v;
  }
  return out;
}
export function initial(fields: F[], row?: Record<string, any>) {
  const f: Record<string, any> = {};
  for (const x of fields) {
    const v = row ? row[x.key] : x.default;
    f[x.key] = x.type === "checkbox" ? !!(v ?? x.default ?? false)
      : x.type === "weekdays" ? (v ?? x.default ?? [0, 1, 2, 3, 4, 5, 6])
      : x.type === "multi" ? (v ?? [])
      : x.type === "datetime" ? toLocalDT(v)
      : x.type === "time" ? String(v ?? "").slice(0, 5)
      : v ?? (x.type === "image" ? null : "");
  }
  return f;
}

export function FieldInput({ x, f, set, editing }: { x: F; f: Record<string, any>; set: (k: string, v: any) => void; editing: boolean }) {
  const v = f[x.key]; const dis = editing && x.readOnlyOnEdit;
  let input: ReactNode;
  switch (x.type) {
    case "textarea": input = <textarea className={inputCls} rows={4} value={v} required={x.required} onChange={(e) => set(x.key, e.target.value)} />; break;
    case "checkbox": return <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!v} onChange={(e) => set(x.key, e.target.checked)} /> {x.label}{x.hint && <span className="text-xs text-ink/60">— {x.hint}</span>}</label>;
    case "select": input = <select className={inputCls} value={v ?? ""} required={x.required} disabled={dis} onChange={(e) => set(x.key, e.target.value)}>{!x.required && <option value="">—</option>}{x.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>; break;
    case "image": input = <ImageField value={v} onChange={(u) => set(x.key, u)} />; break;
    case "weekdays": input = <div className="flex flex-wrap gap-2">{DAYS.map((d, i) => <label key={d} className="flex items-center gap-1 text-sm"><input type="checkbox" checked={(v as number[]).includes(i)} onChange={(e) => set(x.key, e.target.checked ? [...v, i].sort() : v.filter((n: number) => n !== i))} />{d}</label>)}</div>; break;
    case "multi": input = <div className="flex max-h-36 flex-wrap gap-x-4 gap-y-1 overflow-y-auto rounded-lg border border-primary/10 p-2">{x.options?.map((o) => <label key={o.value} className="flex items-center gap-1 text-sm"><input type="checkbox" checked={(v as number[]).includes(Number(o.value))} onChange={(e) => set(x.key, e.target.checked ? [...v, Number(o.value)] : v.filter((n: number) => n !== Number(o.value)))} />{o.label}</label>)}</div>; break;
    default: input = <input className={inputCls} value={v ?? ""} required={x.required} disabled={dis} step={x.step ?? (x.type === "decimal" ? "0.01" : x.type === "int" ? "1" : undefined)}
      type={x.type === "int" || x.type === "decimal" ? "number" : x.type === "datetime" ? "datetime-local" : x.type} onChange={(e) => set(x.key, e.target.value)} />;
  }
  return <Field label={x.label + (x.required ? " *" : "")} hint={x.hint}>{input}</Field>;
}

export function FormModal({ title, fields, row, onSave, onClose, pending, error, toBodyFn }: {
  title: string; fields: F[]; row?: Record<string, any>; onSave: (body: any) => void; onClose: () => void; pending: boolean; error: unknown; toBodyFn?: (f: Record<string, any>) => any;
}) {
  const [f, setF] = useState(() => initial(fields, row));
  const set = (k: string, v: any) => setF((p) => ({ ...p, [k]: v }));
  return (
    <Modal title={title} onClose={onClose} wide={fields.length > 6}>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); onSave(toBodyFn ? toBodyFn(f) : toBody(fields, f)); }}>
        {fields.filter((x) => !x.show || x.show(f)).map((x) => <div key={x.key} className={x.span2 || ["textarea", "image", "weekdays", "multi"].includes(x.type) ? "sm:col-span-2" : ""}><FieldInput x={x} f={f} set={set} editing={!!row} /></div>)}
        <div className="flex items-center gap-3 sm:col-span-2"><button className={btn()} disabled={pending}>{pending ? "Saving…" : "Save"}</button><button type="button" className={btn("ghost")} onClick={onClose}>Cancel</button><ErrLine error={error} /></div>
      </form>
    </Modal>
  );
}

/** Generic list + create/edit/delete (+ reorder) screen used by every simple admin entity. */
export function CrudPage<T extends { id: number }>({ title, path, fields, columns, write, canCreate = true, canEdit = true, canDelete = true, reorder, note, rowActions, createLabel = "Add" }: {
  title: string; path: string; fields: F[]; columns: Col<T>[]; write: string; canCreate?: boolean; canEdit?: boolean; canDelete?: boolean; reorder?: boolean; note?: ReactNode;
  rowActions?: (r: T) => ReactNode; createLabel?: string;
}) {
  const { can } = useStaff();
  const key = [path];
  const q = useQuery({ queryKey: key, queryFn: () => aapi<T[]>(path) });
  const [edit, setEdit] = useState<T | "new" | null>(null);
  const save = useAction((b: any) => (edit === "new" ? apost(path, b) : aput(`${path}/${(edit as T).id}`, b)), [key], () => setEdit(null));
  const del = useAction((id: number) => adel(`${path}/${id}`), [key]);
  const move = useAction((ids: number[]) => aput(`${path}/reorder`, { ids }), [key]);
  const writable = can(write);
  const rows = q.data ?? [];
  const swap = (i: number, d: number) => { const ids = rows.map((r) => r.id); [ids[i], ids[i + d]] = [ids[i + d], ids[i]]; move.mutate(ids); };
  const cols: Col<T>[] = [...columns, ...(writable ? [{ header: "", className: "text-right whitespace-nowrap", cell: (r: T) => (
    <span className="space-x-3" onClick={(e) => e.stopPropagation()}>
      {reorder && <><button aria-label="Move up" disabled={rows[0] === r} className="text-primary disabled:opacity-30" onClick={() => swap(rows.indexOf(r), -1)}>↑</button><button aria-label="Move down" disabled={rows[rows.length - 1] === r} className="text-primary disabled:opacity-30" onClick={() => swap(rows.indexOf(r), 1)}>↓</button></>}
      {rowActions?.(r)}
      {canEdit && <button className="text-primary underline" onClick={() => setEdit(r)}>Edit</button>}
      {canDelete && <button className="text-red-700 underline" onClick={() => { if (confirm("Delete this item? This cannot be undone.")) del.mutate(r.id); }}>Delete</button>}
    </span>) }] : [])];
  return (
    <>
      <PageHeader title={title}>{writable && canCreate && <button className={btn()} onClick={() => setEdit("new")}>{createLabel}</button>}</PageHeader>
      {note && <p className="mb-4 text-sm text-ink/70">{note}</p>}
      <Card>
        {q.isLoading ? <Loading /> : q.isError ? <Failed error={q.error} /> : <Table rows={rows} cols={cols} />}
        <ErrLine error={del.error ?? move.error} />
      </Card>
      {edit && <FormModal title={edit === "new" ? `${createLabel} ${title.toLowerCase()}` : `Edit ${title.toLowerCase()}`} fields={fields} row={edit === "new" ? undefined : (edit as any)}
        onSave={(b) => save.mutate(b)} onClose={() => setEdit(null)} pending={save.isPending} error={save.error} />}
    </>
  );
}
