# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def generate_slug():
    return uuid.uuid4().hex[:10]


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(200), default='')
    role = db.Column(db.String(20), default='staff')  # 'admin' or 'staff'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    polls = db.relationship('Poll', backref='author', lazy=True)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    slug = db.Column(db.String(10), unique=True, default=generate_slug)
    duration = db.Column(db.Integer, default=60)  # duration in minutes
    is_closed = db.Column(db.Boolean, default=False)
    chosen_option_id = db.Column(db.Integer, db.ForeignKey('poll_option.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    options = db.relationship('PollOption', backref='poll', lazy=True,
                              cascade='all, delete-orphan',
                              order_by='PollOption.datetime',
                              foreign_keys='PollOption.poll_id')
    chosen_option = db.relationship('PollOption', foreign_keys=[chosen_option_id],
                                    post_update=True)

    def best_option(self):
        """Return the option with the most 'yes' votes."""
        best = None
        best_count = -1
        for opt in self.options:
            yes_count = sum(1 for v in opt.votes if v.choice == 'yes')
            if yes_count > best_count:
                best_count = yes_count
                best = opt
        return best

    def participants(self):
        """Return list of unique participant names."""
        names = set()
        for opt in self.options:
            for vote in opt.votes:
                names.add(vote.participant_name)
        return sorted(names)


class PollOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)
    label = db.Column(db.String(100), default='')

    votes = db.relationship('Vote', backref='option', lazy=True,
                            cascade='all, delete-orphan')


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_option_id = db.Column(db.Integer, db.ForeignKey('poll_option.id'), nullable=False)
    participant_name = db.Column(db.String(100), nullable=False)
    choice = db.Column(db.String(10), nullable=False)  # 'yes', 'no', 'maybe'

    __table_args__ = (
        db.UniqueConstraint('poll_option_id', 'participant_name',
                            name='uq_vote_option_participant'),
    )


class Setting(db.Model):
    """Instance setting edited on /admin/settings. Overrides the environment variable of the same name."""
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(500), default='')
