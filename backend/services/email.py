"""
VYAS — Email Service
Sends all transactional emails via Gmail SMTP (free, no domain required).

Functions:
  send_password_reset_email(to_email, reset_token)  →  forgot-password flow
  send_contact_email(name, email, message)           →  contact form flow

Required .env variables:
  GMAIL_USER         — your Gmail address          e.g. you@gmail.com
  GMAIL_APP_PASSWORD — 16-char App Password        NOT your normal Gmail password
                       Get it at: myaccount.google.com/apppasswords
                       (2-Step Verification must be ON first)
  FRONTEND_URL       — base URL of frontend        e.g. https://mock-prep-three.vercel.app
  OWNER_EMAIL        — inbox for contact messages  defaults to GMAIL_USER if unset
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# ── Config from environment ───────────────────────────────────────────────────

GMAIL_USER         = os.getenv("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
FRONTEND_URL       = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
OWNER_EMAIL        = (os.getenv("OWNER_EMAIL", "") or GMAIL_USER).strip()

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL


# ── Core send helper ──────────────────────────────────────────────────────────

def _send(*, to: str, subject: str, html: str, reply_to: str = "") -> bool:
    """
    Send an HTML email via Gmail SMTP SSL.
    Returns True on success, False on any failure — never raises.
    """
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.warning(
            "GMAIL_USER or GMAIL_APP_PASSWORD not configured. "
            "Email to <%s> skipped.", to
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"VYAS <{GMAIL_USER}>"
    msg["To"]      = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, to, msg.as_string())
        logger.info("Email sent → %s | subject: %s", to, subject)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail SMTP authentication failed. "
            "Make sure GMAIL_APP_PASSWORD is a 16-character App Password, "
            "NOT your regular Gmail password. "
            "Generate one at: myaccount.google.com/apppasswords"
        )
        return False

    except smtplib.SMTPRecipientsRefused as exc:
        logger.error("Recipient refused by Gmail: %s — %s", to, exc)
        return False

    except Exception as exc:
        logger.error("Unexpected error sending email to %s: %s", to, exc)
        return False


# ── Password reset email ──────────────────────────────────────────────────────

def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """
    Send a password-reset link to the user.
    `reset_token` is the RAW token (never the stored hash).
    The link expires in 15 minutes (enforced server-side).
    """
    reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;
             font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0a0a0a;padding:40px 16px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#141414;
                    border:1px solid rgba(212,168,67,0.2);
                    border-radius:12px;overflow:hidden;
                    max-width:520px;width:100%;">

        <!-- Header -->
        <tr>
          <td style="padding:28px 36px 22px;
                     border-bottom:1px solid rgba(212,168,67,0.12);">
            <p style="margin:0;font-size:22px;font-weight:800;
                      letter-spacing:0.1em;color:#d4a843;">VYAS</p>
            <p style="margin:4px 0 0;font-size:12px;color:#666;">
              Virtual Yield Assessment System
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px 36px;">
            <h1 style="margin:0 0 12px;font-size:20px;
                       font-weight:700;color:#f0f0f0;">
              Reset your password
            </h1>
            <p style="margin:0 0 24px;font-size:14px;
                      color:#aaa;line-height:1.7;">
              We received a request to reset the password for your VYAS account.
              Click the button below — the link expires in
              <strong style="color:#d4a843;">15&nbsp;minutes</strong>.
            </p>

            <!-- CTA button -->
            <table cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
              <tr>
                <td style="border-radius:8px;background:#d4a843;">
                  <a href="{reset_url}"
                     style="display:inline-block;padding:13px 32px;
                            font-size:14px;font-weight:700;
                            color:#0a0a0a;text-decoration:none;
                            letter-spacing:0.03em;">
                    Reset password &rarr;
                  </a>
                </td>
              </tr>
            </table>

            <p style="margin:0;font-size:12px;color:#555;line-height:1.75;">
              Didn't request a reset? Ignore this email —
              your password will not change.<br/><br/>
              Button not working? Paste this URL into your browser:<br/>
              <a href="{reset_url}"
                 style="color:#d4a843;word-break:break-all;">
                {reset_url}
              </a>
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:18px 36px;
                     border-top:1px solid rgba(212,168,67,0.08);">
            <p style="margin:0;font-size:11px;color:#444;">
              VYAS &middot; Intelligence &middot; Discipline &middot; Ascent
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return _send(
        to=to_email,
        subject="Reset your VYAS password",
        html=html,
    )


# ── Contact form email ────────────────────────────────────────────────────────

def send_contact_email(name: str, email: str, message: str) -> bool:
    """
    Forward a contact-form submission to the platform owner (OWNER_EMAIL).
    Sets reply_to = user's email so you can reply directly from your inbox.
    """
    if not OWNER_EMAIL:
        logger.warning(
            "OWNER_EMAIL is not set and GMAIL_USER is empty — "
            "cannot deliver contact message from %s <%s>.", name, email
        )
        return False

    # Escape user content for safe HTML rendering
    safe_name    = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_email   = email.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_message = (
        message
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;
             font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0a0a0a;padding:40px 16px;">
    <tr><td align="center">
      <table width="540" cellpadding="0" cellspacing="0"
             style="background:#141414;
                    border:1px solid rgba(212,168,67,0.2);
                    border-radius:12px;overflow:hidden;
                    max-width:540px;width:100%;">

        <!-- Header -->
        <tr>
          <td style="padding:24px 32px 18px;
                     border-bottom:1px solid rgba(212,168,67,0.1);">
            <p style="margin:0;font-size:20px;font-weight:800;
                      letter-spacing:0.1em;color:#d4a843;">VYAS</p>
            <p style="margin:4px 0 0;font-size:12px;color:#555;">
              New contact form submission
            </p>
          </td>
        </tr>

        <!-- Sender info -->
        <tr>
          <td style="padding:24px 32px 0;">
            <p style="margin:0 0 3px;font-size:10px;font-weight:700;
                      letter-spacing:0.1em;text-transform:uppercase;
                      color:#555;">From</p>
            <p style="margin:0;font-size:16px;font-weight:600;
                      color:#f0f0f0;">{safe_name}</p>
            <p style="margin:3px 0 0;font-size:13px;color:#d4a843;">
              {safe_email}
            </p>
          </td>
        </tr>

        <!-- Message -->
        <tr>
          <td style="padding:20px 32px 28px;">
            <p style="margin:0 0 10px;font-size:10px;font-weight:700;
                      letter-spacing:0.1em;text-transform:uppercase;color:#555;
                      border-top:1px solid rgba(255,255,255,0.07);
                      padding-top:18px;">Message</p>
            <p style="margin:0;font-size:14px;color:#ccc;
                      line-height:1.8;white-space:pre-wrap;">{safe_message}</p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:14px 32px;
                     border-top:1px solid rgba(212,168,67,0.08);">
            <p style="margin:0;font-size:11px;color:#444;">
              Hit Reply to respond directly to {safe_name}.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return _send(
        to=OWNER_EMAIL,
        subject=f"VYAS Contact: {name}",
        html=html,
        reply_to=email,
    )
