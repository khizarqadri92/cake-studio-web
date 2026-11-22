from .conftest import bearer, checkout, new_cart_with

API = "/api/v1"


def test_health(client):
    assert client.get(f"{API}/health").json() == {"status": "ok"}


# ---------- auth & RBAC ----------
def test_admin_endpoints_require_login(client):
    for path in ("/admin/orders", "/admin/users", "/admin/dashboard", "/admin/settings/general", "/admin/audit-logs"):
        assert client.get(API + path).status_code == 401, path


def test_wrong_password_is_generic(client):
    r = client.post(f"{API}/auth/login", json={"email": "root@example.com", "password": "nope-nope-nope"})
    assert r.status_code == 401
    r2 = client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "nope-nope-nope"})
    assert r2.status_code == 401 and r.json() == r2.json()


def test_role_limits_are_enforced_server_side(client, admin):
    r = client.post(f"{API}/admin/users", headers=admin, json={"email": "orders@example.com", "full_name": "Olive Orders", "password": "Another-Strong-Pass-1", "roles": ["Order Manager"]})
    assert r.status_code == 201, r.text
    tok = client.post(f"{API}/auth/login", json={"email": "orders@example.com", "password": "Another-Strong-Pass-1"}).json()["access_token"]
    h = bearer(tok)
    assert client.get(f"{API}/admin/orders", headers=h).status_code == 200
    assert client.get(f"{API}/admin/users", headers=h).status_code == 403
    assert client.put(f"{API}/admin/settings/general", headers=h, json={}).status_code == 403


def test_nobody_but_super_admin_can_make_super_admin(client, admin):
    mgr = client.post(f"{API}/auth/login", json={"email": "orders@example.com", "password": "Another-Strong-Pass-1"}).json()["access_token"]
    r = client.post(f"{API}/admin/users", headers=bearer(mgr), json={"email": "x@example.com", "full_name": "X", "password": "Another-Strong-Pass-1", "roles": ["Super Admin"]})
    assert r.status_code in (403, 422)


