"""
database.py - Gerenciamento completo do banco de dados SQLite
Contém todas as funções de criação de tabelas e operações CRUD.
"""

import sqlite3
from config import DATABASE_PATH


def get_connection():
    """Retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas pelo nome
    return conn


def criar_tabelas():
    """Cria todas as tabelas do banco de dados, se não existirem."""
    conn = get_connection()
    cursor = conn.cursor()

    # ── Membros da facção ────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS membros (
            discord_id   TEXT PRIMARY KEY,
            nome         TEXT NOT NULL,
            id_jogo      TEXT,
            cargo        TEXT,
            data_entrada TEXT,
            farm_total   INTEGER DEFAULT 0,
            farm_semanal INTEGER DEFAULT 0,
            c4_total     INTEGER DEFAULT 0,
            advertencias INTEGER DEFAULT 0,
            punicoes     INTEGER DEFAULT 0,
            presencas    INTEGER DEFAULT 0,
            faltas       INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'ativo'
        )
    """)

    # ── Registros de farm ────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS farm (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id     TEXT NOT NULL,
            quantidade     INTEGER NOT NULL,
            tipo           TEXT,
            responsavel_id TEXT,
            data           TEXT
        )
    """)

    # ── Registros de entrega de C4 ───────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS c4 (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id     TEXT NOT NULL,
            quantidade     INTEGER NOT NULL,
            responsavel_id TEXT,
            data           TEXT
        )
    """)

    # ── Advertências ─────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS advertencias (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id     TEXT NOT NULL,
            motivo         TEXT,
            responsavel_id TEXT,
            data           TEXT
        )
    """)

    # ── Punições ──────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS punicoes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id     TEXT NOT NULL,
            motivo         TEXT,
            tipo           TEXT,
            responsavel_id TEXT,
            data           TEXT
        )
    """)

    # ── Reuniões ──────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reunioes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo    TEXT NOT NULL,
            data      TEXT,
            horario   TEXT,
            descricao TEXT,
            criada_por TEXT
        )
    """)

    # ── Presenças nas reuniões ────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presencas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            reuniao_id   INTEGER NOT NULL,
            discord_id   TEXT NOT NULL,
            status       TEXT,
            justificativa TEXT
        )
    """)

    # ── Solicitações de ausência ──────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ausencias (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id   TEXT NOT NULL,
            motivo       TEXT,
            data         TEXT,
            status       TEXT DEFAULT 'pendente',
            aprovado_por TEXT
        )
    """)

    # ── Entregas de Meta (C4 / Plásticos) ────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entregas_meta (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id     TEXT NOT NULL,
            tipo           TEXT NOT NULL,
            quantidade     INTEGER NOT NULL,
            responsavel_id TEXT NOT NULL,
            data           TEXT NOT NULL
        )
    """)

    # ── Bate-Ponto (registro de entrada/saída) ──────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bate_ponto (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id       TEXT NOT NULL,
            entrada          TEXT NOT NULL,
            saida            TEXT,
            duracao_segundos INTEGER DEFAULT 0,
            status           TEXT DEFAULT 'aberto'
        )
    """)

    # ── Configurações do bot (chave-valor) ────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    # ── Vínculos do Site (Discord API OAuth2) ──────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vinculos (
            discord_id TEXT PRIMARY KEY,
            data_vinculo TEXT NOT NULL
        )
    """)

    # ── Sistema de Tickets ────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_paineis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id    TEXT NOT NULL,
            canal_id    TEXT,
            mensagem_id TEXT,
            titulo      TEXT DEFAULT 'Central de Atendimento',
            descricao   TEXT DEFAULT 'Selecione o tipo de atendimento abaixo.',
            cor         TEXT DEFAULT '00FF7F',
            banner_url  TEXT DEFAULT '',
            thumbnail_url TEXT DEFAULT '',
            rodape      TEXT DEFAULT '⚔️ Facção Bot • Sistema de Tickets',
            tipo_menu   TEXT DEFAULT 'select'
        )
    """)

    # Tenta adicionar a coluna tipo_menu caso a tabela já existisse sem ela
    try:
        cursor.execute("ALTER TABLE ticket_paineis ADD COLUMN tipo_menu TEXT DEFAULT 'select'")
    except:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_opcoes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            painel_id       INTEGER NOT NULL,
            guild_id        TEXT NOT NULL,
            nome            TEXT NOT NULL,
            emoji           TEXT DEFAULT '🎫',
            descricao       TEXT DEFAULT '',
            categoria_id    TEXT NOT NULL,
            cargo_ids       TEXT NOT NULL,
            FOREIGN KEY (painel_id) REFERENCES ticket_paineis(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets_abertos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id        TEXT NOT NULL,
            canal_id        TEXT NOT NULL UNIQUE,
            autor_id        TEXT NOT NULL,
            opcao_nome      TEXT NOT NULL,
            painel_id       INTEGER NOT NULL,
            aberto_em       TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Tabelas criadas/verificadas com sucesso.")



# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE VÍNCULO (SITE)
# ═══════════════════════════════════════════════════════════════════

def registrar_vinculo(discord_id: str):
    """Registra ou atualiza o vínculo de um usuário que logou no site."""
    conn = get_connection()
    data = sqlite3.connect(DATABASE_PATH).execute("SELECT datetime('now')").fetchone()[0]
    conn.execute(
        "INSERT OR REPLACE INTO vinculos (discord_id, data_vinculo) VALUES (?, ?)",
        (discord_id, data)
    )
    conn.commit()
    conn.close()

def get_vinculo(discord_id: str):
    """Verifica se o usuário possui vínculo registrado no site."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM vinculos WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return row

# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE MEMBROS
# ═══════════════════════════════════════════════════════════════════

def registrar_membro(discord_id: str, nome: str, id_jogo: str, cargo: str, data_entrada: str):
    """Registra um novo membro no banco de dados."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO membros (discord_id, nome, id_jogo, cargo, data_entrada) VALUES (?, ?, ?, ?, ?)",
            (discord_id, nome, id_jogo, cargo, data_entrada)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Membro já existe
    finally:
        conn.close()


def remover_membro(discord_id: str):
    """Remove um membro 100% do banco de dados (DELETE completo)."""
    conn = get_connection()
    conn.execute("DELETE FROM membros WHERE discord_id = ?", (discord_id,))
    conn.execute("DELETE FROM entregas_meta WHERE discord_id = ?", (discord_id,))
    conn.execute("DELETE FROM farm WHERE discord_id = ?", (discord_id,))
    conn.execute("DELETE FROM c4 WHERE discord_id = ?", (discord_id,))
    conn.commit()
    conn.close()


def get_membro(discord_id: str):
    """Retorna os dados de um membro pelo discord_id."""
    conn = get_connection()
    membro = conn.execute("SELECT * FROM membros WHERE discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return membro


def get_todos_membros(status: str = 'ativo'):
    """Retorna todos os membros com determinado status."""
    conn = get_connection()
    membros = conn.execute("SELECT * FROM membros WHERE status = ?", (status,)).fetchall()
    conn.close()
    return membros


def editar_cargo_membro(discord_id: str, novo_cargo: str):
    """Atualiza o cargo de um membro."""
    conn = get_connection()
    conn.execute("UPDATE membros SET cargo = ? WHERE discord_id = ?", (novo_cargo, discord_id))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE FARM
# ═══════════════════════════════════════════════════════════════════

def adicionar_farm(discord_id: str, quantidade: int, tipo: str, responsavel_id: str, data: str):
    """Registra farm e atualiza totais do membro."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO farm (discord_id, quantidade, tipo, responsavel_id, data) VALUES (?, ?, ?, ?, ?)",
        (discord_id, quantidade, tipo, responsavel_id, data)
    )
    conn.execute(
        "UPDATE membros SET farm_total = farm_total + ?, farm_semanal = farm_semanal + ? WHERE discord_id = ?",
        (quantidade, quantidade, discord_id)
    )
    conn.commit()
    conn.close()


