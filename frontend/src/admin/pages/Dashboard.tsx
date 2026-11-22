import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { aapi } from "../api";
import { Badge, Card, Failed, inputCls, label, Loading, PageHeader, statusTone, Table } from "../kit";
import { money } from "@/lib/format";
import { useSettings } from "@/lib/queries";

export default function Dashboard() {
  const cur = useSettings().data?.general.currency_code;
  const [range, setRange] = useState({ date_from: "", date_to: "" });
  const qs = new URLSearchParams((Object.entries(range) as [string, string][]).filter(([, v]) => v)).toString();
  const q = useQuery({ queryKey: ["admin", "dashboard", qs], queryFn: () => aapi<any>(`/admin/dashboard?${qs}`) });
  if (q.isLoading) return <Loading />;
  if (q.isError) return <Failed error={q.error} />;
  const d = q.data;
  const tiles: [string, string][] = [["Today's sales", money(d.today_sales, cur)], ["This month", money(d.month_revenue, cur)], ["All-time sales", money(d.all_time_sales, cur)],
    ["Pending confirmation", String(d.pending_orders)], ["Orders in range", String(d.total_orders)]];
  const series: { period: string; revenue: string }[] = d.sales_series ?? [];
  const max = Math.max(1, ...series.map((s) => Number(s.revenue)));
  return (
    <>
      <PageHeader title="Dashboard">
        <input type="date" aria-label="From" className={inputCls} value={range.date_from} onChange={(e) => setRange({ ...range, date_from: e.target.value })} />
        <input type="date" aria-label="To" className={inputCls} value={range.date_to} onChange={(e) => setRange({ ...range, date_to: e.target.value })} />
      </PageHeader>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">{tiles.map(([k, v], i) => (
        <Card key={k} className="relative overflow-hidden">
          <span className={`absolute inset-y-0 left-0 w-1.5 ${["bg-primary", "bg-pink-300", "bg-amber-400", "bg-orange-400", "bg-sky-400"][i % 5]}`} aria-hidden="true" />
          <p className="text-xs font-medium uppercase tracking-wide text-ink/60">{k}</p><p className="mt-2 text-2xl font-semibold text-ink md:text-[1.7rem]">{v}</p>
        </Card>
      ))}</div>
      {series.length > 0 && (
        <Card className="mt-6"><h2 className="mb-4 font-heading text-xl text-ink">Sales</h2>
          <div className="flex h-48 items-end gap-1.5" role="img" aria-label="Sales per day bar chart">{series.map((s, i) => <div key={i} title={`${s.period}: ${money(s.revenue, cur)}`} className="min-w-1 flex-1 rounded-t-lg bg-gradient-to-t from-primary to-primary/50 transition hover:opacity-80" style={{ height: `${(Number(s.revenue) / max) * 100}%` }} />)}</div>
        </Card>
      )}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card><h2 className="mb-4 font-heading text-xl text-ink">Recent orders</h2>
          <Table rows={d.recent_orders} empty="No orders yet." cols={[
            { header: "Order", cell: (o: any) => <Link className="text-primary" to={`/admin/orders/${o.id}`}>{o.order_number}</Link> }, { header: "Customer", cell: (o: any) => o.customer },
            { header: "Status", cell: (o: any) => <Badge tone={statusTone(o.status)}>{label(o.status)}</Badge> }, { header: "Total", className: "text-right", cell: (o: any) => money(o.total, cur) }]} /></Card>
        <Card><h2 className="mb-4 font-heading text-xl text-ink">Low stock</h2>
          {d.low_stock_products.length + d.low_stock_ingredients.length === 0 ? <p className="text-sm text-ink/60">Everything is stocked.</p> : (
            <ul className="space-y-1 text-sm">
              {d.low_stock_products.map((p: any) => <li key={`p${p.id}`}><Link className="text-primary" to={`/admin/products/${p.id}`}>{p.name}</Link> — {p.stock} left</li>)}
              {d.low_stock_ingredients.map((i: any) => <li key={`i${i.id}`}><Link className="text-primary" to="/admin/inventory">{i.name}</Link> — {i.stock} {i.unit} left</li>)}
            </ul>)}
        </Card>
      </div>
      <Card className="mt-6"><h2 className="mb-4 font-heading text-xl text-ink">Best sellers ({d.range.from} → {d.range.to})</h2>
        <Table rows={d.best_sellers.map((b: any, i: number) => ({ ...b, id: i }))} empty="No sales in this range." cols={[{ header: "Product", cell: (b: any) => b.product }, { header: "Qty", cell: (b: any) => b.quantity }, { header: "Revenue", className: "text-right", cell: (b: any) => money(b.revenue, cur) }]} /></Card>
    </>
  );
}
