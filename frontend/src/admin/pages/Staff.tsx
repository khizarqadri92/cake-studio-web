import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { aapi, apost, aput } from "../api";
import { useStaff } from "../auth";
import { Badge, btn, Card, ErrLine, Failed, Field, inputCls, label, Loading, Modal, PageHeader, Pager, Table, useAction } from "../kit";

export function Users() {
  const { can, me } = useStaff(); const w = can("users.write");
  const users = useQuery({ queryKey: ["admin", "users"], queryFn: () => aapi<any[]>("/admin/users") });
  const roles = useQuery({ queryKey: ["admin", "roles"], queryFn: () => aapi<any[]>("/admin/roles"), enabled: can("roles.read") });
  const [edit, setEdit] = useState<any | "new" | null>(null); const [pw, setPw] = useState<any | null>(null);
  const [f, setF] = useState({ email: "", full_name: "", password: "", roles: [] as string[], is_active: true }); const [np, setNp] = useState("");
  const open = (u: any | "new") => { setF(u === "new" ? { email: "", full_name: "", password: "", roles: [], is_active: true } : { email: u.email, full_name: u.full_name, password: "", roles: u.roles, is_active: u.is_active }); setEdit(u); };
  const save = useAction(() => (edit === "new" ? apost("/admin/users", { email: f.email, full_name: f.full_name, password: f.password, roles: f.roles }) : aput(`/admin/users/${edit.id}`, { full_name: f.full_name, is_active: f.is_active, roles: f.roles })), [["admin", "users"]], () => setEdit(null));
  const reset = useAction(() => apost(`/admin/users/${pw.id}/password`, { password: np }), [], () => { setPw(null); setNp(""); });
  const roleNames = (roles.data ?? []).map((r) => r.name);
  return (<><PageHeader title="Staff users">{w && <button className={btn()} onClick={() => open("new")}>Add user</button>}</PageHeader>
    <Card>{users.isLoading ? <Loading /> : users.isError ? <Failed error={users.error} /> : <Table rows={users.data!} cols={[
      { header: "Name", cell: (u) => <b>{u.full_name}</b> }, { header: "Email", cell: (u) => u.email }, { header: "Roles", cell: (u) => u.roles.map((r: string) => <Badge key={r} tone="blue">{r}</Badge>) },
      { header: "Last login", cell: (u) => (u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never") }, { header: "Status", cell: (u) => <Badge tone={u.is_active ? "green" : "gray"}>{u.is_active ? "Active" : "Disabled"}</Badge> },
      { header: "", className: "text-right whitespace-nowrap", cell: (u) => w && <span className="space-x-3"><button className="text-primary underline" onClick={() => open(u)}>Edit</button><button className="text-primary underline" onClick={() => setPw(u)}>Set password</button></span> }]} />}</Card>
    {edit && <Modal title={edit === "new" ? "Add staff user" : `Edit ${edit.full_name}`} onClose={() => setEdit(null)}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <Field label="Full name"><input className={inputCls} required value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Email"><input className={inputCls} type="email" required disabled={edit !== "new"} value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        {edit === "new" && <Field label="Initial password" hint="At least 10 characters; share it securely and ask them to keep it private."><input className={inputCls} type="password" autoComplete="new-password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>}
        <fieldset><legend className="mb-1 text-sm font-medium">Roles</legend><div className="flex flex-wrap gap-4">{roleNames.map((r) => <label key={r} className="flex items-center gap-1 text-sm"><input type="checkbox" checked={f.roles.includes(r)} onChange={(e) => setF({ ...f, roles: e.target.checked ? [...f.roles, r] : f.roles.filter((x) => x !== r) })} />{r}</label>)}</div></fieldset>
        {edit !== "new" && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.is_active} disabled={edit.id === me?.id} onChange={(e) => setF({ ...f, is_active: e.target.checked })} />Account active</label>}
        <div className="flex items-center gap-3"><button className={btn()} disabled={save.isPending || f.roles.length === 0}>Save</button><ErrLine error={save.error} /></div></form></Modal>}
    {pw && <Modal title={`Set password for ${pw.full_name}`} onClose={() => setPw(null)}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); reset.mutate(); }}>
        <Field label="New password" hint="Signs them out of all devices."><input className={inputCls} type="password" autoComplete="new-password" required value={np} onChange={(e) => setNp(e.target.value)} /></Field>
        <div className="flex items-center gap-3"><button className={btn()} disabled={reset.isPending}>Update password</button><ErrLine error={reset.error} /></div></form></Modal>}</>);
}

