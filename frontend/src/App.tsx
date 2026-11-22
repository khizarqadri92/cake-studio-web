import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { NotFound, Spinner } from "@/components/states";
import { ThemeApplier } from "@/lib/theme";

const Home = lazy(() => import("@/pages/Home"));
const Shop = lazy(() => import("@/pages/Shop"));
const ProductDetail = lazy(() => import("@/pages/ProductDetail"));
const CmsPage = lazy(() => import("@/pages/CmsPage"));
const Contact = lazy(() => import("@/pages/Contact"));
const CustomCake = lazy(() => import("@/pages/CustomCake"));
const CustomCakeStatus = lazy(() => import("@/pages/CustomCakeStatus"));
const Track = lazy(() => import("@/pages/Track"));
const Cart = lazy(() => import("@/pages/Cart"));
const Checkout = lazy(() => import("@/pages/Checkout"));
const AdminApp = lazy(() => import("@/admin/AdminApp"));
const AuthPages = lazy(() => import("@/pages/AuthPages"));
const Account = lazy(() => import("@/pages/Account"));
const OrderConfirmation = lazy(() => import("@/pages/OrderConfirmation"));

export default function App() {
  return (
    <>
      <ThemeApplier />
      <Suspense fallback={<Spinner />}>
        <Routes>
          <Route path="admin/*" element={<AdminApp />} />
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="shop" element={<Shop />} />
            <Route path="shop/:slug" element={<ProductDetail />} />
            <Route path="p/:slug" element={<CmsPage />} />
            <Route path="contact" element={<Contact />} />
            <Route path="custom-cake" element={<CustomCake />} />
            <Route path="custom-cake/status" element={<CustomCakeStatus />} />
            <Route path="track" element={<Track />} />
            <Route path="cart" element={<Cart />} />
            <Route path="checkout" element={<Checkout />} />
            <Route path="order-confirmation" element={<OrderConfirmation />} />
            <Route path="account" element={<Account />} />
            <Route path="account/login" element={<AuthPages mode="login" />} />
            <Route path="account/register" element={<AuthPages mode="register" />} />
            <Route path="account/forgot" element={<AuthPages mode="forgot" />} />
            <Route path="account/reset-password" element={<AuthPages mode="reset" />} />
            <Route path="account/verify-email" element={<AuthPages mode="verify" />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </>
  );
}
