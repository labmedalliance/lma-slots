# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
from flask import Blueprint, render_template

about_bp = Blueprint('about', __name__)


@about_bp.route('/about')
def about():
    """Credits, licence and source offer (AGPL section 13). Required by NOTICE."""
    return render_template('about.html')
