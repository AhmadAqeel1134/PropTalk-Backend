"""
Notification Service — SMS (via Twilio) and Email (via SMTP) for showing confirmations.
Both are fire-and-forget; failures are logged, never surface to the caller.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


# ─── SMS via Twilio ───────────────────────────────────────────────────

async def send_showing_sms(
    to_phone: str,
    from_phone: str,
    showing: Dict,
    agent_name: str,
    company_name: str,
) -> bool:
    """
    Send a confirmation SMS from the voice agent's own Twilio number.
    `from_phone` is the voice agent's Twilio number (already in E.164).
    Returns True on success, False on failure (never raises).
    """
    logger.info(
        f"📱 SMS ATTEMPT  |  from={from_phone!r}  →  to={to_phone!r}  |  "
        f"agent={agent_name}  company={company_name}  |  "
        f"showing_data={showing}"
    )

    if not from_phone or not from_phone.strip():
        logger.error("❌ SMS ABORTED — from_phone is empty/None. Voice agent has no Twilio number in context.")
        return False
    if not to_phone or not to_phone.strip():
        logger.error("❌ SMS ABORTED — to_phone is empty/None. Caller phone not resolved.")
        return False

    try:
        from app.services.twilio_service.client import get_twilio_client
        import asyncio

        property_addr = showing.get("property_address") or "your requested property"
        scheduled = showing.get("scheduled_start", "")
        dt = _format_friendly_datetime(scheduled)
        visit_type = (showing.get("visit_type") or "showing").replace("_", " ").title()

        body = (
            f"Hi {showing.get('caller_name') or showing.get('contact_name') or 'there'}! "
            f"Your {visit_type} at {property_addr} is set for {dt}. "
            f"This was arranged by {agent_name}"
            f"{' at ' + company_name if company_name else ''}. "
            f"Reply to this number if you need to reschedule. "
            f"— {company_name or 'PropTalk'}"
        )

        logger.info(f"📱 SMS BODY ({len(body)} chars): {body[:200]}...")

        client = get_twilio_client()
        loop = asyncio.get_event_loop()
        message = await loop.run_in_executor(
            None,
            lambda: client.messages.create(body=body, from_=from_phone, to=to_phone),
        )
        logger.info(f"✅ SMS SENT  |  sid={message.sid}  status={message.status}  from={from_phone}  to={to_phone}")
        return True
    except Exception as e:
        logger.error(
            f"❌ SMS FAILED  |  from={from_phone!r}  to={to_phone!r}  |  "
            f"error_type={type(e).__name__}  error={e}",
            exc_info=True,
        )
        return False


# ─── Email via SMTP ───────────────────────────────────────────────────

async def send_showing_email(
    to_email: str,
    showing: Dict,
    agent_name: str,
    company_name: str,
) -> bool:
    """
    Send a styled HTML confirmation email.
    Returns True on success, False on failure (never raises).
    """
    logger.info(
        f"📧 EMAIL ATTEMPT  |  from={settings.SENDER_EMAIL!r} ({settings.SENDER_NAME!r})  →  to={to_email!r}  |  "
        f"smtp={settings.SMTP_HOST}:{settings.SMTP_PORT}  |  "
        f"password_set={'YES' if settings.SENDER_EMAIL_PASSWORD else 'NO'}  |  "
        f"agent={agent_name}  company={company_name}  |  "
        f"showing_data={showing}"
    )

    if not to_email or not to_email.strip():
        logger.error("❌ EMAIL ABORTED — to_email is empty/None.")
        return False

    if not all([settings.SMTP_HOST, settings.SENDER_EMAIL, settings.SENDER_EMAIL_PASSWORD]):
        logger.warning(
            f"⚠️ EMAIL ABORTED — SMTP not configured  |  "
            f"SMTP_HOST={settings.SMTP_HOST!r}  SENDER_EMAIL={settings.SENDER_EMAIL!r}  "
            f"PASSWORD_SET={'YES' if settings.SENDER_EMAIL_PASSWORD else 'NO'}"
        )
        return False

    try:
        import asyncio

        visitor = showing.get("caller_name") or showing.get("contact_name") or "Valued Client"
        property_addr = showing.get("property_address") or "your requested property"
        scheduled = showing.get("scheduled_start", "")
        dt = _format_friendly_datetime(scheduled)
        visit_type = (showing.get("visit_type") or "showing").replace("_", " ").title()
        status = (showing.get("status") or "requested").title()

        subject = f"Your {visit_type} Confirmation — {property_addr}"

        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1a2e;">
          <div style="background: linear-gradient(135deg, #7c3aed, #4f46e5); padding: 28px 24px; border-radius: 16px 16px 0 0;">
            <h1 style="color: #fff; font-size: 20px; margin: 0;">Your {visit_type} is Confirmed</h1>
            <p style="color: rgba(255,255,255,0.85); font-size: 13px; margin: 6px 0 0;">Arranged by {agent_name}{' — ' + company_name if company_name else ''}</p>
          </div>
          <div style="background: #fff; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 16px 16px;">
            <p style="font-size: 15px; line-height: 1.5;">Hi <strong>{visitor}</strong>,</p>
            <p style="font-size: 15px; line-height: 1.5;">Here are your visit details:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
              <tr><td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Property</td><td style="padding: 8px 0; font-weight: 600;">{property_addr}</td></tr>
              <tr><td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Date &amp; Time</td><td style="padding: 8px 0; font-weight: 600;">{dt}</td></tr>
              <tr><td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Type</td><td style="padding: 8px 0;">{visit_type}</td></tr>
              <tr><td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Status</td><td style="padding: 8px 0;">{status}</td></tr>
            </table>
            <p style="font-size: 13px; color: #6b7280; line-height: 1.5;">If you need to reschedule or cancel, simply reply to this email or call us back.</p>
            <p style="font-size: 14px; margin-top: 20px;">Best regards,<br><strong>{agent_name}</strong>{' — ' + company_name if company_name else ''}</p>
          </div>
          <p style="text-align: center; font-size: 11px; color: #9ca3af; margin-top: 12px;">Sent via PropTalk</p>
        </div>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))

        logger.info(f"📧 EMAIL SENDING  |  subject={subject!r}  smtp={settings.SMTP_HOST}:{settings.SMTP_PORT}")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send, msg)
        logger.info(f"✅ EMAIL SENT  |  from={settings.SENDER_EMAIL}  →  to={to_email}  subject={subject!r}")
        return True
    except Exception as e:
        logger.error(
            f"❌ EMAIL FAILED  |  from={settings.SENDER_EMAIL!r}  to={to_email!r}  "
            f"smtp={settings.SMTP_HOST}:{settings.SMTP_PORT}  |  "
            f"error_type={type(e).__name__}  error={e}",
            exc_info=True,
        )
        return False


def _smtp_send(msg: MIMEMultipart) -> None:
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.SENDER_EMAIL, settings.SENDER_EMAIL_PASSWORD)
        server.send_message(msg)


# ─── shared helpers ───────────────────────────────────────────────────

def _format_friendly_datetime(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%A, %B %d at %I:%M %p")
    except Exception:
        return iso_str or "TBD"
