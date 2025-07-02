# Cloudflare Failover Manager

Uma aplicação Python com interface Streamlit para gerenciar failover automático de DNS no Cloudflare entre links primário e secundário.

## Funcionalidades

- **Cadastro de Domínios**: Adicione domínios com links primário e secundário
- **Monitoramento Automático**: Verificação contínua do status dos links
- **Failover Automático**: Alteração automática do DNS quando o link primário cai
- **Failback Automático**: Retorno automático ao link primário quando volta online
- **Logs Detalhados**: Histórico completo de todas as alterações
- **Suporte a IPv4/IPv6**: Compatível com diferentes tipos de endereços

## Tecnologias

- **Backend**: Python 3.11+
- **Frontend**: Streamlit
- **Banco de Dados**: SQLite
- **API**: Cloudflare v4
- **Containerização**: Docker & Docker Compose

## Configuração

### 1. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```bash
# Cloudflare API Token (obrigatório)
CLOUDFLARE_API_TOKEN=seu_token_aqui

# Cloudflare Zone ID (obrigatório)
CLOUDFLARE_ZONE_ID=seu_zone_id_aqui
```

### 2. Obter credenciais do Cloudflare

#### API Token
1. Acesse [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Vá em **My Profile** > **API Tokens**
3. Clique em **Create Token**
4. Use o template **Custom token**
5. Configure as permissões:
   - **Zone** > **Zone** > **Read**
   - **Zone** > **DNS** > **Edit**
6. Selecione a zona (domínio) específica
7. Copie o token gerado

#### Zone ID
1. No Cloudflare Dashboard, selecione seu domínio
2. Na página de visão geral, procure por **Zone ID**
3. Copie o ID (32 caracteres alfanuméricos)

## Execução com Docker

### 1. Build e execução

```bash
# Build da imagem
docker compose build

# Executar a aplicação
docker compose up -d
```

### 2. Acessar a aplicação

Abra seu navegador e acesse: `http://localhost:8501`

### 3. Parar a aplicação

```bash
docker compose down
```

## Como Usar

### 1. Configuração Inicial

1. Acesse a aplicação no navegador
2. Vá para a aba **Configurações**
3. Verifique se as credenciais do Cloudflare estão configuradas
4. Teste a conexão com o Cloudflare

### 2. Adicionar Domínios

1. Vá para a aba **Gerenciar Domínios**
2. Clique em **Adicionar Novo Domínio**
3. Preencha os dados:
   - **Nome do Domínio**: ex: `api.exemplo.com`
   - **Tipo de Record**: A, AAAA ou CNAME
   - **TTL**: Tempo de vida do registro (padrão: 300s)
   - **Link Primário**: IPv4, IPv6 ou hostname
   - **Link Secundário**: IPv4, IPv6 ou hostname

### 3. Iniciar Monitoramento

1. Na sidebar, clique em **Iniciar Monitoramento**
2. O sistema começará a verificar os links automaticamente
3. Ajuste o intervalo de verificação conforme necessário

### 4. Monitorar Status

- **Dashboard**: Visualize métricas e status em tempo real
- **Logs**: Acompanhe todas as alterações realizadas
- **Status dos Links**: Veja se os links estão online/offline

## Funcionamento do Failover

### Cenário de Failover
1. Sistema detecta que o link primário está offline
2. Verifica se o link secundário está online
3. Atualiza o registro DNS no Cloudflare para o IP secundário
4. Registra a alteração nos logs

### Cenário de Failback
1. Sistema detecta que o link primário voltou online
2. Atualiza o registro DNS no Cloudflare para o IP primário
3. Registra a alteração nos logs

## Tipos de Records Suportados

- **A**: Para endereços IPv4
- **AAAA**: Para endereços IPv6
- **CNAME**: Para redirecionamentos de hostname

### Acessar

Abra: `http://localhost:8501`

## Estrutura do Projeto

```
cloudflare-failover/
├── app/
│   ├── main.py           # Aplicação Streamlit
│   ├── db.py             # Operações com banco de dados
│   ├── cloudflare.py     # Integração com API Cloudflare
│   └── monitor.py        # Monitoramento e failover
├── data/                 # Banco de dados SQLite
├── logs/                 # Logs da aplicação
├── requirements.txt      # Dependências Python
├── Dockerfile           # Configuração Docker
├── docker-compose.yml   # Orquestração Docker
└── README.md            # Este arquivo
```

### Erro no banco de dados
- Verifique as permissões da pasta `data/`
- Delete o arquivo `data/cloudflare_failover.db` para recriar

## Logs

Os logs são salvos em:
- **Aplicação**: `logs/monitor.log`
- **Docker**: `docker-compose logs cloudflare-failover`
