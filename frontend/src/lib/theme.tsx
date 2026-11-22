import { useEffect } from "react";
import { useSettings } from "./queries";

const RADIUS = { pill: "9999px", rounded: "0.75rem", square: "0.25rem" } as const;

function loadFont(name: string) {
  const id = `font-${name.replace(/\s+/g, "-")}`;
  if (document.getElementById(id)) return;
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(name).replace(/%20/g, "+")}:wght@400;500;600;700&display=swap`;
  document.head.appendChild(link);
}

/** Applies admin-configured theme + favicon + default SEO tags. Renders nothing. */
export function ThemeApplier() {
  const { data } = useSettings();
  useEffect(() => {
    if (!data) return;
    const t = data.theme;
    const root = document.documentElement.style;
    root.setProperty("--color-primary", t.primary_color);
    root.setProperty("--color-secondary", t.secondary_color);
    root.setProperty("--color-background", t.background_color);
    root.setProperty("--color-surface", t.surface_color);
    root.setProperty("--color-text", t.text_color);
    root.setProperty("--font-heading", `"${t.heading_font}", serif`);
    root.setProperty("--font-body", `"${t.body_font}", sans-serif`);
    root.setProperty("--radius-btn", RADIUS[t.button_style] ?? RADIUS.pill);
    loadFont(t.heading_font);
    loadFont(t.body_font);
    if (data.general.favicon_url) {
      let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
      if (!link) { link = document.createElement("link"); link.rel = "icon"; document.head.appendChild(link); }
      link.href = data.general.favicon_url;
    }
  }, [data]);
  return null;
}

/** Sets <title>, description and og:image; falls back to the site-wide SEO settings. */
export function useSeo(title?: string | null, description?: string | null) {
  const { data } = useSettings();
  useEffect(() => {
    if (!data) return;
    const site = data.seo.meta_title || data.general.site_name;
    document.title = title ? `${title} | ${data.general.site_name}` : site;
    const desc = description || data.seo.meta_description || "";
    setMeta("name", "description", desc);
    setMeta("property", "og:title", document.title);
    setMeta("property", "og:description", desc);
    if (data.seo.og_image_url) setMeta("property", "og:image", data.seo.og_image_url);
  }, [data, title, description]);
}

function setMeta(attr: "name" | "property", key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}='${key}']`);
  if (!el) { el = document.createElement("meta"); el.setAttribute(attr, key); document.head.appendChild(el); }
  el.content = content;
}
