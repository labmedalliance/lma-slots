# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from models import db, Poll, Vote
from app import limiter, csrf

vote_bp = Blueprint('vote', __name__)


@vote_bp.route('/p/<slug>', methods=['GET', 'POST'])
@csrf.exempt  # public voting page, no login needed
@limiter.limit("20 per minute", methods=["POST"])
def vote_page(slug):
    poll = Poll.query.filter_by(slug=slug).first_or_404()

    if request.method == 'POST':
        if poll.is_closed:
            flash(g.t['poll_closed'], 'warning')
            return redirect(url_for('vote.vote_page', slug=slug))

        name = request.form.get('participant_name', '').strip()[:100]
        if not name:
            flash(g.t['name_required'], 'error')
            return redirect(url_for('vote.vote_page', slug=slug))

        is_update = False
        for option in poll.options:
            choice = request.form.get(f'choice_{option.id}', 'no')
            if choice not in ('yes', 'no', 'maybe'):
                choice = 'no'

            existing = Vote.query.filter_by(
                poll_option_id=option.id,
                participant_name=name
            ).first()

            if existing:
                existing.choice = choice
                is_update = True
            else:
                vote = Vote(
                    poll_option_id=option.id,
                    participant_name=name,
                    choice=choice
                )
                db.session.add(vote)

        db.session.commit()

        # Notify poll author
        try:
            from helpers.mail import send_vote_notification
            send_vote_notification(poll, name, is_update)
        except Exception:
            pass

        if is_update:
            flash(g.t['vote_updated'], 'success')
        else:
            flash(g.t['vote_success'], 'success')

        return redirect(url_for('vote.vote_page', slug=slug))

    # Build result matrix
    participants = poll.participants()
    matrix = {}
    for name in participants:
        matrix[name] = {}
        for option in poll.options:
            vote = Vote.query.filter_by(
                poll_option_id=option.id,
                participant_name=name
            ).first()
            matrix[name][option.id] = vote.choice if vote else 'no'

    best = poll.best_option()

    return render_template('vote/poll.html',
                           poll=poll,
                           participants=participants,
                           matrix=matrix,
                           best_option=best)
