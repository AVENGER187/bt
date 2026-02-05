import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import BackgroundTasks
from config import SMTP_EMAIL, SMTP_PASSWORD, SMTP_PORT, SMTP_SERVER
import logging

logger = logging.getLogger(__name__)

def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure OTP"""
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def send_otp_email(email: str, otp: str):
    """Send OTP email with HTML and plain text fallback"""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Filmo Authentication <{SMTP_EMAIL}>"
        msg["To"] = email
        msg["Subject"] = "Your Filmo Verification Code"

        # Plain-text fallback (IMPORTANT for accessibility)
        text = f"""
Your Filmo verification code is: {otp}

This code is valid for 5 minutes.

If you didn't request this code, please ignore this email.

---
Filmo Team
"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Verification Code</title>
</head>
<body style="margin:0; padding:0; background:#f4f6f8; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td align="center" style="padding:40px 20px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
          style="max-width:420px; background:#ffffff; border-radius:12px; box-shadow:0 4px 16px rgba(0,0,0,0.1);">
          
          <!-- Header -->
          <tr>
            <td style="padding:32px 24px 24px; text-align:center; border-bottom:1px solid #eee;">
              <h1 style="margin:0; color:#1a1a1a; font-size:24px; font-weight:600;">
                Verification Code
              </h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px 24px; text-align:center;">
              <p style="margin:0 0 20px; color:#666; font-size:15px; line-height:1.5;">
                Use the following code to verify your account:
              </p>

              <!-- OTP Box -->
              <div style="
                display:inline-block;
                margin:24px 0;
                padding:16px 32px;
                font-size:32px;
                letter-spacing:8px;
                font-weight:700;
                color:#1a1a1a;
                background:#f8f9fa;
                border:2px solid #e9ecef;
                border-radius:8px;
                font-family: 'Courier New', monospace;
              ">
                {otp}
              </div>

              <p style="margin:24px 0 0; color:#888; font-size:14px; line-height:1.6;">
                This code will expire in <strong style="color:#666;">5 minutes</strong>.<br>
                For security, don't share this code with anyone.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 24px; text-align:center; background:#fafbfc;
              border-top:1px solid #eee; border-radius:0 0 12px 12px;">
              <p style="margin:0; font-size:13px; color:#999; line-height:1.5;">
                If you didn't request this code, you can safely ignore this email.<br>
                Someone else may have entered your email by mistake.
              </p>
            </td>
          </tr>

        </table>
        
        <!-- Bottom text -->
        <p style="margin:24px 0 0; text-align:center; font-size:12px; color:#aaa;">
          © 2026 Filmo. All rights reserved.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""
        
        # Attach both versions (plain text first for better compatibility)
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        # Send email with timeout
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"OTP email sent successfully to {email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email to {email}: {e}", exc_info=True)
        return False


def send_otp(bg: BackgroundTasks, email: str) -> str:
    """
    Generate OTP and queue email sending in background.
    Returns the OTP for storage in database.
    """
    otp = generate_otp()
    bg.add_task(send_otp_email, email, otp)
    logger.info(f"OTP generated and email queued for {email}")
    return otp