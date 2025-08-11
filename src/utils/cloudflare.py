import requests
import os
import json
from typing import Dict, List, Optional
from datetime import datetime


class CloudflareAPI:
    def __init__(self):
        self.api_token = os.getenv('CLOUDFLARE_API_TOKEN')
        self.zone_id = os.getenv('CLOUDFLARE_ZONE_ID')
        self.base_url = "https://api.cloudflare.com/client/v4"

        if not self.api_token:
            raise ValueError("CLOUDFLARE_API_TOKEN não configurado")
        if not self.zone_id:
            raise ValueError("CLOUDFLARE_ZONE_ID não configurado")

    def make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }

        url = f"{self.base_url}{endpoint}"

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Método HTTP não suportado: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro na requisição para Cloudflare: {str(e)}")

    def get_dns_records(self, hostname: str = None) -> List[Dict]:
        """Lista todos os registros DNS ou filtra por domínio"""
        endpoint = f"/zones/{self.zone_id}/dns_records"

        if hostname:
            endpoint += f"?name={hostname}"

        response = self.make_request('GET', endpoint)

        if response.get('success'):
            return response.get('result', [])
        else:
            raise Exception(f"Erro ao buscar registros DNS: {response.get('errors', [])}")

    def get_dns_record(self, record_id: str) -> Optional[Dict]:
        """Busca um registro DNS específico por ID"""
        endpoint = f"/zones/{self.zone_id}/dns_records/{record_id}"

        response = self.make_request('GET', endpoint)

        if response.get('success'):
            return response.get('result')
        else:
            return None

    """
    DNS/RECORD - CREATE
    """

    def create_dns_record(self, domain: str, record_type: str, content: str,
                          ttl: int = 300, proxied: bool = False, comment: str = None) -> Dict:
        """Cria um novo registro DNS"""
        endpoint = f"/zones/{self.zone_id}/dns_records"

        data = {
            "type": record_type,
            "name": domain,
            "content": content,
            "comment": comment,
            "ttl": ttl,
            "proxied": proxied
        }

        response = self.make_request('POST', endpoint, data)

        if response.get('success'):
            return response.get('result')
        else:
            raise Exception(f"Erro ao criar registro DNS: {response.get('errors', [])}")

    """
    DNS/RECORD - UPDATE
    """

    def update_dns_record(self, record_id: str, name: str, record_type: str,
                          content: str, ttl: int = 300, proxied: bool = False) -> Dict:
        """Atualiza um registro DNS existente"""
        endpoint = f"/zones/{self.zone_id}/dns_records/{record_id}"

        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied
        }

        response = self.make_request('PUT', endpoint, data)

        if response.get('success'):
            return response.get('result')
        else:
            raise Exception(f"Erro ao atualizar registro DNS: {response.get('errors', [])}")

    def delete_dns_record(self, record_id: str) -> bool:
        """Deleta um registro DNS"""
        endpoint = f"/zones/{self.zone_id}/dns_records/{record_id}"

        response = self.make_request('DELETE', endpoint)

        if response.get('success'):
            return True
        else:
            raise Exception(f"Erro ao deletar registro DNS: {response.get('errors', [])}")

    def find_dns_record(self, name: str, record_type: str) -> Optional[Dict]:
        """Encontra um registro DNS específico por nome e tipo"""
        records = self.get_dns_records(name)

        for record in records:
            if record['name'] == name and record['type'] == record_type:
                return record

        return None

    def update_domain_to_secondary(self, hostname: str, record_type: str,
                                   secondary_ipv4: str = None, secondary_ipv6: str = None,
                                   secondary_hostname: str = None) -> Dict:
        """Atualiza um domínio para usar o link secundário"""
        # Encontrar o registro atual
        current_record = self.find_dns_record(hostname, record_type)

        if not current_record:
            raise Exception(f"Registro DNS não encontrado para {hostname} ({record_type})")

        # Determinar o conteúdo baseado no tipo de record e dados secundários
        if record_type == 'A' and secondary_ipv4:
            new_content = secondary_ipv4
        elif record_type == 'AAAA' and secondary_ipv6:
            new_content = secondary_ipv6
        elif record_type == 'CNAME' and secondary_hostname:
            new_content = secondary_hostname
        else:
            raise Exception(f"Dados secundários insuficientes para tipo {record_type}")

        # Atualizar o registro
        return self.update_dns_record(
            record_id=current_record['id'],
            name=hostname,
            record_type=record_type,
            content=new_content,
            ttl=current_record.get('ttl', 300),
            proxied=current_record.get('proxied', False)
        )

    def update_domain_to_primary(self, hostname: str, record_type: str,
                                 primary_ipv4: str = None, primary_ipv6: str = None,
                                 primary_hostname: str = None) -> Dict:
        """Atualiza um domínio para usar o link primário"""
        # Encontrar o registro atual
        current_record = self.find_dns_record(hostname, record_type)

        if not current_record:
            raise Exception(f"Registro DNS não encontrado para {hostname} ({record_type})")

        # Determinar o conteúdo baseado no tipo de record e dados primários
        if record_type == 'A' and primary_ipv4:
            new_content = primary_ipv4
        elif record_type == 'AAAA' and primary_ipv6:
            new_content = primary_ipv6
        elif record_type == 'CNAME' and primary_hostname:
            new_content = primary_hostname
        else:
            raise Exception(f"Dados primários insuficientes para tipo {record_type}")

        # Atualizar o registro
        return self.update_dns_record(
            record_id=current_record['id'],
            name=hostname,
            record_type=record_type,
            content=new_content,
            ttl=current_record.get('ttl', 300),
            proxied=current_record.get('proxied', False)
        )

    def test_connection(self) -> bool:
        """Testa a conexão com a API do Cloudflare"""
        try:
            endpoint = f"/zones/{self.zone_id}"
            response = self.make_request('GET', endpoint)
            return response.get('success', False)
        except Exception:
            return False
