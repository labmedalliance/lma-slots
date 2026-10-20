# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from models import db, Poll, PollOption, Vote
from routes.auth import login_required

polls_bp = Blueprint('polls', __name__)


@polls_bp.route('/')
@login_required
def index():
    polls = Poll.query.filter_by(user_id=session['user_id']).order_by(Poll.created_at.desc()).all()
    return render_template('polls/index.html', polls=polls)


@polls_bp.route('/polls/new', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        duration = int(request.form.get('duration', 60))

        if not title:
            flash(g.t['title_required'], 'error')
            return render_template('polls/form.html', poll=None)

        # Collect slots from JSON hidden field (calendar) or fallback to date/time fields
        slots_json = request.form.get('slots_json', '').strip()
        options = []

        if slots_json:
            try:
                slots = json.loads(slots_json)
                for s in slots:
                    dt = datetime.strptime(s, '%Y-%m-%dT%H:%M')
                    options.append(dt)
            except (json.JSONDecodeError, ValueError):
                pass

        if not options:
            flash(g.t['at_least_one_option'], 'error')
            return render_template('polls/form.html', poll=None)

        poll = Poll(title=title, description=description,
                    duration=duration, user_id=session['user_id'])
        db.session.add(poll)
        db.session.flush()

        for dt in sorted(options):
            opt = PollOption(poll_id=poll.id, datetime=dt)
            db.session.add(opt)

        db.session.commit()
        flash(g.t['poll_created'], 'success')
        return redirect(url_for('polls.detail', poll_id=poll.id))

    return render_template('polls/form.html', poll=None)


@polls_bp.route('/polls/<int:poll_id>')
@login_required
def detail(poll_id):
    poll = Poll.query.filter_by(id=poll_id, user_id=session['user_id']).first_or_404()
    share_url = url_for('vote.vote_page', slug=poll.slug, _external=True)

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

    return render_template('polls/detail.html', poll=poll, share_url=share_url,
                           participants=participants, matrix=matrix)


@polls_bp.route('/polls/<int:poll_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(poll_id):
    poll = Poll.query.filter_by(id=poll_id, user_id=session['user_id']).first_or_404()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        duration = int(request.form.get('duration', poll.duration or 60))

        if not title:
            flash(g.t['title_required'], 'error')
            return render_template('polls/form.html', poll=poll)

        slots_json = request.form.get('slots_json', '').strip()
        options = []

        if slots_json:
            try:
                slots = json.loads(slots_json)
                for s in slots:
                    dt = datetime.strptime(s, '%Y-%m-%dT%H:%M')
                    options.append(dt)
            except (json.JSONDecodeError, ValueError):
                pass

        if not options:
            flash(g.t['at_least_one_option'], 'error')
            return render_template('polls/form.html', poll=poll)

        poll.title = title
        poll.description = description
        poll.duration = duration

        PollOption.query.filter_by(poll_id=poll.id).delete()
        for dt in sorted(options):
            opt = PollOption(poll_id=poll.id, datetime=dt)
            db.session.add(opt)

        db.session.commit()
        flash(g.t['poll_updated'], 'success')
        return redirect(url_for('polls.detail', poll_id=poll.id))

    return render_template('polls/form.html', poll=poll)


@polls_bp.route('/polls/<int:poll_id>/close', methods=['POST'])
@login_required
def close(poll_id):
    poll = Poll.query.filter_by(id=poll_id, user_id=session['user_id']).first_or_404()
    poll.is_closed = not poll.is_closed
    if not poll.is_closed:
        poll.chosen_option_id = None
    db.session.commit()

    if poll.is_closed:
        flash(g.t['poll_closed_msg'], 'info')
    else:
        flash(g.t['poll_reopened'], 'info')

    return redirect(url_for('polls.detail', poll_id=poll.id))


@polls_bp.route('/polls/<int:poll_id>/choose/<int:option_id>', methods=['POST'])
@login_required
def choose_and_close(poll_id, option_id):
    poll = Poll.query.filter_by(id=poll_id, user_id=session['user_id']).first_or_404()
    option = PollOption.query.filter_by(id=option_id, poll_id=poll.id).first_or_404()
    poll.chosen_option_id = option.id
    poll.is_closed = True
    db.session.commit()
    flash(g.t['date_chosen_closed'], 'success')
    return redirect(url_for('polls.detail', poll_id=poll.id))


@polls_bp.route('/polls/<int:poll_id>/delete', methods=['POST'])
@login_required
def delete(poll_id):
    poll = Poll.query.filter_by(id=poll_id, user_id=session['user_id']).first_or_404()
    db.session.delete(poll)
    db.session.commit()
    flash(g.t['poll_deleted'], 'success')
    return redirect(url_for('polls.index'))