export function Roles() {
  const { can } = useStaff(); const w = can("roles.write");
  const roles = useQuery({ queryKey: ["admin", "roles"], queryFn: () => aapi<any[]>("/admin/roles") });
  const perms = useQuery({ queryKey: ["admin", "permissions"], queryFn: () => aapi<string[]>("/admin/roles/permissions") });
  const [sel, setSel] = useState<number | null>(null); const [draft, setDraft] = useState<string[] | null>(null);
  const role = roles.data?.find((r) => r.id === (sel ?? roles.data[0]?.id));
  const cur: string[] = draft ?? role?.permissions ?? [];
  const save = useAction(() => aput(`/admin/roles/${role.id}/permissions`, { permissions: cur }), [["admin", "roles"]], () => setDraft(null));
  if (roles.isLoading || perms.isLoading) return <Loading />;
  if (roles.isError) return <Failed error={roles.error} />;
  const groups = Object.entries((perms.data ?? []).reduce<Record<string, string[]>>((a, p) => { const [g] = p.split("."); (a[g] ??= []).push(p); return a; }, {})) as [string, string[]][];
  const locked = !w || role?.name === "Super Admin";
  return (<><PageHeader title="Roles & permissions" />
    <div className="grid gap-6 lg:grid-cols-4"><Card><ul className="space-y-1">{roles.data!.map((r) => <li key={r.id}><button className={`w-full rounded-lg px-3 py-2 text-left text-sm ${r.id === role?.id ? "bg-primary text-white" : "hover:bg-primary/5"}`} onClick={() => { setSel(r.id); setDraft(null); }}>{r.name}</button></li>)}</ul></Card>
      <Card className="lg:col-span-3">{role && (<>
        <h2 className="mb-1 font-heading text-lg text-primary">{role.name}</h2>{role.name === "Super Admin" && <p className="mb-3 text-sm text-ink/70">Super Admin has every permission and cannot be edited.</p>}
        <div className="grid gap-4 sm:grid-cols-2">{groups.map(([g, ps]) => <fieldset key={g} disabled={locked}><legend className="mb-1 text-sm font-medium">{label(g)}</legend>{ps.map((p) => <label key={p} className="mr-4 inline-flex items-center gap-1 text-sm"><input type="checkbox" checked={role.name === "Super Admin" || cur.includes(p)} onChange={(e) => setDraft(e.target.checked ? [...cur, p] : cur.filter((x) => x !== p))} />{p.split(".")[1]}</label>)}</fieldset>)}</div>
        {!locked && draft && <div className="mt-4 flex items-center gap-3"><button className={btn()} disabled={save.isPending} onClick={() => save.mutate()}>Save permissions</button><button className={btn("ghost")} onClick={() => setDraft(null)}>Discard</button><ErrLine error={save.error} /></div>}</>)}</Card></div></>);
}

export function AuditLog() {
  const [page, setPage] = useState(1); const [action, setAction] = useState("");
  const q = useQuery({ queryKey: ["admin", "audit", page, action], queryFn: () => aapi<{ total: number; items: any[] }>(`/admin/audit-logs?page=${page}${action ? `&action=${encodeURIComponent(action)}` : ""}`), placeholderData: (p) => p });
  return (<><PageHeader title="Audit log" />
    <Card className="mb-4"><input className={`${inputCls} max-w-sm`} placeholder="Filter by action, e.g. order." aria-label="Filter by action" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} /></Card>
    <Card>{q.isLoading ? <Loading /> : q.isError ? <Failed error={q.error} /> : (<>
      <Table rows={q.data!.items} cols={[{ header: "When", cell: (a) => new Date(a.at).toLocaleString() }, { header: "Who", cell: (a) => a.user ?? "System" }, { header: "Action", cell: (a) => <code>{a.action}</code> },
        { header: "Entity", cell: (a) => `${a.entity_type}${a.entity_id ? ` #${a.entity_id}` : ""}` }, { header: "Details", cell: (a) => (a.changes ? <code className="break-all text-xs">{JSON.stringify(a.changes)}</code> : "—") }, { header: "IP", cell: (a) => a.ip ?? "—" }]} />
      <Pager page={page} pageSize={50} total={q.data!.total} onPage={setPage} /></>)}</Card></>);
}