def remover_farm(discord_id: str, quantidade: int, responsavel_id: str, data: str, motivo: str):
    """Remove farm e atualiza totais do membro."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO farm (discord_id, quantidade, tipo, responsavel_id, data) VALUES (?, ?, ?, ?, ?)",
        (discord_id, -quantidade, f"REMOÇÃO: {motivo}", responsavel_id, data)
    )
    conn.execute(
        """UPDATE membros
           SET farm_total   = MAX(0, farm_total   - ?),
               farm_semanal = MAX(0, farm_semanal - ?)
           WHERE discord_id = ?""",
        (quantidade, quantidade, discord_id)
    )
    conn.commit()
    conn.close()


def get_ranking_farm(limite: int = 10):
    """Retorna o ranking de farm semanal."""
    conn = get_connection()
    ranking = conn.execute(
        "SELECT discord_id, nome, farm_semanal, farm_total FROM membros WHERE status='ativo' ORDER BY farm_semanal DESC LIMIT ?",
        (limite,)
    ).fetchall()
    conn.close()
    return ranking


def get_membros_sem_meta(meta: int):
    """Retorna membros que não bateram a meta semanal."""
    conn = get_connection()
    membros = conn.execute(
        "SELECT discord_id, nome, farm_semanal FROM membros WHERE status='ativo' AND farm_semanal < ?",
        (meta,)
    ).fetchall()
    conn.close()
    return membros


def resetar_farm_semanal():
    """Reseta o farm semanal de todos os membros."""
    conn = get_connection()
    conn.execute("UPDATE membros SET farm_semanal = 0 WHERE status = 'ativo'")
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE C4
# ═══════════════════════════════════════════════════════════════════

def entregar_c4(discord_id: str, quantidade: int, responsavel_id: str, data: str):
    """Registra entrega de C4."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO c4 (discord_id, quantidade, responsavel_id, data) VALUES (?, ?, ?, ?)",
        (discord_id, quantidade, responsavel_id, data)
    )
    conn.execute(
        "UPDATE membros SET c4_total = c4_total + ? WHERE discord_id = ?",
        (quantidade, discord_id)
    )
    conn.commit()
    conn.close()


def get_ranking_c4(limite: int = 10):
    """Retorna o ranking de C4."""
    conn = get_connection()
    ranking = conn.execute(
        "SELECT discord_id, nome, c4_total FROM membros WHERE status='ativo' ORDER BY c4_total DESC LIMIT ?",
        (limite,)
    ).fetchall()
    conn.close()
    return ranking


# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE ADVERTÊNCIAS E PUNIÇÕES
# ═══════════════════════════════════════════════════════════════════

def aplicar_advertencia(discord_id: str, motivo: str, responsavel_id: str, data: str):
    """Aplica uma advertência ao membro."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO advertencias (discord_id, motivo, responsavel_id, data) VALUES (?, ?, ?, ?)",
        (discord_id, motivo, responsavel_id, data)
    )
    conn.execute("UPDATE membros SET advertencias = advertencias + 1 WHERE discord_id = ?", (discord_id,))
    conn.commit()
    conn.close()


def remover_ultima_advertencia(discord_id: str) -> bool:
    """Remove a última advertência de um membro. Retorna True se removeu."""
    conn = get_connection()
    ultima = conn.execute(
        "SELECT id FROM advertencias WHERE discord_id = ? ORDER BY id DESC LIMIT 1", (discord_id,)
    ).fetchone()
    if ultima:
        conn.execute("DELETE FROM advertencias WHERE id = ?", (ultima['id'],))
        conn.execute(
            "UPDATE membros SET advertencias = MAX(0, advertencias - 1) WHERE discord_id = ?", (discord_id,)
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def aplicar_punicao(discord_id: str, motivo: str, tipo: str, responsavel_id: str, data: str):
    """Aplica uma punição ao membro."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO punicoes (discord_id, motivo, tipo, responsavel_id, data) VALUES (?, ?, ?, ?, ?)",
        (discord_id, motivo, tipo, responsavel_id, data)
    )
    conn.execute("UPDATE membros SET punicoes = punicoes + 1 WHERE discord_id = ?", (discord_id,))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE REUNIÕES E PRESENÇAS
# ═══════════════════════════════════════════════════════════════════

