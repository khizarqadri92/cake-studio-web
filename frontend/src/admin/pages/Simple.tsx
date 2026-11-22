import { useQuery } from "@tanstack/react-query";
import { aapi } from "../api";
import { CrudPage, type F } from "../Crud";
import { Badge, label } from "../kit";

const yes = (v: boolean) => <Badge tone={v ? "green" : "gray"}>{v ? "Active" : "Hidden"}</Badge>;
const useList = <T,>(path: string) => useQuery({ queryKey: [path], queryFn: () => aapi<T[]>(path) }).data ?? [];
const DAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function Categories() {
  const cats = useList<{ id: number; name: string }>("/admin/categories");
  const fields: F[] = [
    { key: "name", label: "Name", type: "text", required: true }, { key: "slug", label: "URL slug", type: "text", hint: "Leave blank to generate from the name" },
    { key: "parent_id", label: "Parent category", type: "select", options: cats.map((c) => ({ value: c.id, label: c.name })) },
    { key: "description", label: "Description", type: "textarea" }, { key: "image_url", label: "Image", type: "image" }, { key: "is_active", label: "Visible in shop", type: "checkbox", default: true },
  ];
  return <CrudPage<any> title="Categories" path="/admin/categories" write="products.write" reorder fields={fields}
    columns={[{ header: "Name", cell: (r) => <b>{r.name}</b> }, { header: "Parent", cell: (r) => cats.find((c) => c.id === r.parent_id)?.name ?? "—" }, { header: "Status", cell: (r) => yes(r.is_active) }]} />;
}

export const Flavours = () => <CrudPage<any> title="Flavours" path="/admin/flavours" write="products.write"
  fields={[{ key: "name", label: "Name", type: "text", required: true }, { key: "is_active", label: "Available", type: "checkbox", default: true }]}
  columns={[{ header: "Name", cell: (r) => <b>{r.name}</b> }, { header: "Status", cell: (r) => yes(r.is_active) }]} />;

export const Suppliers = () => <CrudPage<any> title="Suppliers" path="/admin/suppliers" write="inventory.write"
  fields={[{ key: "name", label: "Name", type: "text", required: true }, { key: "contact_name", label: "Contact person", type: "text" }, { key: "phone", label: "Phone", type: "text" },
    { key: "email", label: "Email", type: "text" }, { key: "address", label: "Address", type: "text", span2: true }, { key: "notes", label: "Notes", type: "textarea" }]}
  columns={[{ header: "Name", cell: (r) => <b>{r.name}</b> }, { header: "Contact", cell: (r) => [r.contact_name, r.phone].filter(Boolean).join(" · ") || "—" }, { header: "Email", cell: (r) => r.email ?? "—" }]} />;

export const Banners = () => <CrudPage<any> title="Banners" path="/admin/banners" write="cms.write" reorder
  fields={[{ key: "title", label: "Title", type: "text", required: true }, { key: "subtitle", label: "Subtitle", type: "text" }, { key: "link_url", label: "Link (e.g. /shop)", type: "text" },
    { key: "placement", label: "Placement", type: "select", required: true, default: "home_promo", options: [{ value: "home_promo", label: "Homepage promo" }, { value: "home_hero", label: "Homepage hero" }] },
    { key: "image_url", label: "Image", type: "image" }, { key: "is_active", label: "Active", type: "checkbox", default: true }]}
  columns={[{ header: "", cell: (r) => r.image_url ? <img src={r.image_url} alt="" className="h-10 w-16 rounded object-cover" /> : null }, { header: "Title", cell: (r) => <b>{r.title}</b> }, { header: "Placement", cell: (r) => label(r.placement) }, { header: "Status", cell: (r) => yes(r.is_active) }]} />;

