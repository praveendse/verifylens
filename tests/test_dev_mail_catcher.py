"""The local fake mail server must print emails decoded, so links can be copied."""
from email.message import EmailMessage

from app.services.password_reset_service import reset_email, reset_link
from scripts.dev_mail_catcher import render

TOKEN = "Ab3_" * 10 + "xyz"  # 43 chars, like a real token


def test_long_reset_link_is_printed_whole():
    link = reset_link("http://127.0.0.1:5173", TOKEN)
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = "noreply@x.test", "alice@example.com", "VerifyLens password reset"
    msg.set_content(reset_email(link, 15)[1])
    raw = msg.as_bytes()
    assert b"=3D" in raw  # the wire format really is encoded (quoted-printable)

    text = render(raw)
    assert link in text.splitlines()  # whole link on one line, no "3D", no soft breaks
    assert "Subject: VerifyLens password reset" in text
    assert "To: alice@example.com" in text
