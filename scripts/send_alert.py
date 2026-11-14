#!/usr/bin/env python3
"""
Self-contained SMTP alert sender for the IOFlow health monitor.

Deliberately uses ONLY the Python standard library so it can run as a root
systemd service without the project virtualenv, and so it keeps working even
when the application (and its dependencies) is the thing that is down.

SMTP credentials are read from the application's backend/.env file so alerting
shares the same mailbox the app already uses (MAIL_SERVER / EMAIL_USER /
EMAIL_PASS / FROM_EMAIL), matching backend/utils/email_service.py
(port 587 + STARTTLS).

Usage:
    send_alert.py --subject "..." --to "a@x.com,b@y.com" [--body-file FILE]
    echo "body text" | send_alert.py --subject "..." --to "a@x.com"

Environment overrides (used by health_monitor.sh):
    PROJECT_DIR      project root containing backend/.env (default: parent of this script's dir)
    ALERT_RECIPIENTS comma-separated default recipients when --to is omitted
    MAIL_SERVER / EMAIL_USER / EMAIL_PASS / FROM_EMAIL / MAIL_PORT
                     override values from backend/.env if set in the environment

Exit codes: 0 sent, 2 misconfigured (no recipients / no SMTP server), 3 send error.
"""
import argparse
import os
import smtplib
import ssl
import sys
from email.mime.text import MIMEText


def parse_env_file(path):
    """Minimal KEY=VALUE .env parser (no external deps)."""
    values = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key:
                    values[key] = val
    except FileNotFoundError:
        pass
    return values


def get_setting(env_values, name, default=None):
    """Environment takes precedence over the .env file, then default."""
    if os.environ.get(name):
        return os.environ[name]
    if env_values.get(name):
        return env_values[name]
    return default


def main():
    parser = argparse.ArgumentParser(description="Send an IOFlow health alert email.")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--to", default=os.environ.get("ALERT_RECIPIENTS", ""),
                        help="Comma-separated recipients (default: $ALERT_RECIPIENTS)")
    parser.add_argument("--body-file", help="File to read the body from (default: stdin)")
    args = parser.parse_args()

    recipients = [r.strip() for r in args.to.split(",") if r.strip()]
    if not recipients:
        sys.stderr.write("send_alert: no recipients (pass --to or set ALERT_RECIPIENTS)\n")
        return 2

    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as fh:
            body = fh.read()
    else:
        body = sys.stdin.read() if not sys.stdin.isatty() else ""

    project_dir = os.environ.get(
        "PROJECT_DIR",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    env_values = parse_env_file(os.path.join(project_dir, "backend", ".env"))

    smtp_server = get_setting(env_values, "MAIL_SERVER")
    smtp_user = get_setting(env_values, "EMAIL_USER")
    smtp_pass = get_setting(env_values, "EMAIL_PASS")
    smtp_port = int(get_setting(env_values, "MAIL_PORT", "587"))
    from_email = get_setting(env_values, "FROM_EMAIL") or smtp_user or "noreply@ioflow.com"

    if not smtp_server:
        sys.stderr.write("send_alert: MAIL_SERVER not configured in backend/.env\n")
        return 2

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = args.subject
    msg["From"] = from_email
    msg["To"] = ", ".join(recipients)

    try:
        if smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=30) as server:
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg, from_email, recipients)
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.starttls(context=ssl.create_default_context())
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg, from_email, recipients)
    except Exception as exc:  # noqa: BLE001 - report any send failure to the monitor log
        sys.stderr.write(f"send_alert: failed to send via {smtp_server}:{smtp_port}: {exc}\n")
        return 3

    sys.stderr.write(f"send_alert: sent '{args.subject}' to {', '.join(recipients)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
