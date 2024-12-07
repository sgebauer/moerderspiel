from email.message import EmailMessage
from smtplib import SMTP, LMTP

from moerderspiel import config


def send_message(to: str, subject: str, body: str, attachment: bytes = None, attachment_type: str = 'application',
                 attachment_subtype: str = 'pdf', attachment_filename: str = None):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = config.EMAIL_FROM
    msg['To'] = to
    msg.set_content(body)
    if attachment:
        msg.add_attachment(attachment, maintype=attachment_type, subtype=attachment_subtype,
                           filename=attachment_filename)

    if config.EMAIL_SMTP_HOST.startswith('/'):
        with LMTP(config.EMAIL_SMTP_HOST) as lmtp:
            lmtp.send_message(msg)
            lmtp.quit()
    else:
        with SMTP(config.EMAIL_SMTP_HOST, port=int(config.EMAIL_SMTP_PORT)) as smtp:
            smtp.starttls()
            smtp.ehlo(config.EMAIL_HELO_HOSTNAME)
            smtp.send_message(msg)
            smtp.quit()


def send_confirmation_message(address: str, url: str, game_title: str):
    send_message(
        subject=f"Mörderspiel \"{game_title}\": Adresse bestätigen",
        to=address,
        body=f"Du hast dich für das Mörderspiel \"{game_title}\" angemeldet.\n"
             "Bevor du Benachrichtigungen per E-Mail bekommst, musst du deine E-Mail-Adresse bestätigen.\n"
             f"Klicke dazu auf den folgenden Link:\n\n{url}"
    )


def send_mission_update(address: str, pdf_path: str, game_title: str):
    with open(pdf_path, "rb") as file:
        send_message(
            subject=f"Mörderspiel \"{game_title}\": Neue Aufträge",
            to=address,
            body="Im Anhang findest du deine neuen Aufträge.",
            attachment=file.read(),
            attachment_type='application',
            attachment_subtype='pdf',
            attachment_filename='missions.pdf'
        )
