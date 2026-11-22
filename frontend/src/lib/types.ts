export interface BusinessHour { day: string; open?: string; close?: string; closed?: boolean }
export interface SiteSettings {
  general: {
    site_name: string; tagline: string; logo_url: string | null; favicon_url: string | null;
    email: string | null; phone: string | null; whatsapp: string | null; address: string | null;
    google_maps_embed_url: string | null; business_hours: BusinessHour[];
    currency_code: string; currency_symbol: string;
  };
  theme: {
    primary_color: string; secondary_color: string; background_color: string; surface_color: string;
    text_color: string; heading_font: string; body_font: string;
    button_style: "rounded" | "pill" | "square"; header_layout: "centered" | "left" | "split";
    footer_layout: "simple" | "columns";
  };
  social: { facebook: string | null; instagram: string | null; tiktok: string | null; youtube: string | null; whatsapp: string | null };
  seo: { meta_title: string | null; meta_description: string | null; og_image_url: string | null };
}
export interface NavItem { id: number; label: string; url: string; new_tab: boolean; children: NavItem[] }
export interface Navigation { header: NavItem[]; footer: NavItem[] }
export interface HomeSection { key: string; title: string; content: Record<string, any> }
export interface Banner { id: number; title: string; subtitle: string; image_url: string | null; link_url: string | null; placement: string }
export interface Testimonial { id: number; name: string; quote: string; rating: number; photo_url: string | null }
export interface Homepage { sections: HomeSection[]; banners: Banner[]; testimonials: Testimonial[] }
export interface Category { id: number; name: string; slug: string; description: string; image_url: string | null; parent_id: number | null }
export interface ProductCard {
  id: number; slug: string; name: string; image: string | null; from_price: string; has_options: boolean;
  on_sale: boolean; is_available: boolean; in_stock: boolean; is_featured: boolean; is_bestseller: boolean;
}
export interface ProductList { items: ProductCard[]; total: number; page: number; page_size: number }
export interface ProductDetail extends ProductCard {
  description: string; product_type: "simple" | "variable"; category: { name: string; slug: string } | null;
  images: { url: string; alt: string }[];
  variants: { id: number; name: string; kind: string; price: string; sale_price: string | null; in_stock: boolean }[];
  option_groups: { id: number; name: string; is_required: boolean; choices: { id: number; label: string; price_delta: string }[] }[];
  addons: { id: number; name: string; price: string }[];
  allows_message: boolean; message_max_length: number; prep_time_hours: number;
  meta_title: string; meta_description: string | null;
}
export interface Quote { unit_price: string; line_total: string; quantity: number; breakdown: { base: string; options: string; addons: string } }
export interface CmsPage { slug: string; title: string; body_html: string; meta_title: string | null; meta_description: string | null }
export interface CartLine {
  id: number; product_id: number | null; name: string; error: string | null;
  slug?: string; image?: string | null; variant?: string | null; options?: string[]; addons?: string[];
  message?: string | null; quantity?: number; unit_price?: string; line_total?: string;
}
export interface CartTotals { subtotal: string; discount: string; delivery_fee: string; tax: string; total: string }
export interface Cart { token: string; items: CartLine[]; coupon_code: string | null; coupon_error: string | null; totals: CartTotals | null }
export interface Slot { slot_id: number; start: string; end: string; remaining: number }
export interface PayMethod { code: string; name: string; instructions: string }
export interface OrderPlaced {
  order_number: string; status: string; total: string; payment_method: string; payment_instructions: string;
  delivery_date: string; slot: string;
}
