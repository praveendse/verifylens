"""Local development only: a fake mail server that prints emails instead of sending them.

    python -m scripts.dev_mail_catcher          # listens on 127.0.0.1:1025

Point the app at it with SMTP_HOST=127.0.0.1, SMTP_PORT=1025, SMTP_STARTTLS=false.
Never use in production: it accepts any message and keeps nothing.
"""
import socketserver
from email import message_from_bytes, policy


def render(raw: bytes) -> str:
    """Readable email: key headers plus the DECODED body. Long lines arrive
    quoted-printable encoded (e.g. "token=3D..." split over lines), which
    would break copied links if printed raw."""
    msg = message_from_bytes(raw, policy=policy.default)
    headers = [f"{name}: {msg[name]}" for name in ("From", "To", "Subject") if msg[name]]
    part = msg.get_body(preferencelist=("plain",)) or msg
    return "\n".join(headers) + "\n\n" + part.get_content().rstrip("\n")


class _Handler(socketserver.StreamRequestHandler):
    def _reply(self, line: str) -> None:
        self.wfile.write((line + "\r\n").encode())

    def handle(self) -> None:
        self._reply("220 dev-mail-catcher ready")
        while raw := self.rfile.readline():
            command = raw.decode(errors="replace").strip()
            verb = command.split(" ", 1)[0].upper()
            if verb in ("EHLO", "HELO"):
                self._reply("250 dev-mail-catcher")
            elif verb == "DATA":
                self._reply("354 end with <CRLF>.<CRLF>")
                lines = []
                while (line := self.rfile.readline()) not in (b".\r\n", b".\n", b""):
                    # SMTP dot-stuffing: a leading ".." stands for "."
                    lines.append(line[1:] if line.startswith(b"..") else line)
                print("\n" + "=" * 70 + "\n" + render(b"".join(lines)) + "\n" + "=" * 70, flush=True)
                self._reply("250 OK")
            elif verb == "QUIT":
                self._reply("221 bye")
                return
            else:  # MAIL FROM, RCPT TO, RSET, NOOP ...
                self._reply("250 OK")


if __name__ == "__main__":
    with socketserver.ThreadingTCPServer(("127.0.0.1", 1025), _Handler) as server:
        print("Fake mail server on 127.0.0.1:1025. Emails print here. Ctrl+C to stop.", flush=True)
        server.serve_forever()