def test_refresh_token_rotates_and_cannot_be_replayed(client):
    t = client.post(f"{API}/auth/login", json={"email": "root@example.com", "password": "Correct-Horse-Battery-9"}).json()
    r1 = client.post(f"{API}/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert r1.status_code == 200
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401


# ---------- checkout ----------
def test_order_flow_end_to_end(client, admin, product):
    cart = new_cart_with(client, product["id"], 1)
    r = checkout(client, cart, key="flow-1")
    assert r.status_code == 201, r.text
    number = r.json()["order_number"]
    assert r.json()["status"] == "pending_confirmation"
    # idempotent retry returns the same order, not a second one
    assert checkout(client, new_cart_with(client, product["id"], 1), key="flow-1").json()["order_number"] == number
    # guest tracking needs number + matching phone
    assert client.get(f"{API}/orders/track", params={"order_number": number, "phone": "+923001234567"}).status_code == 200
    assert client.get(f"{API}/orders/track", params={"order_number": number, "phone": "+923009999999"}).status_code == 404
    # staff confirm
    oid = client.get(f"{API}/admin/orders", headers=admin, params={"q": number}).json()["items"][0]["id"]
    r = client.post(f"{API}/admin/orders/{oid}/status", headers=admin, json={"status": "confirmed"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    # illegal jump is refused
    assert client.post(f"{API}/admin/orders/{oid}/status", headers=admin, json={"status": "delivered"}).status_code == 422


def test_client_cannot_set_prices(client, product):
    cart = new_cart_with(client, product["id"], 1)
    r = client.post(f"{API}/cart/{cart}/items", json={"product_id": product["id"], "quantity": 1, "unit_price": "0.01"})
    body = client.get(f"{API}/cart/{cart}").json()
    assert r.status_code in (201, 422)
    assert all(i["unit_price"] == "25.00" for i in body["items"])


def test_stock_cannot_be_oversold(client, admin):
    p = client.post(f"{API}/admin/products", headers=admin, json={"name": "Last Slice", "base_price": "5.00", "track_stock": True, "stock_qty": 1, "prep_time_hours": 0}).json()
    a, b = new_cart_with(client, p["id"]), new_cart_with(client, p["id"])
    assert checkout(client, a, phone="+923001111111").status_code == 201
    assert checkout(client, b, phone="+923002222222").status_code in (409, 422)
    assert client.get(f"{API}/admin/products/{p['id']}", headers=admin).json()["stock_qty"] == 0


def test_cancelling_restores_stock(client, admin):
    p = client.post(f"{API}/admin/products", headers=admin, json={"name": "Cancel Me", "base_price": "5.00", "track_stock": True, "stock_qty": 2, "prep_time_hours": 0}).json()
    num = checkout(client, new_cart_with(client, p["id"], 2), phone="+923003333333").json()["order_number"]
    assert client.get(f"{API}/admin/products/{p['id']}", headers=admin).json()["stock_qty"] == 0
    oid = client.get(f"{API}/admin/orders", headers=admin, params={"q": num}).json()["items"][0]["id"]
    assert client.post(f"{API}/admin/orders/{oid}/status", headers=admin, json={"status": "cancelled"}).status_code == 200
    assert client.get(f"{API}/admin/products/{p['id']}", headers=admin).json()["stock_qty"] == 2


def test_coupon_is_validated_server_side(client, admin, product):
    client.post(f"{API}/admin/coupons", headers=admin, json={"code": "TEN", "kind": "percent", "value": "10"})
    cart = new_cart_with(client, product["id"], 1)
    assert client.put(f"{API}/cart/{cart}/coupon", json={"code": "ten"}).status_code == 200
    assert client.put(f"{API}/cart/{cart}/coupon", json={"code": "DOESNOTEXIST"}).status_code == 422


# ---------- customer accounts ----------
def _register_and_login(client, email):
    pw = "Sturdy-Passphrase-77"
    assert client.post(f"{API}/auth/customer/register", json={"email": email, "password": pw, "full_name": "Cust"}).status_code == 202
    return bearer(client.post(f"{API}/auth/customer/login", json={"email": email, "password": pw}).json()["access_token"])


def test_registration_does_not_reveal_existing_emails(client):
    body = {"email": "dup@example.com", "password": "Sturdy-Passphrase-77", "full_name": "Dup"}
    a = client.post(f"{API}/auth/customer/register", json=body)
    b = client.post(f"{API}/auth/customer/register", json=body)
    assert a.status_code == b.status_code == 202 and a.json() == b.json()
    assert client.post(f"{API}/auth/customer/password/forgot", json={"email": "ghost@example.com"}).status_code == 202


def test_weak_password_rejected(client):
    assert client.post(f"{API}/auth/customer/register", json={"email": "weak@example.com", "password": "password123", "full_name": "W"}).status_code == 422


def test_customers_cannot_see_each_others_orders(client, product):
    ha, hb = _register_and_login(client, "alice@example.com"), _register_and_login(client, "bob@example.com")
    num = checkout(client, new_cart_with(client, product["id"], 1), phone="+923004444444", headers=ha).json()["order_number"]
    assert [o["order_number"] for o in client.get(f"{API}/account/orders", headers=ha).json()["items"]] == [num]
    assert client.get(f"{API}/account/orders", headers=hb).json()["items"] == []
    assert client.get(f"{API}/account/orders/{num}", headers=ha).status_code == 200
    assert client.get(f"{API}/account/orders/{num}", headers=hb).status_code == 404


def test_address_book_is_private(client):
    ha, hb = _register_and_login(client, "carol@example.com"), _register_and_login(client, "dave@example.com")
    aid = client.post(f"{API}/account/addresses", headers=ha, json={"label": "Home", "line": "1 Rose Lane", "city": "Lahore"}).json()["id"]
    assert client.delete(f"{API}/account/addresses/{aid}", headers=hb).status_code == 404
    assert client.put(f"{API}/account/addresses/{aid}", headers=hb, json={"label": "x", "line": "hacked", "city": "x"}).status_code == 404
    assert client.get(f"{API}/account/me", headers=ha).json()["addresses"][0]["line"] == "1 Rose Lane"


def test_principals_are_not_interchangeable(client, admin):
    cust = _register_and_login(client, "erin@example.com")
    assert client.get(f"{API}/admin/orders", headers=cust).status_code in (401, 403)
    assert client.get(f"{API}/account/me", headers=admin).status_code == 401


# ---------- public data hygiene ----------
def test_public_settings_do_not_leak_private_groups(client):
    s = client.get(f"{API}/public/settings").json()
    assert "notifications" not in s and "inventory" not in s


def test_uploads_reject_non_images(client, admin):
    r = client.post(f"{API}/admin/uploads/image", headers=admin, files={"file": ("evil.png", b"<script>alert(1)</script>", "image/png")})
    assert r.status_code in (400, 415, 422)


def test_cms_html_is_sanitised(client, admin):
    r = client.post(f"{API}/admin/pages", headers=admin, json={"slug": "xss-test", "title": "T", "body_html": "<p>hi</p><script>alert(1)</script><img src=x onerror=alert(1)>"})
    assert r.status_code == 201
    html = client.get(f"{API}/public/pages/xss-test").json()["body_html"]
    assert "<script" not in html and "onerror" not in html and "<p>hi</p>" in html


# ---------- reviews ----------
def test_reviews_need_a_delivered_order_and_moderation(client, admin, product):
    num = checkout(client, new_cart_with(client, product["id"], 1), phone="+923005555555").json()["order_number"]
    body = {"product_id": product["id"], "order_number": num, "phone": "+923005555555", "rating": 5, "comment": "Yum"}
    assert client.post(f"{API}/reviews", json=body).status_code == 422  # not delivered yet
    assert client.post(f"{API}/reviews", json=body | {"phone": "+923000000000"}).status_code == 404  # wrong phone
    oid = client.get(f"{API}/admin/orders", headers=admin, params={"q": num}).json()["items"][0]["id"]
    for s in ("confirmed", "in_preparation", "out_for_delivery", "delivered"):
        assert client.post(f"{API}/admin/orders/{oid}/status", headers=admin, json={"status": s}).status_code == 200, s
    assert client.post(f"{API}/reviews", json=body).status_code == 201
    assert client.post(f"{API}/reviews", json=body).status_code == 422  # one review per order+product
    slug = client.get(f"{API}/admin/products/{product['id']}", headers=admin).json()["slug"]
    assert client.get(f"{API}/public/products/{slug}/reviews").json()["count"] == 0  # hidden until approved
    rid = client.get(f"{API}/admin/reviews", headers=admin, params={"status": "pending"}).json()["items"][0]["id"]
    assert client.put(f"{API}/admin/reviews/{rid}", headers=admin, json={"status": "approved"}).status_code == 200
    assert client.get(f"{API}/public/products/{slug}/reviews").json()["count"] == 1
