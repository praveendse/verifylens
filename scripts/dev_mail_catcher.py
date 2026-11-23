"""Local development only: a fake mail server that prints emails instead of sending them.

    python -m scripts.dev_mail_catcher          # listens on 127.0.0.1:1025

Point the app at it with SMTP_HOST=127.0.0.1, SMTP_PORT=1025, SMTP_STARTTLS=false.
Never use in production: it accepts any message and keeps nothing.
"""
import socketserver


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
                while (line := self.rfile.readline().decode(errors="replace")) not in (".\r\n", ".\n", ""):
                    lines.append(line.rstrip("\r\n"))
                print("\n" + "=" * 70 + "\n" + "\n".join(lines) + "\n" + "=" * 70, flush=True)
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
