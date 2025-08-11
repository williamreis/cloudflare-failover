from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from ..utils.db import Database
from ..utils.monitor import LinkMonitor
from ..utils.cloudflare import CloudflareAPI
from dotenv import load_dotenv

load_dotenv()

bp = Blueprint('domain', __name__, url_prefix='/domains')
db = Database()
cloudflare = None
try:
    cloudflare = CloudflareAPI()
except Exception as e:
    cloudflare_error = str(e)
else:
    cloudflare_error = None


# monitor = LinkMonitor(db, cloudflare) if cloudflare else None


@bp.route('/', methods=['GET', 'POST'])
def manage_domains():
    if request.method == 'POST':
        hostname = request.form.get('hostname')
        ttl = request.form.get('ttl', 300)
        comment = request.form.get('comment')

        # Register DNS
        primary_ip = request.form.get('primary_ip')
        primary_type = request.form.get('primary_type')
        secondary_ip = request.form.get('secondary_ip')
        secondary_type = request.form.get('secondary_type')

        try:
            domain_id = db.add_domain(hostname, comment, int(ttl))
            # Adicionar link primário se algum campo preenchido
            if primary_ip:
                db.add_dns(domain_id, "primary", primary_ip, hostname, primary_type or 'A')
            # Adicionar link secundário se algum campo preenchido
            if secondary_ip:
                db.add_dns(domain_id, "secondary", secondary_ip, hostname, secondary_type or 'A')
            # Sincronizar com Cloudflare (criar registro DNS)
            # if cloudflare:
            #     try:
            #         if primary_type and primary_ip:
            #             cloudflare.create_dns_record(hostname, primary_type, primary_ip, int(ttl), False, )
            #         else:
            #             flash(
            #                 'Domínio cadastrado, mas dados do link primário insuficientes para criar DNS no Cloudflare.',
            #                 'warning')
            #         flash('Registro DNS criado no Cloudflare com sucesso!', 'success')
            #     except Exception as e:
            #         flash(f'Domínio cadastrado, mas erro ao criar DNS no Cloudflare: {str(e)}', 'danger')
            # else:
            #     flash('Domínio cadastrado, mas Cloudflare não está configurado.', 'warning')
            flash(f'Domínio {hostname} adicionado com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro ao adicionar domínio: {str(e)}', 'danger')
        return redirect(url_for('domain.manage_domains'))
    domains = db.get_domains()
    return render_template('domains/list.html', domains=domains)


