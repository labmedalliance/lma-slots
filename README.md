# LMA Slots

Self-hosted scheduling polls, built with Flask. Organizers propose time slots in a weekly calendar; participants
vote through a share link without an account. A result matrix shows the best slot.

Powered by [LabMed Alliance](https://labmedalliance.com).

## Features

- Calendar-based slot creation on a 15-minute grid, overlapping slots side by side
- Public voting page with yes / maybe / no, calendar or table view, vote updates by name
- Result matrix with best option; organizer picks the final date and closes the poll
- Times stored in UTC, shown in each visitor's local time zone
- German and English UI
- Admin and staff roles, user management, optional e-mail notification on new votes
- Settings page for admins: public address, default language, own name and logo, SMTP with test mail
- CSRF protection, rate limiting on login and voting, unguessable poll links

## Quick start

Requires Python 3.10 or later.

```bash
git clone https://github.com/labmedalliance/lma-slots.git
cd lma-slots
uv venv && uv pip install -r requirements.txt
.venv/bin/python init_admin.py <username> <password>
.venv/bin/flask --app app run --port 8110   # http://127.0.0.1:8110
```

For production, run it behind a reverse proxy with gunicorn:

```bash
.venv/bin/gunicorn -w 2 -b 127.0.0.1:8110 app:app
```

The SQLite database (`instance/doodle.db`) and sessions live in `instance/`, which is never committed.

## Configuration

Admins set the most important options on the **Settings** page (`/admin/settings`): public address, default
language, organization name and logo, and SMTP, including a test mail. Values saved there take precedence over environment variables.

Everything can also be set through environment variables; see [`.env.example`](.env.example). The app does not
read `.env` itself, so set them in your process manager (systemd, supervisord, …). An empty field on the settings
page falls back to the environment variable, then to the default.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Session signing key. If unset, a random key is created once in `instance/.secret_key`. |
| `BASE_URL` | Public URL, used for links in notification mails. Falls back to the request URL. |
| `DEFAULT_LANGUAGE` | `de` (default) or `en`. Visitors can still switch. |
| `ORG_NAME` | Organization name shown in the header instead of "LMA Slots". |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` | Optional mail notifications to poll owners. |
| `SETTINGS_KEY` | Key for encrypting the SMTP password saved on the settings page. Default: `instance/.settings_key`. |
| `SMTP_SECURITY` | `starttls`, `ssl` or `none`. Default: `starttls` when user and password are set. |

An SMTP password saved on the settings page is stored encrypted (Fernet, AES-128 + HMAC) in the database. The key
comes from `SETTINGS_KEY` or, if unset, from `instance/.settings_key`, created on first use. A copy of the database
alone does not reveal the password. Anyone with access to both the database and the key can decrypt it, so for
real separation set `SETTINGS_KEY` in your process manager: `instance/` holds the database *and* the key file, and
backups usually include both. If the key changes, the settings page asks you to enter the password again.

### Your own name and logo

On the settings page you can set your organization's name and upload a logo (PNG, JPG or WebP, up to 512 KB).
Both replace "LMA Slots" and the LMA mark in the header and in the page titles. The logo is stored in
`instance/branding/`. The *Powered by LabMed Alliance* credit in the footer and the `/about` page stay as they are.

Branding set this way does not count as a modification (NOTICE, term 4): the instance remains an unmodified copy
of LMA Slots, with no need to rename it or replace the icons.

## Who built it

LMA Slots was designed and developed by **Janne Cadamuro / LabMed Alliance Inc.**

Copyright © 2026 Janne Cadamuro / LabMed Alliance Inc.

The same information is shown in the app: every page footer carries the *Powered by LabMed Alliance* credit and
links to `/about`, which states the authors, the licence and the link to the source code. These values are
hard-coded in [`attribution.py`](attribution.py), not stored in the database, so no admin setting can remove them.

## License

LMA Slots is free and open-source software under the **GNU Affero General Public License v3.0 or later**
(`AGPL-3.0-or-later`), with additional terms under AGPL section 7. The licence text is in [LICENSE](LICENSE), the
additional terms are in [NOTICE](NOTICE).

You may:

- run LMA Slots for yourself or your organization, commercially or not;
- study the source, adapt it and build on it;
- pass it on, modified or unmodified.

On these conditions:

- **Share alike.** Anything you build on it must be released under the AGPL as well.
- **Also when you only host it.** If you run a modified version as a web service, offer its users the source code
  (AGPL section 13). Point `SOURCE_URL` in `attribution.py` at your own repository.
- **Keep the LabMed Alliance credit.** The *Powered by LabMed Alliance* credit in the footer and the `/about` page
  must stay visible on every page (NOTICE, term 1). Add your own credits next to it; do not remove the original.
- **Mark your changes.** Say that your version is modified, and do not present it as the original or as endorsed
  by LabMed Alliance (NOTICE, term 2).
- **Own branding is fine.** Set your organization's name and logo on the settings page; the instance still counts
  as unmodified (NOTICE, term 4).
- **New name for modified versions.** "LabMed Alliance", "LMA", "LMA Slots" and the LMA logo are not licensed
  (NOTICE, term 3). Unmodified copies may run as *LMA Slots*. A modified version needs its own name and icons;
  it may call itself "based on LMA Slots". The logo and the icons in `static/img/` are not covered by the AGPL.
- **No warranty.** The software is provided as is.

### Built on

| Component | Licence |
|---|---|
| Flask | BSD-3-Clause |
| Flask-SQLAlchemy | BSD-3-Clause |
| Flask-Session | BSD-3-Clause |
| Flask-WTF | BSD-3-Clause |
| Flask-Limiter | MIT |
| Gunicorn | MIT |
| cryptography | Apache-2.0 OR BSD-3-Clause |

## Contributing

Issues and pull requests are welcome. Code, comments and commit messages are in English. By contributing you
agree that your contribution is licensed under the same terms (AGPL-3.0-or-later with the NOTICE terms).
