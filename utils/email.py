import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import BackgroundTasks
from config import SMTP_EMAIL, SMTP_PASSWORD, SMTP_PORT, SMTP_SERVER

def generate_otp(length: int = 6) -> str:
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def send_otp_email(email: str, otp: str):
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Filmo Authentication <{SMTP_EMAIL}>"
        msg["To"] = email
        msg["Subject"] = "Your OTP"

        # Plain-text fallback (IMPORTANT)
        text = f"""
Your OTP is: {otp}

This code is valid for 5 minutes.
If you didn’t request this, ignore this email.
"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Your OTP</title>
</head>
<body style="margin:0; padding:0; background:#f4f6f8; font-family:Arial, Helvetica, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:40px 0;">
        <table width="420" cellpadding="0" cellspacing="0"
          style="background:#ffffff; border-radius:8px; box-shadow:0 4px 12px rgba(0,0,0,0.08);">
          
          <tr>
            <td style="padding:24px; text-align:center; border-bottom:1px solid #eee;">
              <h2 style="margin:0; color:#333;">Authentication Code</h2>
            </td>
          </tr>

          <tr>
            <td style="padding:30px; text-align:center;">
              <p style="margin:0 0 12px; color:#555; font-size:14px;">
                Use the following OTP to continue:
              </p>

              <div style="
                display:inline-block;
                margin:16px 0;
                padding:14px 24px;
                font-size:28px;
                letter-spacing:6px;
                font-weight:bold;
                color:#111;
                background:#f0f2f5;
                border-radius:6px;
              ">
                {otp}
              </div>

              <p style="margin:16px 0 0; color:#777; font-size:13px;">
                This code is valid for <b>5 minutes</b>.
              </p>
            </td>
          </tr>

          <tr>
            <td style="padding:16px; text-align:center; background:#fafafa;
              border-top:1px solid #eee; border-radius:0 0 8px 8px;">
              <p style="margin:0; font-size:12px; color:#999;">
                If you didn’t request this, you can safely ignore this email.
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
        
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)

    except Exception as e:
        print("Email error:", e)


def send_otp(bg: BackgroundTasks, email: str):
    otp = generate_otp()
    bg.add_task(send_otp_email, email, otp)
    return otp
