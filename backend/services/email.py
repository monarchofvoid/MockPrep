"""
VYAS — Email Service
Sends transactional emails via the Resend HTTP API.
No extra SDK required — uses httpx (already a transitive dependency of FastAPI).

Environment variables required:
  RESEND_API_KEY   — Resend API key  (e.g. re_xxxxxxxxxxxx)
  FRONTEND_URL     — Base URL of the frontend (e.g. https://vyas.app or http://localhost:5173)
"""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL  = "https://api.resend.com/emails"
RESEND_API_KEY  = os.getenv("RESEND_API_KEY", "")
FRONTEND_URL    = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
OWNER_EMAIL     = os.getenv("OWNER_EMAIL", "")

# Sender address — swap for your verified domain once you go to production
FROM_ADDRESS = "VYAS <onboarding@resend.dev>"


def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """
    Send a password-reset link to *to_email*.
    Returns True on success, False on failure (never raises — callers must
    not reveal to the user whether the email was sent).

    Security note:
      - reset_token here is the RAW token (not the stored hash).
      - It is embedded in the URL as a query parameter; the backend will
        SHA-256-hash it again before comparing with the stored value.
    """
    if not RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY is not set — skipping email send. "
            "Token for manual testing: %s", reset_token
        )
        return False

    reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Reset your VYAS password</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="520" cellpadding="0" cellspacing="0"
               style="background:#141414;border:1px solid rgba(212,168,67,0.18);border-radius:12px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="padding:32px 40px 24px;border-bottom:1px solid rgba(212,168,67,0.12);">
              <p style="margin:0;font-size:22px;font-weight:800;letter-spacing:0.1em;color:#d4a843;">
                VYAS
              </p>
              <p style="margin:4px 0 0;font-size:12px;color:#666;letter-spacing:0.06em;">
                Virtual Yield Assessment System
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px;">
              <h1 style="margin:0 0 12px;font-size:20px;font-weight:700;color:#f0f0f0;">
                Reset your password
              </h1>
              <p style="margin:0 0 28px;font-size:14px;color:#aaa;line-height:1.7;">
                We received a request to reset the password for your VYAS account.
                Click the button below — the link expires in&nbsp;<strong style="color:#d4a843;">15&nbsp;minutes</strong>.
              </p>

              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-radius:8px;background:#d4a843;">
                    <a href="{reset_url}"
                       style="display:inline-block;padding:13px 32px;font-size:14px;
                              font-weight:700;color:#0a0a0a;text-decoration:none;
                              letter-spacing:0.04em;">
                      Reset password →
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:28px 0 0;font-size:12px;color:#555;line-height:1.7;">
                If you did not request a password reset, you can ignore this email —
                your password will not change.<br/><br/>
                If the button doesn't work, paste this URL into your browser:<br/>
                <a href="{reset_url}" style="color:#d4a843;word-break:break-all;">
                  {reset_url}
                </a>
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 40px;border-top:1px solid rgba(212,168,67,0.08);">
              <p style="margin:0;font-size:11px;color:#444;">
                VYAS · Intelligence · Discipline · Ascent
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    try:
        resp = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from":    FROM_ADDRESS,
                "to":      [to_email],
                "subject": "Reset your VYAS password",
                "html":    html_body,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        logger.info("Password reset email sent to %s (Resend id: %s)",
                    to_email, resp.json().get("id"))
        return True
    except httpx.HTTPStatusError as exc:
        logger.error("Resend HTTP error %s: %s", exc.response.status_code, exc.response.text)
        return False
    except Exception as exc:
        logger.error("Failed to send password reset email: %s", exc)
        return False


def send_contact_email(name: str, email: str, message: str) -> bool:
    """
    Forward a contact-form submission to the platform owner.
    reply_to is set to the user's email so the owner can reply directly.
    Returns True on success, False on failure (never raises).
    """
    if not RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY not set — skipping contact email send. "
            "From: %s <%s>", name, email
        )
        return False

    if not OWNER_EMAIL:
        logger.warning("OWNER_EMAIL not set — cannot deliver contact message.")
        return False

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>VYAS Contact Form</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="540" cellpadding="0" cellspacing="0"
               style="background:#141414;border:1px solid rgba(212,168,67,0.18);border-radius:12px;overflow:hidden;">

          <tr>
            <td style="padding:28px 36px 20px;border-bottom:1px solid rgba(212,168,67,0.1);">
              <p style="margin:0;font-size:20px;font-weight:800;letter-spacing:0.1em;color:#d4a843;">VYAS</p>
              <p style="margin:4px 0 0;font-size:12px;color:#555;">New contact form submission</p>
            </td>
          </tr>

          <tr>
            <td style="padding:28px 36px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding-bottom:20px;">
                    <p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#555;">From</p>
                    <p style="margin:0;font-size:15px;font-weight:600;color:#f0f0f0;">{name}</p>
                    <p style="margin:2px 0 0;font-size:13px;color:#d4a843;">{email}</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding-top:20px;border-top:1px solid rgba(255,255,255,0.06);">
                    <p style="margin:0 0 10px;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#555;">Message</p>
                    <p style="margin:0;font-size:14px;color:#ccc;line-height:1.75;white-space:pre-wrap;">{message}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding:16px 36px;border-top:1px solid rgba(212,168,67,0.08);">
              <p style="margin:0;font-size:11px;color:#444;">
                Reply to this email to respond directly to {name}.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    try:
        resp = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from":     FROM_ADDRESS,
                "to":       [OWNER_EMAIL],
                "reply_to": email,
                "subject":  f"VYAS Contact: {name}",
                "html":     html_body,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        logger.info("Contact email forwarded to owner (Resend id: %s)", resp.json().get("id"))
        return True
    except httpx.HTTPStatusError as exc:
        logger.error("Resend HTTP error %s: %s", exc.response.status_code, exc.response.text)
        return False
    except Exception as exc:
        logger.error("Failed to send contact email: %s", exc)
        return False
