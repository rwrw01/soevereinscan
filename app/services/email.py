import logging
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = "mail.publicvibes.nl"
SMTP_PORT = 465  # SMTPS
FROM_EMAIL = "info@publicvibes.nl"
FROM_NAME = "SoevereinScan"


async def send_report(email: str, pdf_bytes: bytes, scan_url: str) -> None:
    """Send PDF report via email. Fire-and-forget: email address is not stored."""
    msg = MIMEMultipart()
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = email
    msg["Subject"] = f"SoevereinScan rapport: {scan_url}"

    body = MIMEText(
        f"Bijgaand vindt u het SoevereinScan rapport voor {scan_url}.\n\n"
        f"Dit rapport toont welke diensten worden gebruikt en hoe soeverein "
        f"de digitale infrastructuur is.\n\n"
        f"U kunt het rapport ook online bekijken op "
        f"scan.publicvibes.nl/soeverein/\n\n"
        f"Met vriendelijke groet,\n"
        f"SoevereinScan \u2014 PublicVibes.nl\n\n"
        f"---\n"
        f"Uw emailadres is niet opgeslagen. Dit is een eenmalige verzending.",
        "plain",
        "utf-8",
    )
    msg.attach(body)

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename="soevereinscan-rapport.pdf",
    )
    msg.attach(attachment)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.send_message(msg)
        logger.info(
            "Report email sent to %s for %s", email[:3] + "***", scan_url
        )
    except Exception:
        logger.exception("Failed to send report email for %s", scan_url)
