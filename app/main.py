from dotenv import load_dotenv
load_dotenv() 

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import time
import threading

from db import Database
from cloudflare import CloudflareAPI
from monitor import LinkMonitor


# Configuração da página
st.set_page_config(
    page_title="Cloudflare Failover",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-card {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #666666;
    }
    .status-online {
        background-color: green;
    }
    .status-offline {
        background-color: red;
    }
    .metric-card {
        background-color: #000;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# Inicialização das classes
@st.cache_resource
def init_database():
    return Database()


@st.cache_resource
def init_cloudflare():
    try:
        return CloudflareAPI()
    except ValueError as e:
        st.error(f"Erro na configuração do Cloudflare: {str(e)}")
        return None


@st.cache_resource
def init_monitor(_db, _cloudflare):
    if _cloudflare:
        return LinkMonitor(_db, _cloudflare)
    return None


# Inicializar componentes
db = init_database()
cloudflare = init_cloudflare()
monitor = init_monitor(db, cloudflare)

# Sidebar
with st.sidebar:
    st.title("Cloudflare Failover")

    # Status do Cloudflare
    if cloudflare:
        if cloudflare.test_connection():
            st.success("✅ Cloudflare conectado")
        else:
            st.error("❌ Erro na conexão Cloudflare")
    else:
        st.error("❌ Cloudflare não configurado")

    st.divider()

    # Controles de monitoramento
    if monitor:
        st.subheader("Monitoramento")

        if st.button("▶️ Iniciar Monitoramento", type="primary"):
            monitor.start_monitoring()
            st.success("Monitoramento iniciado!")

        if st.button("⏹️ Parar Monitoramento"):
            monitor.stop_monitoring()
            st.info("Monitoramento parado!")

        # Status atual
        if st.button("Atualizar Status"):
            st.rerun()

    st.divider()

    # Configurações
    st.subheader("Configurações")

    # Intervalo de verificação
    check_interval = st.slider(
        "Intervalo de verificação (segundos)",
        min_value=10,
        max_value=300,
        value=30,
        step=10
    )

    if monitor:
        monitor.check_interval = check_interval

# Header principal
st.markdown('<h1 class="main-header">Cloudflare Failover</h1>', unsafe_allow_html=True)

# Tabs principais
tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Gerenciar Domínios", "Logs", "Configurações"])

# Tab 1: Dashboard
with tab1:
    col1, col2, col3, col4 = st.columns(4)

    # Métricas
    domains = db.get_domains()
    total_domains = len(domains)
    active_domains = len([d for d in domains if d.get('primary_id') and d.get('secondary_id')])

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Total de Domínios</h3>
            <h2>{total_domains}</h2>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Domínios Ativos</h3>
            <h2>{active_domains}</h2>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        logs = db.get_change_logs(limit=100)
        recent_changes = len(
            [log for log in logs if log['created_at'] > (datetime.now() - timedelta(hours=24)).isoformat()])
        st.markdown(f"""
        <div class="metric-card">
            <h3>Alterações (24h)</h3>
            <h2>{recent_changes}</h2>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        if monitor and monitor.monitoring:
            status = "🟢 Ativo"
        else:
            status = "🔴 Inativo"
        st.markdown(f"""
        <div class="metric-card">
            <h3>Status Monitoramento</h3>
            <h2>{status}</h2>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Status dos domínios
    if monitor:
        st.subheader("Status dos Links")

        # Buscar status atual
        status_list = monitor.get_current_status()

        if status_list:
            for status in status_list:
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                with col1:
                    st.write(f"**{status['domain_name']}**")

                with col2:
                    if status['primary_online']:
                        st.markdown('<div class="status-card status-online">Primário Online</div>',
                                    unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="status-card status-offline">Primário Offline</div>',
                                    unsafe_allow_html=True)

                with col3:
                    if status['secondary_online']:
                        st.markdown('<div class="status-card status-online">Secundário Online</div>',
                                    unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="status-card status-offline">Secundário Offline</div>',
                                    unsafe_allow_html=True)

                with col4:
                    st.write(f"Última verificação: {status['timestamp'].strftime('%H:%M:%S')}")
        else:
            st.info("Nenhum domínio configurado para monitoramento")

    # Gráfico de alterações recentes
    st.subheader("Histórico de Alterações")

    logs = db.get_change_logs(limit=50)
    if logs:
        # Converter para DataFrame
        df_logs = pd.DataFrame(logs)
        df_logs['created_at'] = pd.to_datetime(df_logs['created_at'])

        # Agrupar por data e tipo
        daily_changes = df_logs.groupby([df_logs['created_at'].dt.date, 'change_type']).size().unstack(fill_value=0)

        # Criar gráfico
        fig = go.Figure()

        for change_type in daily_changes.columns:
            fig.add_trace(go.Scatter(
                x=daily_changes.index,
                y=daily_changes[change_type],
                mode='lines+markers',
                name=change_type.title(),
                line=dict(width=3)
            ))

        fig.update_layout(
            title="Alterações por Dia",
            xaxis_title="Data",
            yaxis_title="Número de Alterações",
            height=400
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum log de alteração encontrado")

# Tab 2: Gerenciar Domínios
with tab2:
    st.subheader("Gerenciar Domínios")

    # Formulário para adicionar domínio
    with st.expander("➕ Adicionar Novo Domínio", expanded=False):
        with st.form("add_domain"):
            col1, col2 = st.columns(2)

            with col1:
                domain_name = st.text_input("Nome do Domínio", placeholder="exemplo.com")
                record_type = st.selectbox("Tipo de Record", ["A", "AAAA", "CNAME"])
                ttl = st.number_input("TTL (segundos)", min_value=60, max_value=86400, value=300, step=60)

            with col2:
                st.write("**Link Primário**")
                primary_ipv4 = st.text_input("IPv4 Primário", placeholder="192.168.1.1")
                primary_ipv6 = st.text_input("IPv6 Primário", placeholder="2001:db8::1")
                primary_hostname = st.text_input("Hostname Primário", placeholder="primary.exemplo.com")

                st.write("**Link Secundário**")
                secondary_ipv4 = st.text_input("IPv4 Secundário", placeholder="192.168.1.2")
                secondary_ipv6 = st.text_input("IPv6 Secundário", placeholder="2001:db8::2")
                secondary_hostname = st.text_input("Hostname Secundário", placeholder="secondary.exemplo.com")

            submitted = st.form_submit_button("Adicionar Domínio", type="primary")

            if submitted:
                if domain_name:
                    try:
                        # Adicionar domínio
                        domain_id = db.add_domain(domain_name, record_type, ttl)

                        # Adicionar links
                        if primary_ipv4 or primary_ipv6 or primary_hostname:
                            db.add_link(domain_id, "primary", primary_ipv4, primary_ipv6, primary_hostname)

                        if secondary_ipv4 or secondary_ipv6 or secondary_hostname:
                            db.add_link(domain_id, "secondary", secondary_ipv4, secondary_ipv6, secondary_hostname)

                        st.success(f"Domínio {domain_name} adicionado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao adicionar domínio: {str(e)}")
                else:
                    st.error("Nome do domínio é obrigatório")

    # Lista de domínios
    st.subheader("Domínios Configurados")

    domains = db.get_domains()

    if domains:
        for domain in domains:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    st.write(f"**{domain['domain_name']}** ({domain['record_type']})")
                    st.write(f"TTL: {domain['ttl']}s")

                with col2:
                    if domain.get('primary_id'):
                        st.success("✅ Primário")
                    else:
                        st.error("❌ Sem Primário")

                with col3:
                    if domain.get('secondary_id'):
                        st.success("✅ Secundário")
                    else:
                        st.error("❌ Sem Secundário")

                with col4:
                    if st.button("️Deletar", key=f"del_{domain['id']}"):
                        db.delete_domain(domain['id'])
                        st.success("Domínio removido!")
                        st.rerun()

                # Detalhes dos links
                with st.expander("Ver detalhes"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**Link Primário:**")
                        if domain.get('primary_ipv4'):
                            st.write(f"IPv4: {domain['primary_ipv4']}")
                        if domain.get('primary_ipv6'):
                            st.write(f"IPv6: {domain['primary_ipv6']}")
                        if domain.get('primary_hostname'):
                            st.write(f"Hostname: {domain['primary_hostname']}")

                    with col2:
                        st.write("**Link Secundário:**")
                        if domain.get('secondary_ipv4'):
                            st.write(f"IPv4: {domain['secondary_ipv4']}")
                        if domain.get('secondary_ipv6'):
                            st.write(f"IPv6: {domain['secondary_ipv6']}")
                        if domain.get('secondary_hostname'):
                            st.write(f"Hostname: {domain['secondary_hostname']}")

                st.divider()
    else:
        st.info("Nenhum domínio configurado")

# Tab 3: Logs
with tab3:
    st.subheader("Logs de Alterações")

    # Filtros
    col1, col2, col3 = st.columns(3)

    with col1:
        log_limit = st.selectbox("Quantidade de logs", [10, 25, 50, 100], index=2)

    with col2:
        status_filter = st.selectbox("Filtrar por status", ["Todos", "success", "error"], index=0)

    with col3:
        if st.button("Atualizar Logs"):
            st.rerun()

    # Buscar logs
    logs = db.get_change_logs(limit=log_limit)

    # Aplicar filtros
    if status_filter != "Todos":
        logs = [log for log in logs if log['status'] == status_filter]

    if logs:
        # Converter para DataFrame
        df_logs = pd.DataFrame(logs)
        df_logs['created_at'] = pd.to_datetime(df_logs['created_at'])

        # Exibir logs
        for log in logs:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

            with col1:
                st.write(f"**{log['domain_name']}**")
                st.write(log.get('message', ''))

            with col2:
                if log['change_type'] == 'failover':
                    st.info("Failover")
                elif log['change_type'] == 'failback':
                    st.success("Failback")
                else:
                    st.write(log['change_type'])

            with col3:
                if log['status'] == 'success':
                    st.success("✅ Sucesso")
                else:
                    st.error("❌ Erro")

            with col4:
                created_at = log['created_at']
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except ValueError:
                        pass
                if hasattr(created_at, 'strftime'):
                    st.write(created_at.strftime('%d/%m %H:%M'))
                else:
                    st.write(created_at)

            st.divider()
    else:
        st.info("Nenhum log encontrado")

# Tab 4: Configurações
with tab4:
    st.subheader("Configurações")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Configurações do Cloudflare**")

        # Verificar variáveis de ambiente
        api_token = os.getenv('CLOUDFLARE_API_TOKEN')
        zone_id = os.getenv('CLOUDFLARE_ZONE_ID')

        if api_token:
            st.success("✅ API Token configurado")
        else:
            st.error("❌ API Token não configurado")

        if zone_id:
            st.success("✅ Zone ID configurado")
        else:
            st.error("❌ Zone ID não configurado")

    with col2:
        st.write("**Teste de Conexão**")

        if st.button("Testar Cloudflare"):
            if cloudflare:
                if cloudflare.test_connection():
                    st.success("✅ Conexão com Cloudflare OK")
                else:
                    st.error("❌ Erro na conexão com Cloudflare")
            else:
                st.error("❌ Cloudflare não configurado")

        if st.button("Testar Banco de Dados"):
            try:
                domains = db.get_domains()
                st.success(f"✅ Banco de dados OK ({len(domains)} domínios)")
            except Exception as e:
                st.error(f"❌ Erro no banco de dados: {str(e)}")

    st.divider()

    # Configurações do monitoramento
    st.subheader("Configurações de Monitoramento")

    if monitor:
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Intervalo atual:** {monitor.check_interval} segundos")
            st.write(f"**Status:** {'🟢 Ativo' if monitor.monitoring else 'Inativo'}")

        with col2:
            if st.button("Reiniciar Monitoramento"):
                monitor.stop_monitoring()
                time.sleep(1)
                monitor.start_monitoring()
                st.success("Monitoramento reiniciado!")

# Auto-refresh do dashboard
if st.button("Atualizar Dashboard"):
    st.rerun()

# Auto-refresh a cada 30 segundos
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

if time.time() - st.session_state.last_refresh > 30:
    st.session_state.last_refresh = time.time()
    st.rerun()
