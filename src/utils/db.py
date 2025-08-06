import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional


class Database:
    def __init__(self, db_path: str = "data/cloudflare_failover.db"):
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Inicializa o banco de dados com as tabelas necessárias"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Tabela de domínios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS domain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain_name TEXT NOT NULL UNIQUE,
                    ttl INTEGER DEFAULT 300,
                    comment TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Tabela de domain_dns (primário e secundário)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS domain_dns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain_id INTEGER NOT NULL,
                    link_type TEXT NOT NULL CHECK (link_type IN ('primary', 'secondary')),
                    ipaddress TEXT,
                    hostname TEXT,
                    record_type TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (domain_id) REFERENCES domain (id) ON DELETE CASCADE,
                    UNIQUE(domain_id, link_type)
                )
            ''')

            # Tabela de logs de alterações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS change_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain_id INTEGER NOT NULL,
                    dns_from_id INTEGER,
                    dns_to_id INTEGER,
                    change_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (domain_id) REFERENCES domain (id) ON DELETE CASCADE,
                    FOREIGN KEY (dns_from_id) REFERENCES domain_dns (id),
                    FOREIGN KEY (dns_to_id) REFERENCES domain_dns (id)
                )
            ''')

            # Tabela de configurações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

    def add_domain(self, domain_name: str, comment: str = None, ttl: int = 300) -> int:
        """Adiciona um novo domínio"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO domain (domain_name, comment, ttl)
                VALUES (?, ?, ?)
            ''', (domain_name, comment, ttl))
            conn.commit()
            return cursor.lastrowid

    def add_dns(self, domain_id: int, link_type: str, ipaddress: str = None, hostname: str = None, record_type: str = 'A') -> int:
        """Adiciona um link (primário ou secundário) para um domínio"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO domain_dns (domain_id, link_type, ipaddress, hostname, record_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (domain_id, link_type, ipaddress, hostname, record_type))
            conn.commit()
            return cursor.lastrowid

    def get_domains(self) -> List[Dict]:
        """Retorna todos os domínios com seus domain_dns"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT d.*, 
                       p.id as primary_id, p.ipaddress as primary_ipv4, p.hostname as primary_hostname,
                       s.id as secondary_id, s.ipaddress as secondary_ipv4, s.hostname as secondary_hostname
                FROM domain d
                LEFT JOIN domain_dns p ON d.id = p.domain_id AND p.link_type = 'primary'
                LEFT JOIN domain_dns s ON d.id = s.domain_id AND s.link_type = 'secondary'
                ORDER BY d.domain_name
            ''')

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_domain_by_id(self, domain_id: int) -> Optional[Dict]:
        """Retorna um domínio específico por ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT d.*, 
                       p.id as primary_id, p.ipaddress as primary_ipv4, p.hostname as primary_hostname,
                       s.id as secondary_id, s.ipaddress as secondary_ipv4, s.hostname as secondary_hostname
                FROM domain d
                LEFT JOIN domain_dns p ON d.id = p.domain_id AND p.link_type = 'primary'
                LEFT JOIN domain_dns s ON d.id = s.domain_id AND s.link_type = 'secondary'
                WHERE d.id = ?
            ''', (domain_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def update_domain(self, domain_id: int, domain_name: str, comment: str = None, ttl: int = 300):
        """Atualiza um domínio"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE domain 
                SET domain_name = ?, comment = ?, ttl = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (domain_name, comment, ttl, domain_id))
            conn.commit()

    def update_dns(self, link_id: int, ipaddress: str = None, hostname: str = None, record_type: str = 'A'):
        """Atualiza um link"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE domain_dns 
                SET ipaddress = ?, hostname = ?, record_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (ipaddress, hostname, record_type, link_id))
            conn.commit()

    def delete_domain(self, domain_id: int):
        """Deleta um domínio e todos os seus dns"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM domain WHERE id = ?', (domain_id,))
            conn.commit()

    def add_change_log(self, domain_id: int, dns_from_id: int, dns_to_id: int,
                       change_type: str, status: str, message: str = None):
        """Adiciona um log de alteração"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO change_logs (domain_id, dns_from_id, dns_to_id, change_type, status, message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (domain_id, dns_from_id, dns_to_id, change_type, status, message))
            conn.commit()

    def get_change_logs(self, limit: int = 50) -> List[Dict]:
        """Retorna os logs de alterações"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT cl.*, d.domain_name
                FROM change_logs cl
                JOIN domain d ON cl.domain_id = d.id
                ORDER BY cl.created_at DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_setting(self, key: str) -> Optional[str]:
        """Retorna uma configuração"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            return result[0] if result else None

    def set_setting(self, key: str, value: str, description: str = None):
        """Define uma configuração"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (key, value, description))
            conn.commit()

    def swap_primary_secondary_domain_dns(self, domain_id: int):
        """Troca os dados dos dns primário e secundário de um domínio"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Busca os dns primário e secundário
            cursor.execute('SELECT id, ipaddress, hostname FROM domain_dns WHERE domain_id = ? AND link_type = "primary"', (domain_id,))
            primary = cursor.fetchone()
            cursor.execute('SELECT id, ipaddress, hostname FROM domain_dns WHERE domain_id = ? AND link_type = "secondary"', (domain_id,))
            secondary = cursor.fetchone()
            if not primary or not secondary:
                raise Exception('Links primário e/ou secundário não encontrados para este domínio.')
            # Troca os dados
            cursor.execute('UPDATE domain_dns SET ipaddress = ?, hostname = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (secondary[1], secondary[2], primary[0]))
            cursor.execute('UPDATE domain_dns SET ipaddress = ?, hostname = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (primary[1], primary[2], secondary[0]))
            conn.commit()

    def delete_log(self, log_id: int):
        """Remove um log pelo id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM change_logs WHERE id = ?', (log_id,))
            conn.commit()
