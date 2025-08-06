from main import app
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from utils.db import Database
from utils.monitor import LinkMonitor
from utils.cloudflare import CloudflareAPI
import plotly.graph_objs as go
import plotly.io as pio
import os
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps

load_dotenv()

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

# Classe de usuário para Flask-Login
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    # Aqui você pode implementar busca no banco de dados
    # Por enquanto, usando usuário fixo
    if user_id == '1':
        return User('1', 'admin')
    return None

# Decorator para verificar autenticação
def login_required_custom(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

db = Database()
cloudflare = None
try:
    cloudflare = CloudflareAPI()
except Exception as e:
    cloudflare_error = str(e)
else:
    cloudflare_error = None
monitor = LinkMonitor(db, cloudflare) if cloudflare else None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Aqui você pode implementar verificação no banco de dados
        # Por enquanto, usando credenciais fixas
        if username == 'admin' and password == 'admin123':
            session['user_id'] = '1'
            session['username'] = username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Usuário ou senha inválidos')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
@login_required_custom
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

@app.route('/domains', methods=['GET', 'POST'])
@login_required_custom
def manage_domains():
    if request.method == 'POST':
        domain_name = request.form.get('domain_name')
        ttl = request.form.get('ttl', 300)
        comment = request.form.get('comment')

        # Primário
        primary_ipv4 = request.form.get('primary_ipv4')
        primary_ipv4_type = request.form.get('primary_ipv4_type')
        primary_ipv6 = request.form.get('primary_ipv6')
        primary_ipv6_type = request.form.get('primary_ipv6_type')
        primary_hostname = request.form.get('primary_hostname')
        primary_hostname_type = request.form.get('primary_hostname_type')

        # Secundário
        secondary_ipv4 = request.form.get('secondary_ipv4')
        secondary_ipv4_type = request.form.get('secondary_ipv4_type')
        secondary_ipv6 = request.form.get('secondary_ipv6')
        secondary_ipv6_type = request.form.get('secondary_ipv6_type')
        secondary_hostname = request.form.get('secondary_hostname')
        secondary_hostname_type = request.form.get('secondary_hostname_type')
        try:
            domain_id = db.add_domain(domain_name, comment, int(ttl))
            # Adicionar link primário se algum campo preenchido
            if primary_ipv4 or primary_ipv6 or primary_hostname:
                db.add_dns(domain_id, "primary", primary_ipv4, primary_ipv6, primary_hostname, primary_ipv4_type or 'A')
                db.add_dns(domain_id, "primary", None, primary_ipv6, None, primary_ipv6_type or 'AAAA')
                db.add_dns(domain_id, "primary", None, None, primary_hostname, primary_hostname_type or 'CNAME')
            # Adicionar link secundário se algum campo preenchido
            if secondary_ipv4 or secondary_ipv6 or secondary_hostname:
                db.add_dns(domain_id, "secondary", secondary_ipv4, secondary_ipv6, secondary_hostname, secondary_ipv4_type or 'A')
                db.add_dns(domain_id, "secondary", None, secondary_ipv6, None, secondary_ipv6_type or 'AAAA')
                db.add_dns(domain_id, "secondary", None, None, secondary_hostname, secondary_hostname_type or 'CNAME')
            # Sincronizar com Cloudflare (criar registro DNS)
            if cloudflare:
                try:
                    if record_type == 'A' and primary_ipv4:
                        cloudflare.create_dns_record(domain_name, 'A', primary_ipv4, int(ttl), False, )
                    elif record_type == 'AAAA' and primary_ipv6:
                        cloudflare.create_dns_record(domain_name, 'AAAA', primary_ipv6, int(ttl))
                    elif record_type == 'CNAME' and primary_hostname:
                        cloudflare.create_dns_record(domain_name, 'CNAME', primary_hostname, int(ttl))
                    else:
                        flash('Domínio cadastrado, mas dados do link primário insuficientes para criar DNS no Cloudflare.', 'warning')
                    flash('Registro DNS criado no Cloudflare com sucesso!', 'success')
                except Exception as e:
                    flash(f'Domínio cadastrado, mas erro ao criar DNS no Cloudflare: {str(e)}', 'danger')
            else:
                flash('Domínio cadastrado, mas Cloudflare não está configurado.', 'warning')
            flash(f'Domínio {domain_name} adicionado com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro ao adicionar domínio: {str(e)}', 'danger')
        return redirect(url_for('manage_domains'))
    domains = db.get_domains()
    return render_template('domains.html', domains=domains)

@app.route('/logs')
@login_required_custom
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
    return render_template('logs.html', logs=logs, failover_count=failover_count, error_count=error_count, success_count=success_count)

@app.route('/settings')
@login_required_custom
def settings():
    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    zone_id = os.getenv('CLOUDFLARE_ZONE_ID')
    return render_template('settings.html', api_token=api_token, zone_id=zone_id, cloudflare_error=cloudflare_error)

@app.route('/domains/edit/<int:domain_id>', methods=['GET', 'POST'])
@login_required_custom
def edit_domain(domain_id):
    domain = db.get_domain_by_id(domain_id)
    if not domain:
        flash('Domínio não encontrado.', 'danger')
        return redirect(url_for('manage_domains'))

    if request.method == 'POST':
        domain_name = request.form.get('domain_name')
        comment = request.form.get('comment')
        ttl = request.form.get('ttl', 300)

        # Primário
        primary_ipv4 = request.form.get('primary_ipv4')
        primary_ipv4_type = request.form.get('primary_ipv4_type')
        primary_ipv6 = request.form.get('primary_ipv6')
        primary_ipv6_type = request.form.get('primary_ipv6_type')
        primary_hostname = request.form.get('primary_hostname')
        primary_hostname_type = request.form.get('primary_hostname_type')
        # Secundário
        secondary_ipv4 = request.form.get('secondary_ipv4')
        secondary_ipv4_type = request.form.get('secondary_ipv4_type')
        secondary_ipv6 = request.form.get('secondary_ipv6')
        secondary_ipv6_type = request.form.get('secondary_ipv6_type')
        secondary_hostname = request.form.get('secondary_hostname')
        secondary_hostname_type = request.form.get('secondary_hostname_type')
        try:
            db.update_domain(domain_id, domain_name, comment, int(ttl))
            # Atualizar link primário
            if domain.get('primary_id'):
                db.update_dns(domain['primary_id'], primary_ipv4, primary_ipv6, primary_hostname, primary_ipv4_type or 'A')
                db.update_dns(domain['primary_id'], None, primary_ipv6, None, primary_ipv6_type or 'AAAA')
                db.update_dns(domain['primary_id'], None, None, primary_hostname, primary_hostname_type or 'CNAME')
            else:
                if primary_ipv4 or primary_ipv6 or primary_hostname:
                    db.add_dns(domain_id, "primary", primary_ipv4, primary_ipv6, primary_hostname, primary_ipv4_type or 'A')
                    db.add_dns(domain_id, "primary", None, primary_ipv6, None, primary_ipv6_type or 'AAAA')
                    db.add_dns(domain_id, "primary", None, None, primary_hostname, primary_hostname_type or 'CNAME')
            # Atualizar link secundário
            if domain.get('secondary_id'):
                db.update_dns(domain['secondary_id'], secondary_ipv4, secondary_ipv6, secondary_hostname, secondary_ipv4_type or 'A')
                db.update_dns(domain['secondary_id'], None, secondary_ipv6, None, secondary_ipv6_type or 'AAAA')
                db.update_dns(domain['secondary_id'], None, None, secondary_hostname, secondary_hostname_type or 'CNAME')
            else:
                if secondary_ipv4 or secondary_ipv6 or secondary_hostname:
                    db.add_dns(domain_id, "secondary", secondary_ipv4, secondary_ipv6, secondary_hostname, secondary_ipv4_type or 'A')
                    db.add_dns(domain_id, "secondary", None, secondary_ipv6, None, secondary_ipv6_type or 'AAAA')
                    db.add_dns(domain_id, "secondary", None, None, secondary_hostname, secondary_hostname_type or 'CNAME')
            # Sincronizar com Cloudflare (atualizar registro DNS)
            if cloudflare:
                try:
                    if record_type == 'A' and primary_ipv4:
                        cloudflare.update_domain_to_primary(domain_name, 'A', primary_ipv4=primary_ipv4)
                    elif record_type == 'AAAA' and primary_ipv6:
                        cloudflare.update_domain_to_primary(domain_name, 'AAAA', primary_ipv6=primary_ipv6)
                    elif record_type == 'CNAME' and primary_hostname:
                        cloudflare.update_domain_to_primary(domain_name, 'CNAME', primary_hostname=primary_hostname)
                    else:
                        flash('Domínio atualizado, mas dados do link primário insuficientes para atualizar DNS no Cloudflare.', 'warning')
                    flash('Registro DNS atualizado no Cloudflare com sucesso!', 'success')
                except Exception as e:
                    flash(f'Domínio atualizado, mas erro ao atualizar DNS no Cloudflare: {str(e)}', 'danger')
            else:
                flash('Domínio atualizado, mas Cloudflare não está configurado.', 'warning')
            flash('Domínio atualizado com sucesso!', 'success')
            return redirect(url_for('manage_domains'))
        except Exception as e:
            flash(f'Erro ao atualizar domínio: {str(e)}', 'danger')
    return render_template('edit_domain.html', domain=domain)

@app.route('/domains/delete/<int:domain_id>', methods=['POST'])
@login_required_custom
def delete_domain(domain_id):
    try:
        db.delete_domain(domain_id)
        flash('Domínio excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir domínio: {str(e)}', 'danger')
    return redirect(url_for('manage_domains'))

@app.route('/domains/switch_ip/<int:domain_id>', methods=['POST'])
@login_required_custom
def switch_ip(domain_id):
    domain = db.get_domain_by_id(domain_id)
    if not domain:
        flash('Domínio não encontrado.', 'danger')
        return redirect(url_for('manage_domains'))

    # Troca os dados do primário e secundário no banco
    try:
        db.swap_primary_secondary_domain_dns(domain_id)
    except Exception as e:
        flash(f'Erro ao alternar links no banco: {str(e)}', 'danger')
        return redirect(url_for('manage_domains'))

    # Atualiza o registro DNS na Cloudflare para apontar para o novo primário
    domain = db.get_domain_by_id(domain_id)  # Atualiza dados após swap
    if cloudflare:
        try:
            if domain['record_type'] == 'A' and domain['primary_ipv4']:
                cloudflare.update_domain_to_primary(domain['domain_name'], 'A', primary_ipv4=domain['primary_ipv4'])
            elif domain['record_type'] == 'AAAA' and domain['primary_ipv6']:
                cloudflare.update_domain_to_primary(domain['domain_name'], 'AAAA', primary_ipv6=domain['primary_ipv6'])
            elif domain['record_type'] == 'CNAME' and domain['primary_hostname']:
                cloudflare.update_domain_to_primary(domain['domain_name'], 'CNAME', primary_hostname=domain['primary_hostname'])
            flash('Switch de IP realizado com sucesso na Cloudflare!', 'success')
        except Exception as e:
            flash(f'Erro ao atualizar DNS na Cloudflare: {str(e)}', 'danger')
    else:
        flash('Cloudflare não está configurado.', 'warning')

    return redirect(url_for('manage_domains'))

def find_hostname(data):
    """Busca recursivamente o campo 'hostname' em qualquer lugar do JSON."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'hostname':
                return value
            result = find_hostname(value)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_hostname(item)
            if result is not None:
                return result
    return None

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'JSON inválido ou não enviado'}), 400

    hostname = find_hostname(data)
    if not hostname:
        return jsonify({'error': 'Campo hostname não encontrado'}), 400

    print(f"Hostname recebido: {hostname}")
    return jsonify({'status': 'ok', 'hostname': hostname}), 200

@app.route('/logs/delete/<int:log_id>', methods=['POST'])
@login_required_custom
def delete_log(log_id):
    try:
        db.delete_log(log_id)
        flash('Log excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir log: {str(e)}', 'danger')
    return redirect(url_for('logs'))
