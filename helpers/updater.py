# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
"""In-app updates from the GitHub releases of the source repository.

A release is a tag `vX.Y.Z` with release notes. The check result is cached in
`instance/update/`, the installation itself runs in `helpers/update_runner.py`
as a separate process, so it survives the restart it triggers.

Polls and votes live in `instance/doodle.db`, which git never touches. The
runner backs the database up before every update.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from flask import current_app
import attribution
from helpers.settings import get_stored, set_setting

CHECK_INTERVAL = 6 * 3600
TAG_PATTERN = re.compile(r'^v(\d+)\.(\d+)\.(\d+)$')


def parse_version(text):
    """Return (major, minor, patch) for '1.2.3' or 'v1.2.3', else None."""
    match = TAG_PATTERN.match(text if text.startswith('v') else 'v' + text)
    return tuple(int(n) for n in match.groups()) if match else None


def enabled():
    return os.environ.get('UPDATE_CHECK', 'on').lower() not in ('0', 'off', 'false', 'no')


def source_git_url():
    """Where updates are fetched from. Forks point SOURCE_URL at their own repo."""
    return os.environ.get('UPDATE_SOURCE') or attribution.SOURCE_URL.rstrip('/') + '.git'


def _github_repo():
    match = re.match(r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$', attribution.SOURCE_URL)
    return match.groups() if match else None


def _update_dir():
    path = os.path.join(current_app.instance_path, 'update')
    os.makedirs(path, exist_ok=True)
    return path


def _read_json(name):
    try:
        with open(os.path.join(_update_dir(), name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(name, data):
    path = os.path.join(_update_dir(), name)
    with open(path + '.tmp', 'w') as f:
        json.dump(data, f)
    os.replace(path + '.tmp', path)


def fetch_latest_release():
    """Ask GitHub for the newest release. Returns a dict or raises."""
    url = os.environ.get('UPDATE_RELEASES_URL')  # other hosts and tests
    if not url:
        repo = _github_repo()
        if not repo:
            raise RuntimeError('SOURCE_URL is not a GitHub repository')
        url = f'https://api.github.com/repos/{repo[0]}/{repo[1]}/releases/latest'
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': f'{attribution.APP_NAME}/{attribution.VERSION}',
    })
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.load(resp)
    tag = data.get('tag_name', '')
    if not parse_version(tag):
        raise RuntimeError(f'Unexpected release tag: {tag!r}')
    return {
        'tag': tag,
        'version': tag[1:],
        'name': data.get('name') or tag,
        'notes': data.get('body') or '',
        'url': data.get('html_url', ''),
        'published': data.get('published_at', ''),
    }


def get_update_info(force=False):
    """Return the cached check result, refreshed when older than CHECK_INTERVAL."""
    cache = _read_json('latest.json') or {}
    if enabled() and (force or time.time() - cache.get('checked', 0) > CHECK_INTERVAL):
        try:
            cache = {'checked': time.time(), 'release': fetch_latest_release(), 'error': ''}
        except urllib.error.HTTPError as e:
            if e.code != 404:  # 404: the repository has no release yet
                cache = {'checked': time.time(), 'release': cache.get('release'), 'error': str(e)[:200]}
            else:
                cache = {'checked': time.time(), 'release': None, 'error': ''}
        except Exception as e:  # network down, rate limit, no release yet
            cache = {'checked': time.time(), 'release': cache.get('release'), 'error': str(e)[:200]}
        _write_json('latest.json', cache)

    release = cache.get('release')
    current = parse_version(attribution.VERSION)
    available = bool(release and current and parse_version(release['tag']) > current)
    skipped = get_stored('update_skipped')
    return {
        'enabled': enabled(),
        'current': attribution.VERSION,
        'release': release,
        'available': available,
        'skipped': available and skipped == release['tag'],
        'error': cache.get('error', ''),
        'checked': cache.get('checked', 0),
    }


def skip(tag):
    set_setting('update_skipped', tag)


def _git(*args):
    return subprocess.run(['git', *args], cwd=current_app.root_path, capture_output=True, text=True, timeout=20)


def preflight():
    """Return a list of translation keys for problems that block an automatic update."""
    problems = []
    try:
        if _git('rev-parse', '--is-inside-work-tree').stdout.strip() != 'true':
            return ['update_problem_no_git']
    except (OSError, subprocess.TimeoutExpired):
        return ['update_problem_no_git']
    # Only tracked files count; instance/ and the venv are ignored by git.
    if _git('status', '--porcelain', '--untracked-files=no').stdout.strip():
        problems.append('update_problem_dirty')
    running = read_status()
    if running and running.get('state') == 'running' and time.time() - running.get('started', 0) < 900:
        problems.append('update_problem_running')
    return problems


def master_pid(environ):
    """PID of the gunicorn master that serves this request, or 0 when not under gunicorn."""
    if environ.get('SERVER_SOFTWARE', '').startswith('gunicorn'):
        return os.getppid()
    return 0


def read_status():
    return _read_json('status.json')


def start_install(tag, pid):
    """Start the runner in its own process group so the restart does not kill it."""
    update_dir = _update_dir()
    _write_json('status.json', {'state': 'running', 'step': 'start', 'tag': tag,
                                'from': attribution.VERSION, 'started': time.time(), 'message': ''})
    log = open(os.path.join(update_dir, 'update.log'), 'a')
    subprocess.Popen(
        [sys.executable, os.path.join(current_app.root_path, 'helpers', 'update_runner.py'),
         '--tag', tag, '--source', source_git_url(), '--root', current_app.root_path,
         '--instance', current_app.instance_path, '--pid', str(pid)],
        cwd=current_app.root_path, stdout=log, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True,
    )


def render_notes(text):
    """Render the small Markdown subset GitHub release notes use. Everything is escaped first."""
    from markupsafe import Markup, escape

    def inline(line):
        html = str(escape(line))
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
        return html

    out, in_list = [], False
    for raw in text.replace('\r\n', '\n').split('\n'):
        line = raw.strip()
        item = re.match(r'^[-*]\s+(.*)', line)
        if in_list and not item:
            out.append('</ul>')
            in_list = False
        if not line:
            continue
        heading = re.match(r'^#{1,6}\s+(.*)', line)
        if heading:
            out.append(f'<h4>{inline(heading.group(1))}</h4>')
        elif item:
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append(f'<li>{inline(item.group(1))}</li>')
        else:
            out.append(f'<p>{inline(line)}</p>')
    if in_list:
        out.append('</ul>')
    return Markup('\n'.join(out))