def marcar_reuniao(titulo: str, data: str, horario: str, descricao: str, criada_por: str) -> int:
    """Cria uma reunião e retorna o ID gerado."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO reunioes (titulo, data, horario, descricao, criada_por) VALUES (?, ?, ?, ?, ?)",
        (titulo, data, horario, descricao, criada_por)
    )
    reuniao_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return reuniao_id


def get_reuniao(reuniao_id: int):
    """Retorna uma reunião pelo ID."""
    conn = get_connection()
    reuniao = conn.execute("SELECT * FROM reunioes WHERE id = ?", (reuniao_id,)).fetchone()
    conn.close()
    return reuniao


def confirmar_presenca(reuniao_id: int, discord_id: str, status: str, justificativa: str = ""):
    """Registra ou atualiza a presença de um membro em uma reunião."""
    conn = get_connection()
    existente = conn.execute(
        "SELECT id FROM presencas WHERE reuniao_id = ? AND discord_id = ?",
        (reuniao_id, discord_id)
    ).fetchone()

    if existente:
        conn.execute(
            "UPDATE presencas SET status = ?, justificativa = ? WHERE reuniao_id = ? AND discord_id = ?",
            (status, justificativa, reuniao_id, discord_id)
        )
    else:
        conn.execute(
            "INSERT INTO presencas (reuniao_id, discord_id, status, justificativa) VALUES (?, ?, ?, ?)",
            (reuniao_id, discord_id, status, justificativa)
        )

    # Atualiza contadores do membro
    if status == "presente":
        conn.execute("UPDATE membros SET presencas = presencas + 1 WHERE discord_id = ?", (discord_id,))
    elif status == "falta":
        conn.execute("UPDATE membros SET faltas = faltas + 1 WHERE discord_id = ?", (discord_id,))

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE AUSÊNCIAS
# ═══════════════════════════════════════════════════════════════════

def registrar_ausencia(discord_id: str, motivo: str, data: str) -> int:
    """Registra uma solicitação de ausência. Retorna o ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO ausencias (discord_id, motivo, data) VALUES (?, ?, ?)",
        (discord_id, motivo, data)
    )
    ausencia_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ausencia_id


def get_ausencia(ausencia_id: int):
    """Retorna uma ausência pelo ID."""
    conn = get_connection()
    ausencia = conn.execute("SELECT * FROM ausencias WHERE id = ?", (ausencia_id,)).fetchone()
    conn.close()
    return ausencia


def aprovar_ausencia(ausencia_id: int, aprovado_por: str):
    """Aprova uma solicitação de ausência."""
    conn = get_connection()
    conn.execute(
        "UPDATE ausencias SET status = 'aprovada', aprovado_por = ? WHERE id = ?",
        (aprovado_por, ausencia_id)
    )
    conn.commit()
    conn.close()


def recusar_ausencia(ausencia_id: int, aprovado_por: str):
    """Recusa uma solicitação de ausência."""
    conn = get_connection()
    conn.execute(
        "UPDATE ausencias SET status = 'recusada', aprovado_por = ? WHERE id = ?",
        (aprovado_por, ausencia_id)
    )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE RELATÓRIOS
# ═══════════════════════════════════════════════════════════════════

def get_estatisticas_gerais():
    """Retorna estatísticas gerais da facção."""
    conn = get_connection()

    total_membros  = conn.execute("SELECT COUNT(*) FROM membros WHERE status='ativo'").fetchone()[0]
    total_farm     = conn.execute("SELECT SUM(farm_total) FROM membros WHERE status='ativo'").fetchone()[0] or 0
    total_c4       = conn.execute("SELECT SUM(c4_total) FROM membros WHERE status='ativo'").fetchone()[0] or 0
    total_adv      = conn.execute("SELECT COUNT(*) FROM advertencias").fetchone()[0]
    total_pun      = conn.execute("SELECT COUNT(*) FROM punicoes").fetchone()[0]
    total_presencas= conn.execute("SELECT SUM(presencas) FROM membros WHERE status='ativo'").fetchone()[0] or 0
    total_faltas   = conn.execute("SELECT SUM(faltas) FROM membros WHERE status='ativo'").fetchone()[0] or 0

    # Top 3 mais ativos (por farm semanal)
    top_ativos = conn.execute(
        "SELECT discord_id, nome, farm_semanal FROM membros WHERE status='ativo' ORDER BY farm_semanal DESC LIMIT 3"
    ).fetchall()

    # Membros parados (sem farm na semana)
    parados = conn.execute(
        "SELECT discord_id, nome FROM membros WHERE status='ativo' AND farm_semanal = 0"
    ).fetchall()

    conn.close()
    return {
        "total_membros": total_membros,
        "total_farm": total_farm,
        "total_c4": total_c4,
        "total_advertencias": total_adv,
        "total_punicoes": total_pun,
        "total_presencas": total_presencas,
        "total_faltas": total_faltas,
        "top_ativos": top_ativos,
        "parados": parados,
    }

