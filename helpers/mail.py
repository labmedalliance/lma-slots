# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
import smtplib
from flask import request
from helpers.settings import get_setting
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid, parseaddr


def send_vote_notification(poll, participant_name, is_update):
    """Send email to poll author when a vote is submitted."""
    author = poll.author
    if not author.email:
        return

    base_url = (get_setting('base_url') or request.url_root).rstrip('/')

    action = 'aktualisiert' if is_update else 'abgestimmt'

    # Build summary
    participants = poll.participants()
    yes_summary = []
    for opt in poll.options:
        yes_count = sum(1 for v in opt.votes if v.choice == 'yes')
        yes_summary.append(f"  {opt.datetime.strftime('%d.%m.%Y %H:%M')}: {yes_count}x Ja")

    summary_text = '\n'.join(yes_summary)

    subject = f'LMA Slots: {participant_name} hat bei "{poll.title}" {action}'
    body = f"""Hallo {author.username},

{participant_name} hat bei deiner Umfrage "{poll.title}" {action}.

Aktueller Stand ({len(participants)} Teilnehmer):
{summary_text}

Zur Umfrage:
{base_url}/polls/{poll.id}

-- LMA Slots"""

    try:
        send_mail(author.email, subject, body)
    except Exception as e:
        print(f'Mail error: {e}')


def send_mail(to_addr, subject, body):
    """Send a plain-text mail with the current SMTP settings. Raises on failure."""
    smtp_host = get_setting('smtp_host', 'localhost')
    smtp_port = int(get_setting('smtp_port', '25'))
    smtp_user = get_setting('smtp_user')
    smtp_pass = get_setting('smtp_pass')
    # Without an explicit choice: STARTTLS when logging in, plain otherwise.
    security = get_setting('smtp_security') or ('starttls' if smtp_user and smtp_pass else 'none')

    msg = MIMEMultipart()
    msg['From'] = get_setting('smtp_from') or smtp_user or 'noreply@localhost'
    msg['To'] = to_addr
    msg['Subject'] = subject
    # Many providers reject or junk mail without these headers.
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=parseaddr(msg['From'])[1].rpartition('@')[2] or None)
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    smtp_class = smtplib.SMTP_SSL if security == 'ssl' else smtplib.SMTP
    with smtp_class(smtp_host, smtp_port, timeout=15) as server:
        if security == 'starttls':
            server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)
