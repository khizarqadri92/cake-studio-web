import { resizeImage } from "../lib/resizeImage";
import { ApiError } from "@/lib/api";

// Staff session: separate from the customer session. Access token in memory, refresh token in localStorage.
const RT = "cs_staff_refresh";
let access: string | null = null;
let refreshing: Promise<boolean> | null = null;

export const staff = {
  get access() { return access; },
  get hasRefresh() { try { return !!localStorage.getItem(RT); } catch { return false; } },
  set(a: string, r: string) { access = a; try { localStorage.setItem(RT, r); } catch { /* blocked */ } },
  clear() { access = null; try { localStorage.removeItem(RT); } catch { /* blocked */ } },
  rt() { try { return localStorage.getItem(RT); } catch { return null; } },
};

export function refreshStaff(): Promise<boolean> {
  const rt = staff.rt();
  if (!rt) return Promise.resolve(false);
  refreshing ??= (async () => {
    try {
      const r = await fetch("/api/v1/auth/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: rt }) });
      if (!r.ok) { if (r.status === 401) staff.clear(); return false; }
      const t = await r.json();
      staff.set(t.access_token, t.refresh_token);
      return true;
    } catch { return false; } finally { refreshing = null; }
  })();
  return refreshing;
}

function msg(d: unknown): string {
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => (e && typeof e === "object" && "msg" in e ? `${(e as any).loc?.slice(1).join(".") ?? ""} ${(e as any).msg}`.trim() : String(e))).join("; ");
  return "Something went wrong";
}

async function raw(path: string, init: RequestInit | undefined, retried = false): Promise<Response> {
  const isForm = init?.body instanceof FormData;
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { ...(isForm ? {} : { "Content-Type": "application/json" }), ...(access ? { Authorization: `Bearer ${access}` } : {}), ...(init?.headers ?? {}) },
  });
  if (res.status === 401 && !retried && staff.hasRefresh && path !== "/auth/login" && (await refreshStaff())) return raw(path, init, true);
  if (!res.ok) {
    let m = res.statusText;
    try { m = msg((await res.json()).detail ?? m); } catch { /* non-JSON */ }
    throw new ApiError(res.status, m);
  }
  return res;
}

export async function aapi<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await raw(path, init);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
export const apost = <T = any,>(path: string, body?: unknown) => aapi<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const aput = <T = any,>(path: string, body: unknown) => aapi<T>(path, { method: "PUT", body: JSON.stringify(body) });
export const adel = (path: string) => aapi<void>(path, { method: "DELETE" });

/** Authenticated download/open (exports, invoices): fetch with the bearer token, then hand the blob to the browser. */
export async function download(path: string, filename?: string, open = false) {
  const res = await raw(path, undefined);
  const url = URL.createObjectURL(await res.blob());
  if (open) window.open(url, "_blank", "noopener");
  else { const a = document.createElement("a"); a.href = url; a.download = filename ?? "download"; a.click(); }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export async function uploadImage(file: File): Promise<string> {
  const fd = new FormData();
  fd.append("file", await resizeImage(file));
  return (await aapi<{ url: string }>("/admin/uploads/image", { method: "POST", body: fd })).url;
}
