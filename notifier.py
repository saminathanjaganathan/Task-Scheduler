"""Email notification sender for task execution results."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app


def send_notification(to_email, task_title, status, output, error):
    """Send email notification about task execution result."""
    smtp_server = current_app.config.get("MAIL_SERVER")
    smtp_port = current_app.config.get("MAIL_PORT", 587)
    smtp_user = current_app.config.get("MAIL_USERNAME")
    smtp_pass = current_app.config.get("MAIL_PASSWORD")
    from_email = current_app.config.get("MAIL_FROM", smtp_user)

    if not all([smtp_server, smtp_user, smtp_pass, to_email]):
        current_app.logger.warning(
            "Email not configured. Set MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD env vars."
        )
        return False

    subject = f"Task '{task_title}' - {'SUCCESS' if status == 'success' else 'FAILED'}"

    body = f"""
Task Execution Report
=====================
Task: {task_title}
Status: {status.upper()}

--- Output ---
{output if output else '(no output)'}
"""
    if error:
        body += f"""
--- Errors ---
{error}
"""

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, to_email, msg.as_string())
        current_app.logger.info(f"Notification sent to {to_email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {e}")
        return False
