import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, post } from "./api";
import type { Cart } from "./types";

const KEY = "cs_cart";
const read = (): string | null => { try { return localStorage.getItem(KEY); } catch { return null; } };
const write = (t: string | null) => { try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch { /* storage blocked: cart lives for this tab only */ } };

export interface AddItem {
  product_id: number; variant_id: number | null; choice_ids: number[]; addon_ids: number[];
  quantity: number; message?: string | null; instructions?: string | null;
}

interface Ctx {
  token: string | null;
  count: number;
  add: (item: AddItem) => Promise<void>;
  clear: () => void;
}
const CartCtx = createContext<Ctx | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [token, setToken] = useState<string | null>(read);

  const { data } = useQuery({
    queryKey: ["cart", token, "delivery"],
    enabled: !!token,
    queryFn: async () => {
      try { return await api<Cart>(`/cart/${token}?fulfillment=delivery`); }
      catch (e) { if (e instanceof ApiError && e.status === 404) { write(null); setToken(null); } throw e; }
    },
    retry: false,
  });

  const addM = useMutation({
    mutationFn: async (item: AddItem) => {
      let t = token;
      if (!t) {
        t = (await post<{ token: string }>("/cart", {})).token;
        write(t); setToken(t);
      }
      try { await post(`/cart/${t}/items`, item); }
      catch (e) {
        if (e instanceof ApiError && e.status === 404 && e.message === "Cart not found") { // stale token: start over once
          t = (await post<{ token: string }>("/cart", {})).token;
          write(t); setToken(t);
          await post(`/cart/${t}/items`, item);
        } else throw e;
      }
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cart"] }),
  });

  const clear = useCallback(() => { write(null); setToken(null); qc.removeQueries({ queryKey: ["cart"] }); }, [qc]);
  const value = useMemo<Ctx>(() => ({
    token,
    count: data?.items.reduce((n, i) => n + (i.quantity ?? 0), 0) ?? 0,
    add: (item) => addM.mutateAsync(item),
    clear,
  }), [token, data, addM, clear]);
  return <CartCtx.Provider value={value}>{children}</CartCtx.Provider>;
}

export function useCartCtx(): Ctx {
  const c = useContext(CartCtx);
  if (!c) throw new Error("CartProvider missing");
  return c;
}

export function useCartData(fulfillment: "delivery" | "pickup" = "delivery") {
  const { token } = useCartCtx();
  return useQuery({
    queryKey: ["cart", token, fulfillment],
    enabled: !!token,
    queryFn: () => api<Cart>(`/cart/${token}?fulfillment=${fulfillment}`),
    retry: false,
  });
}

/** Cart mutations that all end by refreshing every cached cart view. */
export function useCartActions() {
  const { token } = useCartCtx();
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: ["cart"] });
  return {
    setQty: useMutation({ mutationFn: (v: { id: number; quantity: number }) => api(`/cart/${token}/items/${v.id}`, { method: "PATCH", body: JSON.stringify({ quantity: v.quantity }) }), onSuccess: done }),
    remove: useMutation({ mutationFn: (id: number) => api(`/cart/${token}/items/${id}`, { method: "DELETE" }), onSuccess: done }),
    applyCoupon: useMutation({ mutationFn: (code: string) => api(`/cart/${token}/coupon`, { method: "PUT", body: JSON.stringify({ code }) }), onSuccess: done }),
    removeCoupon: useMutation({ mutationFn: () => api(`/cart/${token}/coupon`, { method: "DELETE" }), onSuccess: done }),
  };
}
