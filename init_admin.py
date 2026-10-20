# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
"""Create the initial admin user. Run once after first deployment."""
import sys
from app import app
from models import db, User


def create_admin(username, password):
    with app.app_context():
        if User.query.filter_by(username=username).first():
            print(f'User "{username}" already exists.')
            return
        user = User(username=username, role='admin')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f'Admin user "{username}" created.')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python init_admin.py <username> <password>')
        sys.exit(1)
    create_admin(sys.argv[1], sys.argv[2])
