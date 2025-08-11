from flask import Blueprint, render_template
import plotly.graph_objs as go
import plotly.io as pio
from datetime import datetime
from ..utils.db import Database

bp = Blueprint('main', __name__)
db = Database()


@bp.route('/', methods=['GET'])
# @login_required_custom
def dashboard():
    domains = db.get_domains()
    logs = db.get_change_logs(limit=50)
    # Validação dos logs para evitar erro de strftime
    for log in logs:
        if 'message' not in log or log['message'] is None:
            log['message'] = ''
        if 'created_at' in log and not isinstance(log['created_at'], datetime):
            try:
                log['created_at'] = datetime.fromisoformat(str(log['created_at']))
            except Exception:
                log['created_at'] = None
        elif 'created_at' not in log:
            log['created_at'] = None
    # Exemplo de gráfico Plotly
    x = [log['created_at'] for log in logs]
    y = list(range(len(logs)))
    fig = go.Figure([go.Scatter(x=x, y=y, mode='lines+markers')])
    plot_html = pio.to_html(fig, full_html=False)
    return render_template('dashboard.html', domains=domains, logs=logs, plot_html=plot_html)

# @bp.route('/')
# def index():
#     return render_template('index.html')
