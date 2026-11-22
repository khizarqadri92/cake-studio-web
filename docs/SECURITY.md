# Security notes

## Implemented
- **Passwords**: argon2id. **Tokens**: 15-min JWT access; refresh tokens are random, stored only as SHA-256, single-use (rotated), revocable.
- **RBAC**: permission codes per role; Super Admin bypass; every admin route has a `require_permission` guard; role edits are audit-logged.
- **Money**: all prices/discounts/totals recomputed server-side from the DB at add-to-cart and again at checkout. Orders snapshot names and prices.
- **Concurrency**: slot capacity (row lock), stock and coupon limits (conditional UPDATE), idempotency key on checkout, row lock on order status/payment changes.
- **Input**: Pydantic validation everywhere; CMS HTML passes an allowlist sanitizer; uploads are sniffed by magic bytes (SVG rejected), size-capped, randomly named.
- **Enumeration**: login uses one error for all failures; order tracking requires order number + phone and returns one 404 for any mismatch; newsletter returns the same response for existing addresses.
- **Rate limits** (per IP): login 10/min, refresh 30/min, checkout 10/min, cart creation 30/min, tracking 10/min, contact and newsletter 5/min.
- **Settings**: the `notifications` group (admin e-mail) is never returned by the public API. Provider secrets (SMTP, WhatsApp, payment gateway) are environment variables only.
- **Audit log** for settings, CMS, catalog, orders, payments, refunds, coupons and role changes.

## Known limitations / to do before production
- The rate limiter is in-process: with several API replicas the effective limit multiplies. Move to Redis (compose already ships a Redis service).
- `TRUST_PROXY_HEADERS` must stay `false` unless a trusted proxy overwrites `X-Forwarded-For`.
- Access tokens cannot be revoked before expiry (15 min); logout revokes the refresh token only.
- No CSRF protection is needed for bearer-token calls; if refresh tokens ever move to cookies, use SameSite=Strict + a CSRF token.
- Online payment gateway webhooks (signature verification) are not implemented yet.
- WhatsApp Cloud API requires approved message templates outside the 24-hour customer window; plain text sends may be rejected by Meta.
- Customer refresh tokens are kept in `localStorage` so reloads stay signed in; an XSS bug would expose them. Access tokens stay in memory. Moving the refresh token to an HttpOnly, SameSite cookie is the recommended hardening. Access tokens (15 min) cannot be revoked before expiry.
- Customer e-mails (verification/reset) need SMTP enabled in admin settings; `DEV_LOG_EMAIL_LINKS=true` logs links instead (development only, never in production).

## Customer accounts

- Passwords: argon2, min 10 chars, common-password and e-mail-equals-password checks.
- Registration and forgot-password return the same response whether or not the e-mail exists; login verifies against a dummy hash for unknown e-mails (no enumeration by response or timing).
- Verification (24 h) and reset (1 h) tokens are random, stored only as hashes, single-use. A successful reset revokes every refresh token.
- Refresh tokens rotate on every use; staff and customer tokens are separate principals and cannot be used on each other's endpoints.
- Accounts are never linked to guest customer records by phone number (a phone is not proof of identity). Order history = orders placed while logged in, plus orders with the account's e-mail once that e-mail is verified.
- Rate limits: register 5/min, login 10/min, forgot 5 per 5 min, reset 10/min, resend 3 per 5 min (per IP, in-process).

## Admin dashboard (/admin)

- Staff sessions are separate from customer sessions (different principal, different localStorage key). Hiding a menu item or page for a missing permission is a convenience only; every admin API call is authorised on the server.
- Staff refresh tokens live in `localStorage` (same XSS trade-off as customer tokens; HttpOnly cookie recommended for production hardening).
- Exports and invoices are fetched with the bearer token and opened as blobs, so no token ever appears in a URL.
- Staff user management: only a Super Admin can grant/remove/modify the Super Admin role, nobody can deactivate themselves, and the last active Super Admin cannot be removed (`services/user_rules.py`, unit-tested). Deactivating a user or resetting their password revokes their refresh tokens. Passwords are never written to the audit log.
- Provider secrets (SMTP, WhatsApp) are server environment variables and are not editable from the dashboard.

## Verification status

- `pytest tests` (unit, no database): pricing, coupons, totals, scheduling, order flow, reports, exports, BOM, custom-cake flow, passwords, user rules, notification rules.
- `pytest tests/integration` (needs `TEST_DATABASE_URL` pointing at a **throwaway** PostgreSQL; it drops and rebuilds the schema): auth/RBAC, refresh rotation, checkout idempotency, stock oversell and cancel-restore, coupon validation, customer-account isolation (IDOR), principal separation, enumeration-safe responses, settings privacy, upload and HTML sanitising.
- The integration suite was written but has not been executed in the authoring environment (no database or package installs were available). Expect to fix small mismatches the first time it runs; each failing test points at a real behaviour to confirm.