export const Testimonials = () => <CrudPage<any> title="Testimonials" path="/admin/testimonials" write="cms.write" reorder
  fields={[{ key: "customer_name", label: "Customer name", type: "text", required: true }, { key: "rating", label: "Rating (1–5)", type: "int", required: true, default: 5 },
    { key: "quote", label: "Quote", type: "textarea", required: true }, { key: "photo_url", label: "Photo", type: "image" }, { key: "is_active", label: "Show on site", type: "checkbox", default: true }]}
  columns={[{ header: "Customer", cell: (r) => <b>{r.customer_name}</b> }, { header: "Rating", cell: (r) => "★".repeat(r.rating) }, { header: "Quote", cell: (r) => <span className="line-clamp-2">{r.quote}</span> }, { header: "Status", cell: (r) => yes(r.is_active) }]} />;

export function Navigation() {
  const items = useList<any>("/admin/navigation");
  const fields: F[] = [
    { key: "location", label: "Location", type: "select", required: true, default: "header", options: [{ value: "header", label: "Header" }, { value: "footer", label: "Footer" }] },
    { key: "label", label: "Label", type: "text", required: true }, { key: "url", label: "Link", type: "text", required: true, hint: "/shop, https://…, mailto:…, tel:…" },
    { key: "parent_id", label: "Parent (dropdown)", type: "select", options: items.filter((i) => !i.parent_id).map((i) => ({ value: i.id, label: `${label(i.location)}: ${i.label}` })) },
    { key: "open_in_new_tab", label: "Open in new tab", type: "checkbox" }, { key: "is_active", label: "Active", type: "checkbox", default: true },
  ];
  return <CrudPage<any> title="Navigation" path="/admin/navigation" write="cms.write" reorder fields={fields}
    columns={[{ header: "Label", cell: (r) => <span className={r.parent_id ? "pl-5 text-ink/70" : "font-medium"}>{r.label}</span> }, { header: "Link", cell: (r) => r.url }, { header: "Where", cell: (r) => label(r.location) }, { header: "Status", cell: (r) => yes(r.is_active) }]} />;
}

export const CmsPages = () => <CrudPage<any> title="Pages" path="/admin/pages" write="cms.write"
  note="Page content is cleaned on save: scripts and unsafe markup are removed."
  fields={[{ key: "title", label: "Title", type: "text", required: true }, { key: "slug", label: "URL slug", type: "text", required: true, hint: "Lowercase letters, digits and dashes. Page appears at /p/<slug>" },
    { key: "body_html", label: "Content (HTML)", type: "textarea" }, { key: "meta_title", label: "SEO title", type: "text" }, { key: "meta_description", label: "SEO description", type: "text" },
    { key: "is_published", label: "Published", type: "checkbox", default: true }]}
  columns={[{ header: "Title", cell: (r) => <b>{r.title}</b> }, { header: "URL", cell: (r) => `/p/${r.slug}` }, { header: "Status", cell: (r) => <Badge tone={r.is_published ? "green" : "gray"}>{r.is_published ? "Published" : "Draft"}</Badge> }]} />;

export function Coupons() {
  const products = useQuery({ queryKey: ["admin", "products", "all"], queryFn: () => aapi<{ items: { id: number; name: string }[] }>("/admin/products?page_size=100") }).data?.items ?? [];
  const cats = useList<{ id: number; name: string }>("/admin/categories");
  const fields: F[] = [
    { key: "code", label: "Code", type: "text", required: true, hint: "Letters, digits, - and _" },
    { key: "kind", label: "Type", type: "select", required: true, default: "percent", options: [{ value: "percent", label: "Percentage off" }, { value: "fixed", label: "Fixed amount off" }] },
    { key: "value", label: "Value", type: "decimal", required: true }, { key: "min_order", label: "Minimum order", type: "decimal" }, { key: "max_discount", label: "Maximum discount", type: "decimal" },
    { key: "starts_at", label: "Starts", type: "datetime" }, { key: "expires_at", label: "Expires", type: "datetime" },
    { key: "usage_limit", label: "Total uses allowed", type: "int" }, { key: "per_customer_limit", label: "Uses per customer", type: "int" },
    { key: "first_order_only", label: "First order only", type: "checkbox" }, { key: "is_active", label: "Active", type: "checkbox", default: true },
    { key: "product_ids", label: "Only these products (blank = all)", type: "multi", options: products.map((p) => ({ value: p.id, label: p.name })) },
    { key: "category_ids", label: "Only these categories (blank = all)", type: "multi", options: cats.map((c) => ({ value: c.id, label: c.name })) },
  ];
  return <CrudPage<any> title="Coupons" path="/admin/coupons" write="coupons.write" fields={fields}
    columns={[{ header: "Code", cell: (r) => <b>{r.code}</b> }, { header: "Discount", cell: (r) => (r.kind === "percent" ? `${r.value}%` : r.value) }, { header: "Used", cell: (r) => `${r.used_count}${r.usage_limit ? ` / ${r.usage_limit}` : ""}` },
      { header: "Expires", cell: (r) => (r.expires_at ? new Date(r.expires_at).toLocaleDateString() : "Never") }, { header: "Status", cell: (r) => yes(r.is_active) }]} />;
}