def get_ranking_metas(limite: int = 3):
    """Retorna os membros com mais itens entregues para metas."""
    conn = get_connection()
    ranking = conn.execute(
        """SELECT m.discord_id, m.nome, SUM(e.quantidade) as total_entregas
           FROM membros m
           JOIN entregas_meta e ON m.discord_id = e.discord_id
           WHERE m.status = 'ativo'
           GROUP BY m.discord_id
           ORDER BY total_entregas DESC
           LIMIT ?""",
        (limite,)
    ).fetchall()
    conn.close()
    return ranking

def get_membros_exemplares(limite: int = 5):
    """Retorna membros sem punições/advertências e com atividade."""
    conn = get_connection()
    membros = conn.execute(
        """SELECT discord_id, nome, farm_semanal
           FROM membros 
           WHERE status = 'ativo' 
             AND punicoes = 0 
             AND advertencias = 0
             AND farm_semanal > 0
           ORDER BY farm_semanal DESC
           LIMIT ?""",
        (limite,)
    ).fetchall()
    conn.close()
    return membros

def get_inativos():
    """Retorna membros que estão com 0 farm e 0 ponto na semana (ou seja, inativos).
       Como o ponto não zera semanalmente de forma explícita na mesma tabela,
       verificamos se eles têm 0 farm e não têm entregas de meta recentes."""
    conn = get_connection()
    membros = conn.execute(
        """SELECT m.discord_id, m.nome 
           FROM membros m
           WHERE m.status = 'ativo' 
             AND m.farm_semanal = 0
             AND m.discord_id NOT IN (
                 SELECT discord_id FROM entregas_meta
             )
        """
    ).fetchall()
    conn.close()
    return membros

# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE METAS (C4 / PLÁSTICOS)
# ═══════════════════════════════════════════════════════════════════

def registrar_entrega_meta(discord_id: str, tipo: str, quantidade: int, responsavel_id: str, data: str):
    """Registra uma entrega de meta (c4 ou plasticos)."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO entregas_meta (discord_id, tipo, quantidade, responsavel_id, data) VALUES (?, ?, ?, ?, ?)",
        (discord_id, tipo, quantidade, responsavel_id, data)
    )
    conn.commit()
    conn.close()


def editar_entrega_meta(discord_id: str, tipo: str, nova_quantidade: int, responsavel_id: str, data: str):
    """Edita o total de entregas de um tipo para um membro (remove anteriores e cria novo)."""
    conn = get_connection()
    conn.execute("DELETE FROM entregas_meta WHERE discord_id = ? AND tipo = ?", (discord_id, tipo))
    conn.execute(
        "INSERT INTO entregas_meta (discord_id, tipo, quantidade, responsavel_id, data) VALUES (?, ?, ?, ?, ?)",
        (discord_id, tipo, nova_quantidade, responsavel_id, data)
    )
    conn.commit()
    conn.close()


def get_total_por_tipo(discord_id: str) -> dict:
    """Retorna o total de entregas por tipo para um membro."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT tipo, SUM(quantidade) as total FROM entregas_meta WHERE discord_id = ? GROUP BY tipo",
        (discord_id,)
    ).fetchall()
    conn.close()
    
    totais = {"c4": 0, "plasticos": 0, "colete": 0, "corda": 0, "capuz": 0, "chave_verde": 0, "chave_vermelha": 0, "chave_amarela": 0}
    for r in rows:
        totais[r['tipo']] = r['total']
    return totais

def get_metas_ativas() -> dict:
    """Retorna um dicionário com os tipos de metas ativas e suas quantidades necessárias."""
    conn = get_connection()
    rows = conn.execute("SELECT chave, valor FROM bot_config WHERE chave LIKE 'meta_%'").fetchall()
    conn.close()
    
    metas = {}
    for r in rows:
        tipo = r['chave'].replace('meta_', '')
        try:
            val = int(r['valor'])
            if val > 0:
                metas[tipo] = val
        except ValueError:
            pass
            
    # Valores padrão iniciais se nada estiver configurado
    if not metas:
        # Import local para não dar circular import se fosse no topo
        from config import META_C4_MINIMA, META_PLASTICOS_MINIMA
        return {"c4": META_C4_MINIMA, "plasticos": META_PLASTICOS_MINIMA}
        
    return metas

