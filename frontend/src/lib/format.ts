export function money(amount: string | number, currency = "USD"): string {
  const n = typeof amount === "string" ? Number(amount) : amount;
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(n);
  } catch {
    return `${currency} ${n.toFixed(2)}`; // unknown currency code from settings
  }
}

/** Admin-supplied URL used as a link target: allow only safe schemes. */
export function safeHref(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  return /^(\/(?!\/)|https?:\/\/|mailto:|tel:)/i.test(url) ? url : undefined;
}

/** Google Maps embed URL from either a bare URL or a pasted <iframe> snippet; undefined if it isn't a Google Maps URL. */
export function mapEmbedUrl(raw: string | null | undefined): string | undefined {
  if (!raw) return undefined;
  const m = raw.includes("<") ? raw.match(/src\s*=\s*["']([^"']+)["']/i) : null;
  const url = (m ? m[1] : raw).replace(/&amp;/g, "&").trim();
  return /^https:\/\/(www\.)?google\.com\/maps\/|^https:\/\/maps\.google\.com\//i.test(url) ? url : undefined;
}