@bp.route('/domains/edit/<int:domain_id>', methods=['GET', 'POST'])
def edit_domain(domain_id):
    domain = db.get_domain_by_id(domain_id)
    if not domain:
        flash('Domínio não encontrado.', 'danger')
        return redirect(url_for('domain.manage_domains'))

    if request.method == 'POST':
        hostname = request.form.get('hostname')
        comment = request.form.get('comment')
        ttl = request.form.get('ttl', 300)

        # Primário
        primary_ip = request.form.get('primary_ip')
        primary_type = request.form.get('primary_type')
        # Secundário
        secondary_ip = request.form.get('secondary_ip')
        secondary_type = request.form.get('secondary_type')
        try:
            db.update_domain(domain_id, hostname, comment, int(ttl))
            # Atualizar link primário
            if domain.get('primary_id'):
                db.update_dns(domain['primary_id'], primary_ip, primary_ipv6, primary_hostname, primary_type or 'A')
                db.update_dns(domain['primary_id'], None, primary_ipv6, None, primary_ipv6_type or 'AAAA')
                db.update_dns(domain['primary_id'], None, None, primary_hostname, primary_hostname_type or 'CNAME')
            else:
                if primary_ip or primary_ipv6 or primary_hostname:
                    db.add_dns(domain_id, "primary", primary_ip, primary_ipv6, primary_hostname, primary_type or 'A')
                    db.add_dns(domain_id, "primary", None, primary_ipv6, None, primary_ipv6_type or 'AAAA')
                    db.add_dns(domain_id, "primary", None, None, primary_hostname, primary_hostname_type or 'CNAME')
            # Atualizar link secundário
            if domain.get('secondary_id'):
                db.update_dns(domain['secondary_id'], secondary_ip, secondary_ipv6, secondary_hostname,
                              secondary_type or 'A')
                db.update_dns(domain['secondary_id'], None, secondary_ipv6, None, secondary_ipv6_type or 'AAAA')
                db.update_dns(domain['secondary_id'], None, None, secondary_hostname,
                              secondary_hostname_type or 'CNAME')
            else:
                if secondary_ip or secondary_ipv6 or secondary_hostname:
                    db.add_dns(domain_id, "secondary", secondary_ip, secondary_ipv6, secondary_hostname,
                               secondary_type or 'A')
                    db.add_dns(domain_id, "secondary", None, secondary_ipv6, None, secondary_ipv6_type or 'AAAA')
                    db.add_dns(domain_id, "secondary", None, None, secondary_hostname,
                               secondary_hostname_type or 'CNAME')
            # Sincronizar com Cloudflare (atualizar registro DNS)
            if cloudflare:
                try:
                    if record_type == 'A' and primary_ip:
                        cloudflare.update_domain_to_primary(hostname, 'A', primary_ip=primary_ip)
                    elif record_type == 'AAAA' and primary_ipv6:
                        cloudflare.update_domain_to_primary(hostname, 'AAAA', primary_ipv6=primary_ipv6)
                    elif record_type == 'CNAME' and primary_hostname:
                        cloudflare.update_domain_to_primary(hostname, 'CNAME', primary_hostname=primary_hostname)
                    else:
                        flash(
                            'Domínio atualizado, mas dados do link primário insuficientes para atualizar DNS no Cloudflare.',
                            'warning')
                    flash('Registro DNS atualizado no Cloudflare com sucesso!', 'success')
                except Exception as e:
                    flash(f'Domínio atualizado, mas erro ao atualizar DNS no Cloudflare: {str(e)}', 'danger')
            else:
                flash('Domínio atualizado, mas Cloudflare não está configurado.', 'warning')
            flash('Domínio atualizado com sucesso!', 'success')
            return redirect(url_for('domain.manage_domains'))
        except Exception as e:
            flash(f'Erro ao atualizar domínio: {str(e)}', 'danger')
    return redirect(url_for('domain.manage_domains'))


@bp.route('/domains/delete/<int:domain_id>', methods=['POST'])
def delete_domain(domain_id):
    try:
        db.delete_domain(domain_id)
        flash('Domínio excluído com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir domínio: {str(e)}', 'danger')
    return redirect(url_for('domain.manage_domains'))


@bp.route('/switch_ip/<int:domain_id>', methods=['POST'])
def switch_ip(domain_id):
    domain = db.get_domain_by_id(domain_id)
    if not domain:
        flash('Domínio não encontrado.', 'danger')
        return redirect(url_for('domain.manage_domains'))

    # Troca os dados do primário e secundário no banco
    try:
        db.swap_primary_secondary_domain_dns(domain_id)
    except Exception as e:
        flash(f'Erro ao alternar links no banco: {str(e)}', 'danger')
        return redirect(url_for('domain.manage_domains'))

    # Atualiza o registro DNS na Cloudflare para apontar para o novo primário
    domain = db.get_domain_by_id(domain_id)  # Atualiza dados após swap
    if cloudflare:
        try:
            if domain['record_type'] == 'A' and domain['primary_ip']:
                cloudflare.update_domain_to_primary(domain['hostname'], 'A', primary_ip=domain['primary_ip'])
            elif domain['record_type'] == 'AAAA' and domain['primary_ipv6']:
                cloudflare.update_domain_to_primary(domain['hostname'], 'AAAA', primary_ipv6=domain['primary_ipv6'])
            elif domain['record_type'] == 'CNAME' and domain['primary_hostname']:
                cloudflare.update_domain_to_primary(domain['hostname'], 'CNAME',
                                                    primary_hostname=domain['primary_hostname'])
            flash('Switch de IP realizado com sucesso na Cloudflare!', 'success')
        except Exception as e:
            flash(f'Erro ao atualizar DNS na Cloudflare: {str(e)}', 'danger')
    else:
        flash('Cloudflare não está configurado.', 'warning')

    return redirect(url_for('domain.manage_domains'))