def set_meta_ativa(tipo: str, quantidade: int):
    """Ativa ou desativa (quantidade=0) uma meta para um tipo."""
    set_config(f"meta_{tipo}", str(quantidade))

def get_modo_meta() -> str:
    """Retorna o modo da meta: 'ou' (qualquer item) ou 'e' (todos os itens)."""
    modo = get_config("modo_meta")
    return modo if modo in ["ou", "e"] else "ou"

def set_modo_meta(modo: str):
    """Define o modo da meta."""
    set_config("modo_meta", modo)


def get_entregas_membro(discord_id: str):
    """Retorna todas as entregas de um membro."""
    conn = get_connection()
    entregas = conn.execute(
        "SELECT * FROM entregas_meta WHERE discord_id = ? ORDER BY id DESC", (discord_id,)
    ).fetchall()
    conn.close()
    return entregas


def resetar_entregas_meta():
    """Remove todas as entregas de meta (para novo período)."""
    conn = get_connection()
    conn.execute("DELETE FROM entregas_meta")
    conn.commit()
    conn.close()


def get_punicoes_lista(discord_id: str):
    """Retorna lista de punições de um membro."""
    conn = get_connection()
    punicoes = conn.execute(
        "SELECT * FROM punicoes WHERE discord_id = ? ORDER BY id DESC", (discord_id,)
    ).fetchall()
    conn.close()
    return punicoes


def remover_ultima_punicao(discord_id: str) -> bool:
    """Remove a última punição de um membro. Retorna True se removeu."""
    conn = get_connection()
    ultima = conn.execute(
        "SELECT id FROM punicoes WHERE discord_id = ? ORDER BY id DESC LIMIT 1", (discord_id,)
    ).fetchone()
    if ultima:
        conn.execute("DELETE FROM punicoes WHERE id = ?", (ultima['id'],))
        conn.execute(
            "UPDATE membros SET punicoes = MAX(0, punicoes - 1) WHERE discord_id = ?", (discord_id,)
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE BATE-PONTO
# ═══════════════════════════════════════════════════════════════════

def registrar_ponto_entrada(discord_id: str, entrada: str):
    """Registra um ponto de entrada para o membro."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO bate_ponto (discord_id, entrada, status) VALUES (?, ?, 'aberto')",
        (discord_id, entrada)
    )
    conn.commit()
    conn.close()


def get_ponto_aberto(discord_id: str):
    """Retorna o ponto aberto de um membro, se existir."""
    conn = get_connection()
    ponto = conn.execute(
        "SELECT * FROM bate_ponto WHERE discord_id = ? AND status = 'aberto' ORDER BY id DESC LIMIT 1",
        (discord_id,)
    ).fetchone()
    conn.close()
    return ponto


def fechar_ponto(ponto_id: int, saida: str, duracao_segundos: int):
    """Fecha um ponto, registrando a saída e a duração."""
    conn = get_connection()
    conn.execute(
        "UPDATE bate_ponto SET saida = ?, duracao_segundos = ?, status = 'fechado' WHERE id = ?",
        (saida, duracao_segundos, ponto_id)
    )
    conn.commit()
    conn.close()


def get_historico_ponto(discord_id: str, limite: int = 10):
    """Retorna os últimos registros de ponto de um membro."""
    conn = get_connection()
    registros = conn.execute(
        "SELECT * FROM bate_ponto WHERE discord_id = ? ORDER BY id DESC LIMIT ?",
        (discord_id, limite)
    ).fetchall()
    conn.close()
    return registros


def deletar_ultimo_ponto(discord_id: str):
    """Deleta o último registro de ponto do membro."""
    conn = get_connection()
    # Pega o ID do último registro
    ultimo = conn.execute(
        "SELECT id FROM bate_ponto WHERE discord_id = ? ORDER BY id DESC LIMIT 1",
        (discord_id,)
    ).fetchone()
    
    if ultimo:
        conn.execute("DELETE FROM bate_ponto WHERE id = ?", (ultimo['id'],))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False


def get_ranking_ponto(limite: int = 15):
    """Retorna o ranking de tempo de serviço total dos membros."""
    conn = get_connection()
    ranking = conn.execute(
        """SELECT discord_id,
                  SUM(duracao_segundos) AS tempo_total,
                  COUNT(*) AS total_pontos
           FROM bate_ponto
           WHERE status = 'fechado'
           GROUP BY discord_id
           ORDER BY tempo_total DESC
           LIMIT ?""",
        (limite,)
    ).fetchall()
    conn.close()
    return ranking


# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE CONFIGURAÇÃO (CHAVE-VALOR)
# ═══════════════════════════════════════════════════════════════════

def get_config(chave: str) -> str | None:
    """Retorna o valor de uma configuração pelo nome da chave."""
    conn = get_connection()
    row = conn.execute("SELECT valor FROM bot_config WHERE chave = ?", (chave,)).fetchone()
    conn.close()
    return row['valor'] if row else None


def set_config(chave: str, valor: str):
    """Define ou atualiza uma configuração no banco."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO bot_config (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor = ?",
        (chave, valor, valor)
    )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════
