from flask import Blueprint, render_template, redirect, url_for, flash
from datetime import datetime
from ..utils.db import Database

bp = Blueprint('log', __name__, url_prefix='/logs')
db = Database()


@bp.route('/')
def logs():
    logs = db.get_change_logs(limit=100)
    for log in logs:
        # Garante que o campo 'message' existe
        if 'message' not in log or log['message'] is None:
            log['message'] = ''
        # Garante que o campo 'created_at' existe e é datetime
        if 'created_at' in log and not isinstance(log['created_at'], datetime):
            try:
                log['created_at'] = datetime.fromisoformat(str(log['created_at']))
            except Exception:
                log['created_at'] = None
        elif 'created_at' not in log:
            log['created_at'] = None
    failover_count = sum('failover' in log['message'].lower() for log in logs)
    error_count = sum('error' in log['message'].lower() for log in logs)
    success_count = sum('success' in log['message'].lower() for log in logs)
    return render_template('logs.html', logs=logs, failover_count=failover_count, error_count=error_count,
                           success_count=success_count)


@bp.route('/delete/<int:log_id>', methods=['POST'])
def delete_log(log_id):
    try:
        db.delete_log(log_id)
        flash('Log excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir log: {str(e)}', 'danger')
    return redirect(url_for('logs'))
