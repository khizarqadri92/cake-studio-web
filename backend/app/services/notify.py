"""Notification outbox: enqueue inside the order transaction, deliver from the worker with retries."""
import json
import smtplib
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Notification, Order
from app.services import shop
from app.services.messages import OrderView, render, render_custom
from app.services.outbox_rules import MAX_ATTEMPTS, apply_result  # noqa: F401



def _view(o: Order, currency: str, note: str = "") -> OrderView:
    return OrderView(o.order_number, o.customer_name, o.status, o.fulfillment, o.delivery_date.isoformat(), o.slot_label,
                     o.total, currency, note)


def enqueue_for_order(db: Session, o: Order, event: str, note: str = "") -> None:
    """event: order_placed | status_changed. Call before commit so rows are atomic with the order change."""
    cfg, gen = shop.get_group(db, "notifications"), shop.get_group(db, "general")
    now = datetime.now(timezone.utc)
    if event == "status_changed" and o.status not in cfg["notify_statuses"]:
        subject, body = None, None
    else:
        subject, body = render(event, _view(o, gen["currency_code"], note), gen["site_name"])
    if body:
        if cfg["email_enabled"] and o.customer_email:
            db.add(Notification(channel="email", recipient=o.customer_email, subject=subject, body=body, order_id=o.id,
                                created_at=now, next_attempt_at=now))
        if cfg["whatsapp_enabled"]:
            db.add(Notification(channel="whatsapp", recipient=o.customer_phone.lstrip("+"), subject="", body=body,
                                order_id=o.id, created_at=now, next_attempt_at=now))
    if event == "order_placed":  # staff bell
        db.add(Notification(channel="inapp", recipient="staff", subject=f"New order {o.order_number}",
                            body=f"{o.customer_name} · {gen['currency_code']} {o.total:.2f} · {o.delivery_date} {o.slot_label}",
                            order_id=o.id, status="sent", created_at=now, next_attempt_at=now, sent_at=now))
        if cfg["email_enabled"] and cfg["admin_email"]:
            db.add(Notification(channel="email", recipient=cfg["admin_email"], subject=f"New order {o.order_number}",
                                body=f"New order {o.order_number} from {o.customer_name} ({o.customer_phone}), total {o.total:.2f}.",
                                order_id=o.id, created_at=now, next_attempt_at=now))


class SmtpSender:
    def __init__(self, host: str, port: int, user: str, password: str, from_addr: str):
        self.host, self.port, self.user, self.password, self.from_addr = host, port, user, password, from_addr

    def __call__(self, n: Notification) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.from_addr, n.recipient, n.subject.replace("\n", " ")
        msg.set_content(n.body)
        with smtplib.SMTP(self.host, self.port, timeout=15) as s:
            s.starttls()
            if self.user:
                s.login(self.user, self.password)
            s.send_message(msg)


class WhatsAppSender:
    """WhatsApp Cloud API. Note: outside the 24h customer-service window Meta requires pre-approved templates."""

    def __init__(self, token: str, phone_id: str):
        self.token, self.phone_id = token, phone_id

    def __call__(self, n: Notification) -> None:
        payload = json.dumps({"messaging_product": "whatsapp", "to": n.recipient, "type": "text", "text": {"body": n.body}}).encode()
        req = urllib.request.Request(f"https://graph.facebook.com/v20.0/{self.phone_id}/messages", data=payload, method="POST",
                                     headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status >= 300:
                raise RuntimeError(f"WhatsApp API returned {r.status}")


def configured_senders() -> dict[str, Callable[[Notification], None]]:
    s, out = get_settings(), {}
    if s.smtp_host and s.smtp_from:
        out["email"] = SmtpSender(s.smtp_host, s.smtp_port, s.smtp_user, s.smtp_password, s.smtp_from)
    if s.whatsapp_token and s.whatsapp_phone_id:
        out["whatsapp"] = WhatsAppSender(s.whatsapp_token, s.whatsapp_phone_id)
    return out


def process_pending(db: Session, senders: dict[str, Callable], batch: int = 20) -> int:
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(Notification).where(
        Notification.status == "pending", Notification.next_attempt_at <= now, Notification.channel != "inapp")
        .order_by(Notification.id).limit(batch).with_for_update(skip_locked=True)).all()
    for n in rows:
        send = senders.get(n.channel)
        if send is None:
            apply_result(n, False, f"{n.channel} provider not configured", now)
            continue
        try:
            send(n)
            apply_result(n, True, None, now)
        except Exception as e:  # provider/network error: retry later
            apply_result(n, False, f"{type(e).__name__}: {e}", now)
    db.commit()
    return len(rows)


def enqueue_custom_cake(db: Session, req, event: str) -> None:
    """event: request_received | quote_ready (customer) ; staff bell on request_received."""
    cfg, gen = shop.get_group(db, "notifications"), shop.get_group(db, "general")
    base = get_settings().public_base_url.rstrip("/")
    now = datetime.now(timezone.utc)
    url = f"{base}/custom-cake/status?ref={req.reference}"
    subject, body = render_custom(event, req.reference, req.customer_name, gen["site_name"], url,
                                  price=req.quoted_price, currency=gen["currency_code"],
                                  valid_until=req.quote_valid_until.isoformat() if req.quote_valid_until else None, note=req.quote_note)
    if cfg["email_enabled"] and req.customer_email:
        db.add(Notification(channel="email", recipient=req.customer_email, subject=subject, body=body, created_at=now, next_attempt_at=now))
    if cfg["whatsapp_enabled"]:
        db.add(Notification(channel="whatsapp", recipient=req.customer_phone.lstrip("+"), subject="", body=body, created_at=now, next_attempt_at=now))
    if event == "request_received":
        db.add(Notification(channel="inapp", recipient="staff", subject=f"New custom cake request {req.reference}",
                            body=f"{req.customer_name} · {req.occasion} · needed {req.required_date}", status="sent",
                            created_at=now, next_attempt_at=now, sent_at=now))


def enqueue_account_email(db: Session, to: str, subject: str, body: str, link: str) -> None:
    """Verification / password-reset mail via the outbox. If e-mail is disabled nothing is sent; with
    DEV_LOG_EMAIL_LINKS=true the link is logged so local development still works."""
    import logging

    cfg = shop.get_group(db, "notifications")
    now = datetime.now(timezone.utc)
    if cfg["email_enabled"]:
        db.add(Notification(channel="email", recipient=to, subject=subject, body=body, created_at=now, next_attempt_at=now))
    elif get_settings().dev_log_email_links:
        logging.getLogger("account").warning("DEV e-mail link for %s: %s", to, link)
    else:
        logging.getLogger("account").warning("E-mail is disabled; an account e-mail to a customer was not sent")
