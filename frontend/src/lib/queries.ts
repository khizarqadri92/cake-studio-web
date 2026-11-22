import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Category, CmsPage, Homepage, Navigation, ProductDetail, ProductList, SiteSettings } from "./types";

const stale = 30_000;
export const useSettings = () => useQuery({ queryKey: ["settings"], queryFn: () => api<SiteSettings>("/public/settings"), staleTime: stale });
export const useNavigation = () => useQuery({ queryKey: ["nav"], queryFn: () => api<Navigation>("/public/navigation"), staleTime: stale });
export const useHomepage = () => useQuery({ queryKey: ["home"], queryFn: () => api<Homepage>("/public/homepage"), staleTime: stale });
export const useCategories = () => useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/public/categories"), staleTime: stale });
export const useProducts = (qs: string) => useQuery({ queryKey: ["products", qs], queryFn: () => api<ProductList>(`/public/products?${qs}`), placeholderData: (prev) => prev });
export const useProduct = (slug: string) => useQuery({ queryKey: ["product", slug], queryFn: () => api<ProductDetail>(`/public/products/${encodeURIComponent(slug)}`), retry: false });
export const useCmsPage = (slug: string) => useQuery({ queryKey: ["page", slug], queryFn: () => api<CmsPage>(`/public/pages/${encodeURIComponent(slug)}`), retry: false });
