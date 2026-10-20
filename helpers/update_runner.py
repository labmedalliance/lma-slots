# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
"""Install one release. Started by helpers/updater.py as a separate process.

Steps: back up the database, fetch the tag, check it out, install changed
requirements, test-import the app, then ask gunicorn to reload its workers.
If a step after the checkout fails, the previous version is restored.

The database in instance/ is never touched by git; schema changes of a new
version are applied when the app starts (db.create_all plus additive migrations).
Runs without Flask on purpose: it must keep working while the app restarts.
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

KEEP_BACKUPS = 10


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--pid', type=int, default=0)
    args = parser.parse_args()
    Runner(args).run()


class Runner:
    def __init__(self, args):
        self.args = args
        self.status_path = os.path.join(args.instance, 'update', 'status.json')
        self.status = self._load_status()
        self.previous = None
        self.deps_changed = False

    def _load_status(self):
        try:
            with open(self.status_path) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {'tag': self.args.tag, 'started': time.time()}

    def save(self, **fields):
        self.status.update(fields)
        tmp = self.status_path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(self.status, f)
        os.replace(tmp, self.status_path)

    def log(self, text):
        print(time.strftime('%Y-%m-%d %H:%M:%S'), self.args.tag, text, flush=True)

    def sh(self, *cmd, timeout=300):
        self.log('$ ' + ' '.join(cmd))
        result = subprocess.run(cmd, cwd=self.args.root, capture_output=True, text=True, timeout=timeout)
        output = (result.stdout + result.stderr).strip()
        if output:
            self.log(output[-2000:])
        if result.returncode != 0:
            raise StepError(output.splitlines()[-1] if output else f'{cmd[0]} failed')
        return result.stdout.strip()

    def run(self):
        try:
            self.save(state='running', step='backup')
            self.backup_database()

            self.save(step='fetch')
            tag = self.args.tag
            self.sh('git', 'fetch', '--quiet', '--force', '--no-tags', self.args.source,
                    f'refs/tags/{tag}:refs/tags/{tag}', timeout=120)

            self.save(step='checkout')
            self.previous = self.sh('git', 'rev-parse', 'HEAD')
            old_requirements = self.requirements_hash()
            self.sh('git', 'checkout', '--quiet', '--detach', f'refs/tags/{tag}')

            if self.requirements_hash() != old_requirements:
                self.save(step='dependencies')
                self.deps_changed = True
                self.install_requirements()

            self.save(step='verify')
            self.sh(sys.executable, '-c', 'import app', timeout=120)
        except Exception as e:
            self.rollback()
            self.save(state='failed', message=str(e)[:500], finished=time.time())
            self.log(f'failed: {e}')
            return

        if self.args.pid:
            self.save(step='restart')
            # HUP makes gunicorn start fresh workers with the new code and let the
            # old ones finish their requests: no downtime, sessions are kept.
            os.kill(self.args.pid, signal.SIGHUP)
            self.save(state='done', finished=time.time(), restart_needed=False)
        else:
            self.save(state='done', finished=time.time(), restart_needed=True)
        self.log('done')

    def backup_database(self):
        db_path = os.path.join(self.args.instance, 'doodle.db')
        if not os.path.exists(db_path):
            return
        backup_dir = os.path.join(self.args.instance, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M%S')
        target = os.path.join(backup_dir, f'doodle-{stamp}-before-{self.args.tag}.db')
        # SQLite's backup API copies a consistent snapshot even while the app writes.
        src, dst = sqlite3.connect(db_path), sqlite3.connect(target)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        self.save(backup=os.path.basename(target))
        self.log(f'database backed up to {target}')
        for old in sorted(glob.glob(os.path.join(backup_dir, 'doodle-*-before-*.db')))[:-KEEP_BACKUPS]:
            os.remove(old)

    def requirements_hash(self):
        try:
            with open(os.path.join(self.args.root, 'requirements.txt'), 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except OSError:
            return ''

    def install_requirements(self):
        uv = shutil.which('uv') or next((p for p in (os.path.expanduser('~/.local/bin/uv'),
                                                     os.path.expanduser('~/.cargo/bin/uv'))
                                         if os.path.exists(p)), None)
        if uv:
            self.sh(uv, 'pip', 'install', '--quiet', '-p', sys.executable, '-r', 'requirements.txt')
        else:
            self.sh(sys.executable, '-m', 'pip', 'install', '--quiet', '-r', 'requirements.txt')

    def rollback(self):
        if not self.previous:
            return
        try:
            self.sh('git', 'checkout', '--quiet', '--detach', self.previous)
            self.log('rolled back to ' + self.previous)
            if self.deps_changed:
                self.install_requirements()
            self.save(rolled_back=True)
        except Exception as e:
            self.log(f'rollback failed: {e}')
            self.save(rolled_back=False)


class StepError(RuntimeError):
    pass


if __name__ == '__main__':
    main()