#  FUNÇÕES DE TICKETS
# ═══════════════════════════════════════════════════════════════════

def ticket_get_painel(guild_id: str):
    """Retorna o painel de tickets do servidor."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM ticket_paineis WHERE guild_id = ?", (guild_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def ticket_criar_painel(guild_id: str) -> int:
    """Cria um painel de tickets padrão para o servidor e retorna o id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO ticket_paineis (guild_id) VALUES (?)", (guild_id,)
        )
        conn.commit()
        painel_id = cursor.lastrowid
    except:
        painel_id = 0
    conn.close()
    
    if painel_id == 0:
        painel = ticket_get_painel(guild_id)
        return painel['id'] if painel else 0
    return painel_id


def ticket_editar_painel(guild_id: str, **campos):
    """Edita campos do painel de tickets."""
    conn = get_connection()
    try:
        for chave, valor in campos.items():
            conn.execute(
                f"UPDATE ticket_paineis SET {chave} = ? WHERE guild_id = ?",
                (valor, guild_id)
            )
        conn.commit()
    finally:
        conn.close()


def ticket_get_opcoes(guild_id: str):
    """Retorna todas as opções de ticket do servidor."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM ticket_opcoes WHERE guild_id = ? ORDER BY id", (guild_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ticket_add_opcao(painel_id: int, guild_id: str, nome: str, emoji: str,
                     descricao: str, categoria_id: str, cargo_ids: str):
    """Adiciona uma opção de ticket."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO ticket_opcoes (painel_id, guild_id, nome, emoji, descricao, categoria_id, cargo_ids) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (painel_id, guild_id, nome, emoji, descricao, categoria_id, cargo_ids)
    )
    conn.commit()
    conn.close()


def ticket_del_opcao(opcao_id: int, guild_id: str):
    """Remove uma opção de ticket."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM ticket_opcoes WHERE id = ? AND guild_id = ?", (opcao_id, guild_id)
    )
    conn.commit()
    conn.close()


def ticket_abrir(guild_id: str, canal_id: str, autor_id: str,
                 opcao_nome: str, painel_id: int, aberto_em: str):
    """Registra um ticket aberto."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO tickets_abertos (guild_id, canal_id, autor_id, opcao_nome, painel_id, aberto_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, canal_id, autor_id, opcao_nome, painel_id, aberto_em)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def ticket_fechar(canal_id: str):
    """Remove um ticket aberto do banco."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM tickets_abertos WHERE canal_id = ?", (canal_id,)
    ).fetchone()
    if row:
        conn.execute("DELETE FROM tickets_abertos WHERE canal_id = ?", (canal_id,))
        conn.commit()
    conn.close()
    return row


def ticket_get_aberto_por_autor(guild_id: str, autor_id: str, painel_id: int):
    """Verifica se o autor já tem um ticket aberto para esse painel."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM tickets_abertos WHERE guild_id = ? AND autor_id = ? AND painel_id = ?",
        (guild_id, autor_id, painel_id)
    ).fetchone()
    conn.close()
    return row