export function Delivery() {
  return (<>
    <CrudPage<any> title="Delivery slots" path="/admin/delivery-slots" write="settings.write"
      note="Customers pick one of these windows. 'Max orders' caps how many orders can use a slot on one day."
      fields={[{ key: "start_time", label: "Starts", type: "time", required: true }, { key: "end_time", label: "Ends", type: "time", required: true }, { key: "max_orders", label: "Max orders per day", type: "int", required: true, default: 5 },
        { key: "weekdays", label: "Days available", type: "weekdays" }, { key: "is_active", label: "Active", type: "checkbox", default: true }]}
      columns={[{ header: "Window", cell: (r) => <b>{String(r.start_time).slice(0, 5)} – {String(r.end_time).slice(0, 5)}</b> }, { header: "Max/day", cell: (r) => r.max_orders },
        { header: "Days", cell: (r) => (r.weekdays.length === 7 ? "Every day" : r.weekdays.map((d: number) => DAY[d]).join(", ")) }, { header: "Status", cell: (r) => yes(r.is_active) }]} />
    <div className="mt-10" />
    <CrudPage<any> title="Blocked dates" path="/admin/blocked-dates" write="settings.write" canEdit={false} createLabel="Block"
      note="Holidays or days you are fully booked. No orders can be scheduled on these dates."
      fields={[{ key: "day", label: "Date", type: "date", required: true }, { key: "reason", label: "Reason", type: "text" }]}
      columns={[{ header: "Date", cell: (r) => <b>{r.day}</b> }, { header: "Reason", cell: (r) => r.reason || "—" }]} />
  </>);
}

export const PaymentMethods = () => <CrudPage<any> title="Payment methods" path="/admin/payment-methods" write="settings.write" canCreate={false} canDelete={false}
  note="Bank details or instructions are shown to the customer at checkout and on their confirmation."
  fields={[{ key: "code", label: "Type", type: "select", required: true, readOnlyOnEdit: true, options: [{ value: "cod", label: "Cash on delivery" }, { value: "bank_transfer", label: "Bank transfer" }, { value: "online", label: "Online payment" }, { value: "pay_on_pickup", label: "Pay on pickup" }] },
    { key: "name", label: "Display name", type: "text", required: true }, { key: "applies_to", label: "Available for", type: "select", required: true, options: [{ value: "both", label: "Delivery & pickup" }, { value: "delivery", label: "Delivery only" }, { value: "pickup", label: "Pickup only" }] },
    { key: "instructions", label: "Instructions shown to customer", type: "textarea" }, { key: "is_active", label: "Enabled", type: "checkbox", default: true }]}
  columns={[{ header: "Name", cell: (r) => <b>{r.name}</b> }, { header: "Type", cell: (r) => label(r.code) }, { header: "For", cell: (r) => label(r.applies_to) }, { header: "Status", cell: (r) => yes(r.is_active) }]} />;
