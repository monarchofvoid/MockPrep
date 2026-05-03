"""
VYAS — Email Service
Sends all transactional emails via Brevo (HTTP API).

WHY BREVO?
  • Works on Render free tier — uses HTTPS, not SMTP ports (465/587)
  • No custom domain required — send to ANY user's email immediately
  • Free tier: 300 emails/day, 9,000/month

Setup (5 minutes):
  1. Sign up free at https://app.brevo.com
  2. Go to SMTP & API → API Keys → Generate a new API key
  3. Set the env vars below in Render

Required .env variables:
  BREVO_API_KEY  — your Brevo API key   e.g. xkeysib-abc123...
  FROM_EMAIL     — any address you want  e.g. noreply@vyas.app
  FROM_NAME      — sender display name  (default: VYAS)
  FRONTEND_URL   — base URL of frontend  e.g. https://mock-prep-three.vercel.app
  OWNER_EMAIL    — inbox for contact messages

NOTE ON FROM_EMAIL:
  Brevo lets you use any from address without owning the domain.
  Emails will be delivered to any user — they may land in spam until
  you verify a domain, but the password reset flow will work.
"""

import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ── Config from environment ───────────────────────────────────────────────────

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
FROM_EMAIL    = os.getenv("FROM_EMAIL", "noreply@vyas.app").strip()
FROM_NAME     = os.getenv("FROM_NAME", "VYAS").strip()
FRONTEND_URL  = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
OWNER_EMAIL   = (os.getenv("OWNER_EMAIL", "") or FROM_EMAIL).strip()

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


# ── Core send helper ──────────────────────────────────────────────────────────

def _send(*, to: str, subject: str, html: str, reply_to: str = "") -> bool:
    """
    Send an HTML email via Brevo's HTTP API.
    Returns True on success, False on any failure — never raises.
    """
    if not BREVO_API_KEY:
        logger.warning("BREVO_API_KEY not configured. Email to <%s> skipped.", to)
        return False

    payload: dict = {
        "sender":      {"name": FROM_NAME, "email": FROM_EMAIL},
        "to":          [{"email": to}],
        "subject":     subject,
        "htmlContent": html,
    }
    if reply_to:
        payload["replyTo"] = {"email": reply_to}

    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        BREVO_ENDPOINT,
        data=data,
        headers={
            "api-key":      BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            logger.info(
                "Email sent via Brevo → %s | messageId: %s | subject: %s",
                to, body.get("messageId"), subject,
            )
            return True

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        logger.error("Brevo HTTP %s for <%s>: %s", exc.code, to, error_body)
        return False

    except Exception as exc:
        logger.error("Unexpected error sending email to %s: %s", to, exc)
        return False


# ── Password reset email ──────────────────────────────────────────────────────

def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 16px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#141414;border:1px solid rgba(212,168,67,0.2);border-radius:12px;overflow:hidden;max-width:520px;width:100%;">
        <tr>
          <td style="padding:28px 36px 22px;border-bottom:1px solid rgba(212,168,67,0.12);">
            <p style="margin:0;font-size:22px;font-weight:800;letter-spacing:0.1em;color:#d4a843;">VYAS</p>
            <p style="margin:4px 0 0;font-size:12px;color:#666;">Virtual Yield Assessment System</p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 36px;">
            <h1 style="margin:0 0 12px;font-size:20px;font-weight:700;color:#f0f0f0;">Reset your password</h1>
            <p style="margin:0 0 24px;font-size:14px;color:#aaa;line-height:1.7;">
              We received a request to reset the password for your VYAS account.
              Click the button below — the link expires in <strong style="color:#d4a843;">15&nbsp;minutes</strong>.
            </p>
            <table cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
              <tr>
                <td style="border-radius:8px;background:#d4a843;">
                  <a href="{reset_url}" style="display:inline-block;padding:13px 32px;font-size:14px;font-weight:700;color:#0a0a0a;text-decoration:none;letter-spacing:0.03em;">
                    Reset password &rarr;
                  </a>
                </td>
              </tr>
            </table>
            <p style="margin:0;font-size:12px;color:#555;line-height:1.75;">
              Didn't request a reset? Ignore this email — your password will not change.<br/><br/>
              Button not working? Paste this URL into your browser:<br/>
              <a href="{reset_url}" style="color:#d4a843;word-break:break-all;">{reset_url}</a>
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:18px 36px;border-top:1px solid rgba(212,168,67,0.08);">
            <p style="margin:0;font-size:11px;color:#444;">VYAS &middot; Intelligence &middot; Discipline &middot; Ascent</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return _send(to=to_email, subject="Reset your VYAS password", html=html)


# ── Contact form email ────────────────────────────────────────────────────────

def send_contact_email(name: str, email: str, message: str) -> bool:
    if not OWNER_EMAIL:
        logger.warning(
            "OWNER_EMAIL is not set — cannot deliver contact message from %s <%s>.", name, email
        )
        return False

    safe_name    = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_email   = email.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_message = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 16px;">
    <tr><td align="center">
      <table width="540" cellpadding="0" cellspacing="0"
             style="background:#141414;border:1px solid rgba(212,168,67,0.2);border-radius:12px;overflow:hidden;max-width:540px;width:100%;">
        <tr>
          <td style="padding:24px 32px 18px;border-bottom:1px solid rgba(212,168,67,0.1);">
            <p style="margin:0;font-size:20px;font-weight:800;letter-spacing:0.1em;color:#d4a843;">VYAS</p>
            <p style="margin:4px 0 0;font-size:12px;color:#555;">New contact form submission</p>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 32px 0;">
            <p style="margin:0 0 3px;font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#555;">From</p>
            <p style="margin:0;font-size:16px;font-weight:600;color:#f0f0f0;">{safe_name}</p>
            <p style="margin:3px 0 0;font-size:13px;color:#d4a843;">{safe_email}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 32px 28px;">
            <p style="margin:0 0 10px;font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#555;border-top:1px solid rgba(255,255,255,0.07);padding-top:18px;">Message</p>
            <p style="margin:0;font-size:14px;color:#ccc;line-height:1.8;white-space:pre-wrap;">{safe_message}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 32px;border-top:1px solid rgba(212,168,67,0.08);">
            <p style="margin:0;font-size:11px;color:#444;">Hit Reply to respond directly to {safe_name}.</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return _send(to=OWNER_EMAIL, subject=f"VYAS Contact: {name}", html=html, reply_to=email)
