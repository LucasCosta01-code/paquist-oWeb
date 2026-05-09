"""
config.py - Configurações centrais do bot
Aqui ficam os IDs de cargos, cores e outras configurações globais.
"""

import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# ─── TOKEN E IDs ───────────────────────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID         = int(os.getenv("LOG_CHANNEL_ID", 0))          # Canal de logs de ações do bot
LOG_CANAL_SERVIDOR_ID  = int(os.getenv("LOG_CANAL_SERVIDOR_ID", 0))   # Canal de logs do servidor (tudo)
META_FARM_SEMANAL      = int(os.getenv("META_FARM_SEMANAL", 50))      # Meta padrão de farm semanal
CANAL_AVISOS_ID        = 1496283836529770508                           # Canal oficial de avisos da facção

# ─── IDs DOS CARGOS DA FACÇÃO ──────────────────────────────────────────────────
CARGO_FUNDADOR_ID       = 1494537507310800928
CARGO_SUB_FUNDADOR_ID   = 1494537726916169799
CARGO_GERENTE_FARM_ID   = 1494537855739887758
CARGO_MEMBRO_ID         = 1492571692638277795   # Cargo dado ao entrar na facção
CARGO_OBRIGADO_META_ID  = 1492527673531171019  # Cargo que OBRIGA ter meta batida e ser membro

# ─── SISTEMA DE METAS (C4 / PLÁSTICOS) ────────────────────────────────────────
META_C4_MINIMA          = 75                    # Meta mínima de C4
META_PLASTICOS_MINIMA   = 300                   # Meta mínima de Plásticos
CARGO_BATEU_META_ID     = 1501043288654872727   # Cargo: bateu a meta
CARGO_NAO_BATEU_META_ID = 1501043713806438440   # Cargo: não bateu a meta
CANAL_REGISTRO_META_ID  = 1500605283892989952   # Canal de registro de entregas
CARGO_META_OBRIGATORIO_ID = 1492527673531171019  # Cargo que identifica quem precisa bater meta
CANAL_PATENTES_ID       = 1501069026607239208   # Canal de promoções e rebaixamentos

# ─── CONJUNTOS DE PERMISSÃO ────────────────────────────────────────────────────
# Cargos com permissão total
CARGOS_LIDERANCA = {CARGO_FUNDADOR_ID, CARGO_SUB_FUNDADOR_ID}

# Cargos com permissão de farm + liderança
CARGOS_FARM = {CARGO_FUNDADOR_ID, CARGO_SUB_FUNDADOR_ID, CARGO_GERENTE_FARM_ID}

# ─── CORES DOS EMBEDS ──────────────────────────────────────────────────────────
COR_PRINCIPAL   = 0xB22222   # Vermelho escuro (firebrick)
COR_SUCESSO     = 0x2ECC71   # Verde para sucesso
COR_ERRO        = 0xFF0000   # Vermelho para erros
COR_AVISO       = 0xFFA500   # Laranja para avisos
COR_INFO        = 0x2C2F33   # Cinza escuro para informações
COR_PRETA       = 0x1A1A1A   # Quase preta para embeds principais

# ─── CAMINHO DO BANCO DE DADOS ─────────────────────────────────────────────────
volume_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
DATABASE_PATH = os.path.join(volume_path, "faccao.db") if volume_path else "faccao.db"

# ─── SISTEMA DE BATE-PONTO ─────────────────────────────────────────────────────
CANAL_LOG_PONTO_ID        = 1501559832090775793   # Canal onde os logs de ponto são enviados
CANAL_BATER_PONTO_ID      = 1501560241643589762   # Canal onde membros batem o ponto
CARGO_EM_SERVICO_ID       = 1501564535725887539   # Cargo dado ao bater ponto (em serviço)
CARGO_FORA_SERVICO_ID     = 1501564591006810343   # Cargo dado ao parar ponto (fora de serviço)

# ─── WEBHOOK DE BOAS-VINDAS ────────────────────────────────────────────────────
WEBHOOK_BOAS_VINDAS = "https://discord.com/api/webhooks/1501559074536423465/Im-GvDvAcpVkhpTxmi2qLxLSUnAE71mw3VEW2w064GZGc_7DuwfIOjVzXE45ZSRHgAxr"
