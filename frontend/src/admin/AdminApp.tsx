import type { ReactNode } from "react";
import { Route, Routes } from "react-router-dom";
import { StaffProvider } from "./auth";
import { AdminLogin, AdminShell, Guard } from "./Shell";
import { Banners, Categories, CmsPages, Coupons, Delivery, Flavours, Navigation, PaymentMethods, Suppliers, Testimonials } from "./pages/Simple";
import { CustomCakeDetail, CustomCakesList, CustomerDetail, CustomersList, Reports } from "./pages/Sales";
import { Homepage, Inbox, SiteSettings } from "./pages/Site";
import { AuditLog, Roles, Users } from "./pages/Staff";
import { InventoryItems, PurchaseOrders, StockHistory } from "./pages/Inventory";
import { OrderDetail, OrdersList } from "./pages/Orders";
import { ProductEditor, ProductsList } from "./pages/Products";
import Dashboard from "./pages/Dashboard";
import Reviews from "./pages/Reviews";

const g = (perm: string, el: ReactNode) => <Guard perm={perm}>{el}</Guard>;

export default function AdminApp() {
  return (
    <StaffProvider>
      <Routes>
        <Route path="login" element={<AdminLogin />} />
        <Route element={<AdminShell />}>
          <Route index element={g("dashboard.read", <Dashboard />)} />
          <Route path="reports" element={g("reports.read", <Reports />)} />
          <Route path="orders" element={g("orders.read", <OrdersList />)} />
          <Route path="orders/:id" element={g("orders.read", <OrderDetail />)} />
          <Route path="custom-cakes" element={g("orders.read", <CustomCakesList />)} />
          <Route path="custom-cakes/:id" element={g("orders.read", <CustomCakeDetail />)} />
          <Route path="customers" element={g("customers.read", <CustomersList />)} />
          <Route path="customers/:id" element={g("customers.read", <CustomerDetail />)} />
          <Route path="coupons" element={g("coupons.read", <Coupons />)} />
          <Route path="products" element={g("products.read", <ProductsList />)} />
          <Route path="products/:id" element={g("products.read", <ProductEditor />)} />
          <Route path="reviews" element={g("products.read", <Reviews />)} />
          <Route path="categories" element={g("products.read", <Categories />)} />
          <Route path="flavours" element={g("products.read", <Flavours />)} />
          <Route path="inventory" element={g("inventory.read", <InventoryItems />)} />
          <Route path="suppliers" element={g("inventory.read", <Suppliers />)} />
          <Route path="purchase-orders" element={g("inventory.read", <PurchaseOrders />)} />
          <Route path="stock-history" element={g("inventory.read", <StockHistory />)} />
          <Route path="homepage" element={g("cms.read", <Homepage />)} />
          <Route path="pages" element={g("cms.read", <CmsPages />)} />
          <Route path="navigation" element={g("cms.read", <Navigation />)} />
          <Route path="banners" element={g("cms.read", <Banners />)} />
          <Route path="testimonials" element={g("cms.read", <Testimonials />)} />
          <Route path="inbox" element={g("cms.read", <Inbox />)} />
          <Route path="settings" element={g("settings.read", <SiteSettings />)} />
          <Route path="delivery" element={g("settings.read", <Delivery />)} />
          <Route path="payment-methods" element={g("settings.read", <PaymentMethods />)} />
          <Route path="users" element={g("users.read", <Users />)} />
          <Route path="roles" element={g("roles.read", <Roles />)} />
          <Route path="audit" element={g("audit.read", <AuditLog />)} />
          <Route path="*" element={<p className="p-6">Page not found.</p>} />
        </Route>
      </Routes>
    </StaffProvider>
  );
}
