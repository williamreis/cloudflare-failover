import subprocess
import requests
import time
import threading
import os
from typing import Dict, List, Optional
from datetime import datetime
import logging

from .db import Database
from .cloudflare import CloudflareAPI


class LinkMonitor:
    def __init__(self, db: Database, cloudflare: CloudflareAPI):
        self.db = db
        self.cloudflare = cloudflare
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 30  # segundos

        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def ping_host(self, host: str, timeout: int = 5) -> bool:
        """Faz ping em um host para verificar se está online"""
        try:
            # Usar ping com timeout
            result = subprocess.run(
                ['ping', '-c', '1', '-W', str(timeout), host],
                capture_output=True,
                text=True,
                timeout=timeout + 2
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            return False

    def http_check(self, url: str, timeout: int = 5) -> bool:
        """Verifica se um URL está respondendo via HTTP"""
        try:
            # Adicionar http:// se não especificado
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url

            response = requests.get(url, timeout=timeout, allow_redirects=True)
            return response.status_code < 500  # Considera 2xx, 3xx, 4xx como "online"
        except requests.RequestException:
            return False

    def check_link_status(self, domain_data: Dict) -> Dict:
        """Verifica o status dos links primário e secundário de um domínio"""
        primary_online = False
        secondary_online = False

        # Verificar link primário
        if domain_data.get('primary_ipv4'):
            primary_online = self.ping_host(domain_data['primary_ipv4'])
        elif domain_data.get('primary_ipv6'):
            primary_online = self.ping_host(domain_data['primary_ipv6'])
        elif domain_data.get('primary_hostname'):
            primary_online = self.http_check(domain_data['primary_hostname'])

        # Verificar link secundário
        if domain_data.get('secondary_ipv4'):
            secondary_online = self.ping_host(domain_data['secondary_ipv4'])
        elif domain_data.get('secondary_ipv6'):
            secondary_online = self.ping_host(domain_data['secondary_ipv6'])
        elif domain_data.get('secondary_hostname'):
            secondary_online = self.http_check(domain_data['secondary_hostname'])

        return {
            'domain_id': domain_data['id'],
            'domain_name': domain_data['domain_name'],
            'primary_online': primary_online,
            'secondary_online': secondary_online,
            'timestamp': datetime.now()
        }

    def should_failover(self, status: Dict) -> bool:
        """Determina se deve fazer failover baseado no status dos links"""
        # Failover se primário offline e secundário online
        return not status['primary_online'] and status['secondary_online']

    def should_failback(self, status: Dict) -> bool:
        """Determina se deve fazer failback baseado no status dos links"""
        # Failback se primário voltou online
        return status['primary_online']

    def execute_failover(self, domain_data: Dict) -> bool:
        """Executa o failover para o link secundário"""
        try:
            self.logger.info(f"Iniciando failover para {domain_data['domain_name']}")

            # Determinar o conteúdo baseado no tipo de record
            record_type = domain_data['record_type']

            if record_type == 'A':
                secondary_content = domain_data.get('secondary_ipv4')
            elif record_type == 'AAAA':
                secondary_content = domain_data.get('secondary_ipv6')
            elif record_type == 'CNAME':
                secondary_content = domain_data.get('secondary_hostname')
            else:
                raise Exception(f"Tipo de record não suportado: {record_type}")

            if not secondary_content:
                raise Exception(f"Dados secundários insuficientes para tipo {record_type}")

            # Atualizar DNS no Cloudflare
            result = self.cloudflare.update_domain_to_secondary(
                domain_name=domain_data['domain_name'],
                record_type=record_type,
                secondary_ipv4=domain_data.get('secondary_ipv4'),
                secondary_ipv6=domain_data.get('secondary_ipv6'),
                secondary_hostname=domain_data.get('secondary_hostname')
            )

            # Registrar log
            self.db.add_change_log(
                domain_id=domain_data['id'],
                from_link_id=domain_data.get('primary_id'),
                to_link_id=domain_data.get('secondary_id'),
                change_type='failover',
                status='success',
                message=f"Failover executado para {secondary_content}"
            )

            self.logger.info(f"Failover executado com sucesso para {domain_data['domain_name']}")
            return True

        except Exception as e:
            self.logger.error(f"Erro no failover para {domain_data['domain_name']}: {str(e)}")

            # Registrar log de erro
            self.db.add_change_log(
                domain_id=domain_data['id'],
                from_link_id=domain_data.get('primary_id'),
                to_link_id=domain_data.get('secondary_id'),
                change_type='failover',
                status='error',
                message=str(e)
            )
            return False

    def execute_failback(self, domain_data: Dict) -> bool:
        """Executa o failback para o link primário"""
        try:
            self.logger.info(f"Iniciando failback para {domain_data['domain_name']}")

            # Determinar o conteúdo baseado no tipo de record
            record_type = domain_data['record_type']

            if record_type == 'A':
                primary_content = domain_data.get('primary_ipv4')
            elif record_type == 'AAAA':
                primary_content = domain_data.get('primary_ipv6')
            elif record_type == 'CNAME':
                primary_content = domain_data.get('primary_hostname')
            else:
                raise Exception(f"Tipo de record não suportado: {record_type}")

            if not primary_content:
                raise Exception(f"Dados primários insuficientes para tipo {record_type}")

            # Atualizar DNS no Cloudflare
            result = self.cloudflare.update_domain_to_primary(
                domain_name=domain_data['domain_name'],
                record_type=record_type,
                primary_ipv4=domain_data.get('primary_ipv4'),
                primary_ipv6=domain_data.get('primary_ipv6'),
                primary_hostname=domain_data.get('primary_hostname')
            )

            # Registrar log
            self.db.add_change_log(
                domain_id=domain_data['id'],
                from_link_id=domain_data.get('secondary_id'),
                to_link_id=domain_data.get('primary_id'),
                change_type='failback',
                status='success',
                message=f"Failback executado para {primary_content}"
            )

            self.logger.info(f"Failback executado com sucesso para {domain_data['domain_name']}")
            return True

        except Exception as e:
            self.logger.error(f"Erro no failback para {domain_data['domain_name']}: {str(e)}")

            # Registrar log de erro
            self.db.add_change_log(
                domain_id=domain_data['id'],
                from_link_id=domain_data.get('secondary_id'),
                to_link_id=domain_data.get('primary_id'),
                change_type='failback',
                status='error',
                message=str(e)
            )
            return False

    def monitor_loop(self):
        """Loop principal de monitoramento"""
        self.logger.info("Iniciando monitoramento de links")

        while self.monitoring:
            try:
                # Buscar todos os domínios
                domains = self.db.get_domains()

                for domain in domains:
                    # Verificar se tem links configurados
                    if not (domain.get('primary_id') and domain.get('secondary_id')):
                        continue

                    # Verificar status dos links
                    status = self.check_link_status(domain)

                    # Verificar se precisa fazer failover
                    if self.should_failover(status):
                        self.execute_failover(domain)
                    # Verificar se precisa fazer failback
                    elif self.should_failback(status):
                        self.execute_failback(domain)

                # Aguardar próximo check
                time.sleep(self.check_interval)

            except Exception as e:
                self.logger.error(f"Erro no loop de monitoramento: {str(e)}")
                time.sleep(self.check_interval)

    def start_monitoring(self):
        """Inicia o monitoramento em background"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
            self.logger.info("Monitoramento iniciado")

    def stop_monitoring(self):
        """Para o monitoramento"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Monitoramento parado")

    def get_current_status(self) -> List[Dict]:
        """Retorna o status atual de todos os domínios"""
        domains = self.db.get_domains()
        status_list = []

        for domain in domains:
            if domain.get('primary_id') and domain.get('secondary_id'):
                status = self.check_link_status(domain)
                status_list.append(status)

        return status_list

    def test_link(self, host: str, test_type: str = 'ping') -> bool:
        """Testa um link específico"""
        if test_type == 'ping':
            return self.ping_host(host)
        elif test_type == 'http':
            return self.http_check(host)
        else:
            raise ValueError(f"Tipo de teste não suportado: {test_type}")
