import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { aapi, adel, aput } from "../api";
import { useStaff } from "../auth";
import { Badge, Card, ErrLine, Failed, inputCls, label, Loading, PageHeader, Pager, Table, useAction } from "../kit";

export default function Reviews() {
  const { can } = useStaff(); const w = can("products.write");
  const [status, setStatus] = useState("pending"); const [page, setPage] = useState(1);
  const key = ["admin", "reviews", status, page];
  const q = useQuery({ queryKey: key, queryFn: () => aapi<{ items: any[]; total: number }>(`/admin/reviews?page=${page}${status ? `&status=${status}` : ""}`), placeholderData: (p) => p });
  const set = useAction((v: { id: number; status: string }) => aput(`/admin/reviews/${v.id}`, { status: v.status }), [["admin", "reviews"]]);
  const del = useAction((id: number) => adel(`/admin/reviews/${id}`), [["admin", "reviews"]]);
  return (<><PageHeader title="Product reviews" />
    <p className="mb-4 text-sm text-ink/70">Reviews come from delivered orders only and stay hidden until you approve them.</p>
    <Card className="mb-4"><select className={`${inputCls} max-w-xs`} aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All</option>{["pending", "approved", "rejected"].map((s) => <option key={s} value={s}>{label(s)}</option>)}</select></Card>
    <Card>{q.isLoading ? <Loading /> : q.isError ? <Failed error={q.error} /> : (<>
      <Table rows={q.data!.items} empty="No reviews here." cols={[
        { header: "Product", cell: (r) => <Link className="text-primary" to={`/admin/products/${r.product_id}`}>{r.product}</Link> },
        { header: "Review", cell: (r) => <><span className="text-amber-500">{"★".repeat(r.rating)}</span> <b>{r.name}</b><p className="max-w-md whitespace-pre-wrap text-sm">{r.comment}</p></> },
        { header: "Order", cell: (r) => <Link className="text-primary" to={`/admin/orders/${r.order_id}`}>#{r.order_id}</Link> },
        { header: "Status", cell: (r) => <Badge tone={r.status === "approved" ? "green" : r.status === "rejected" ? "red" : "amber"}>{label(r.status)}</Badge> },
        { header: "", className: "text-right whitespace-nowrap", cell: (r) => w && <span className="space-x-3">{r.status !== "approved" && <button className="text-green-700 underline" onClick={() => set.mutate({ id: r.id, status: "approved" })}>Approve</button>}{r.status !== "rejected" && <button className="text-amber-700 underline" onClick={() => set.mutate({ id: r.id, status: "rejected" })}>Reject</button>}<button className="text-red-700 underline" onClick={() => { if (confirm("Delete this review permanently?")) del.mutate(r.id); }}>Delete</button></span> }]} />
      <Pager page={page} pageSize={25} total={q.data!.total} onPage={setPage} /></>)}
      <ErrLine error={set.error ?? del.error} /></Card></>);
}
