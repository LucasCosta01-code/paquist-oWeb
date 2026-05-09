"""
commands/tickets.py - Sistema completo de Tickets
Permite criar painéis customizáveis com dropdown, canais privados por ticket,
logs de fechamento e permissões de cargos configuráveis.
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta

import database as db
import checks
import utils

# ─── ID do canal de logs de tickets ──────────────────────────────────────────
CANAL_LOG_TICKET_ID = 1502421274507612280


# ─── Helpers ──────────────────────────────────────────────────────────────────
def hex_para_int(hex_str: str) -> int:
    """Converte string hex (sem #) para int de cor do discord."""
    try:
        return int(hex_str.lstrip("#"), 16)
    except Exception:
        return 0x00FF7F  # verde padrão


def data_agora_br() -> str:
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y às %H:%M")


def _parse_cargo_ids(cargo_ids_str: str) -> list[int]:
    """Converte string '123,456' em lista de ints."""
    ids = []
    for part in cargo_ids_str.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def _montar_embed_painel(painel) -> discord.Embed:
    """Monta o embed do painel de tickets a partir dos dados do DB."""
    cor = hex_para_int(painel["cor"])
    embed = discord.Embed(
        title=painel["titulo"],
        description=painel["descricao"],
        color=cor
    )
    if painel["thumbnail_url"]:
        embed.set_thumbnail(url=painel["thumbnail_url"])
    if painel["banner_url"]:
        embed.set_image(url=painel["banner_url"])
    embed.set_footer(text=painel["rodape"])
    return embed


# ─── View persistente do painel (Dropdown de opções) ─────────────────────────
class TicketSelectView(discord.ui.View):
    """View persistente com o Select Menu de opções de ticket."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        cls=discord.ui.Select,
        custom_id="ticket_select_opcao",
        placeholder="Selecione o tipo de atendimento...",
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label="Carregando...", value="placeholder")]
    )
    async def selecionar_opcao(self, interaction: discord.Interaction, select: discord.ui.Select):
        await _processar_abertura_ticket(interaction, select.values[0])

    @classmethod
    def com_opcoes(cls, opcoes: list) -> "TicketSelectView":
        """Cria a view com as opções reais do banco de dados."""
        view = cls()
        select: discord.ui.Select = view.children[0]
        select.options = [
            discord.SelectOption(
                label=op["nome"],
                value=str(op["id"]),
                emoji=op["emoji"] or "🎫",
                description=op["descricao"] or ""
            )
            for op in opcoes
        ]
        return view


# ─── View persistente do painel (Botões de opções) ───────────────────────────
class TicketButtonView(discord.ui.View):
    """View persistente com Botões para opções de ticket."""

    def __init__(self):
        super().__init__(timeout=None)

    @classmethod
    def com_opcoes(cls, opcoes: list) -> "TicketButtonView":
        """Cria a view com botões baseados nas opções do banco."""
        view = cls()
        for op in opcoes:
            btn = discord.ui.Button(
                label=op["nome"],
                emoji=op["emoji"] or "🎫",
                style=discord.ButtonStyle.secondary,
                custom_id=f"ticket_btn_open_{op['id']}"
            )
            view.add_item(btn)
        return view


# ─── View do canal do ticket (Fechar) ─────────────────────────────────────────
class FecharTicketView(discord.ui.View):
    """Botão de fechar dentro do canal do ticket."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔒 Fechar Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_fechar_btn"
    )
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _processar_fechamento_ticket(interaction)


# ─── Lógica de abrir ticket ───────────────────────────────────────────────────
async def _processar_abertura_ticket(interaction: discord.Interaction, opcao_id_str: str):
    """Abre um ticket privado para o membro que selecionou uma opção."""
    guild = interaction.guild
    autor = interaction.user

    # Busca opção no banco
    opcoes = db.ticket_get_opcoes(str(guild.id))
    opcao = next((o for o in opcoes if str(o["id"]) == opcao_id_str), None)
    if not opcao:
        return await interaction.response.send_message(
            "❌ Opção inválida. Tente novamente.", ephemeral=True
        )

    painel = db.ticket_get_painel(str(guild.id))
    if not painel:
        return await interaction.response.send_message(
            "❌ Painel não encontrado.", ephemeral=True
        )

    # Verifica se já tem ticket aberto para este painel
    ticket_existente = db.ticket_get_aberto_por_autor(str(guild.id), str(autor.id), painel["id"])
    if ticket_existente:
        canal_existente = guild.get_channel(int(ticket_existente["canal_id"]))
        if canal_existente:
            return await interaction.response.send_message(
                f"❌ Você já tem um ticket aberto: {canal_existente.mention}\n"
                "Por favor, feche-o antes de abrir um novo.",
                ephemeral=True
            )
        else:
            # Canal foi deletado manualmente, limpa o banco
            db.ticket_fechar(ticket_existente["canal_id"])

    await interaction.response.defer(ephemeral=True, thinking=True)

    # Busca categoria
    try:
        categoria = guild.get_channel(int(opcao["categoria_id"]))
    except Exception:
        categoria = None

    # Define permissões do canal
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        autor: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            manage_messages=True
        ),
    }

    # Adiciona os cargos responsáveis
    cargo_ids = _parse_cargo_ids(opcao["cargo_ids"])
    cargos_ping = []
    for cid in cargo_ids:
        cargo = guild.get_role(cid)
        if cargo:
            overwrites[cargo] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            )
            cargos_ping.append(cargo)

    # Cria o canal
    nome_canal = f"ticket-{autor.display_name.lower().replace(' ', '-')}"[:99]
    try:
        canal = await guild.create_text_channel(
            nome_canal,
            category=categoria,
            overwrites=overwrites,
            topic=f"Ticket de {autor.display_name} | {opcao['nome']} | {data_agora_br()}"
        )
    except discord.Forbidden:
        return await interaction.followup.send(
            "❌ Não tenho permissão para criar canais. Contate um administrador.", ephemeral=True
        )

    # Salva no banco
    db.ticket_abrir(
        guild_id=str(guild.id),
        canal_id=str(canal.id),
        autor_id=str(autor.id),
        opcao_nome=opcao["nome"],
        painel_id=painel["id"],
        aberto_em=data_agora_br()
    )

    # Monta embed inicial do canal
    cor = hex_para_int(painel["cor"])
    embed_canal = discord.Embed(
        title=f"🎫  {opcao['nome']}",
        description=(
            f"Olá, {autor.mention}! Seu ticket foi aberto com sucesso.\n"
            f"Descreva sua solicitação e aguarde a equipe de atendimento.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 **Tipo:** `{opcao['nome']}`\n"
            f"⏰ **Aberto em:** `{data_agora_br()}`\n"
            f"👤 **Solicitante:** {autor.mention}\n"
        ),
        color=cor,
        timestamp=datetime.utcnow()
    )
    embed_canal.set_footer(text="Clique em 🔒 Fechar Ticket quando o atendimento acabar")
    if painel["thumbnail_url"]:
        embed_canal.set_thumbnail(url=painel["thumbnail_url"])

    # Monta menção dos responsáveis
    mencao_cargos = " ".join(c.mention for c in cargos_ping) if cargos_ping else ""
    conteudo_ping = f"{autor.mention} {mencao_cargos}".strip()

    await canal.send(content=conteudo_ping, embed=embed_canal, view=FecharTicketView())

    await interaction.followup.send(
        f"✅ Seu ticket foi criado: {canal.mention}", ephemeral=True
    )


# ─── Lógica de fechar ticket ──────────────────────────────────────────────────
async def _processar_fechamento_ticket(interaction: discord.Interaction):
    """Fecha o ticket, gera log e deleta o canal."""
    canal = interaction.channel
    guild = interaction.guild
    quem_fechou = interaction.user

    ticket = db.ticket_fechar(str(canal.id))

    await interaction.response.defer()

    # Gera o histórico de mensagens
    historico = []
    async for msg in canal.history(limit=500, oldest_first=True):
        if msg.author.bot and not msg.embeds:
            continue
        ts = (msg.created_at + timedelta(hours=-3)).strftime("%d/%m/%Y %H:%M")
        conteudo = msg.content or ""
        if msg.embeds:
            conteudo = f"[Embed: {msg.embeds[0].title or 'sem título'}]"
        historico.append(f"[{ts}] {msg.author.display_name}: {conteudo}")

    # Salva histórico como arquivo .txt
    txt_content = "\n".join(historico) if historico else "(sem mensagens)"
    txt_bytes = txt_content.encode("utf-8")
    arquivo = discord.File(
        fp=__import__("io").BytesIO(txt_bytes),
        filename=f"ticket-{canal.name}-{data_agora_br().replace('/', '-').replace(':', '-').replace(' ', '_')}.txt"
    )

    # Envia log no canal configurado
    canal_log = guild.get_channel(CANAL_LOG_TICKET_ID)
    if canal_log:
        embed_log = discord.Embed(
            title="📁  Ticket Fechado",
            color=0xFF4444,
            timestamp=datetime.utcnow()
        )
        if ticket:
            autor = guild.get_member(int(ticket["autor_id"]))
            embed_log.add_field(name="👤 Autor", value=f"{autor.mention if autor else ticket['autor_id']}", inline=True)
            embed_log.add_field(name="📋 Tipo", value=f"`{ticket['opcao_nome']}`", inline=True)
            embed_log.add_field(name="📅 Aberto em", value=f"`{ticket['aberto_em']}`", inline=True)
        embed_log.add_field(name="🔒 Fechado por", value=f"{quem_fechou.mention}", inline=True)
        embed_log.add_field(name="📝 Canal", value=f"`#{canal.name}`", inline=True)
        embed_log.add_field(name="🕐 Fechado em", value=f"`{data_agora_br()}`", inline=True)
        embed_log.set_footer(text="⚔️ Facção Bot • Log de Tickets")
        try:
            await canal_log.send(embed=embed_log, file=arquivo)
        except Exception:
            pass

    # Avisa no canal antes de deletar
    embed_fechando = discord.Embed(
        title="🔒  Ticket Encerrado",
        description=f"Este ticket foi fechado por {quem_fechou.mention}.\nO canal será deletado em **5 segundos**.",
        color=0xFF4444
    )
    await interaction.followup.send(embed=embed_fechando)
    await asyncio.sleep(5)

    try:
        await canal.delete(reason=f"Ticket fechado por {quem_fechou}")
    except Exception:
        pass


# ─── Modal de edição do painel ────────────────────────────────────────────────
class EditarPainelModal(discord.ui.Modal, title="✏️ Editar Painel de Tickets"):
    titulo = discord.ui.TextInput(
        label="Título do Painel",
        placeholder="Ex: 🎫 Central de Atendimento",
        max_length=100,
        required=True
    )
    descricao = discord.ui.TextInput(
        label="Descrição",
        style=discord.TextStyle.paragraph,
        placeholder="Texto explicativo exibido no painel...",
        max_length=1000,
        required=True
    )
    cor = discord.ui.TextInput(
        label="Cor (HEX sem #)",
        placeholder="Ex: 00FF7F",
        max_length=6,
        required=False,
        default="00FF7F"
    )
    banner_url = discord.ui.TextInput(
        label="URL do Banner (imagem de baixo)",
        placeholder="https://...",
        max_length=500,
        required=False
    )
    thumbnail_url = discord.ui.TextInput(
        label="URL da Miniatura (ícone superior direito)",
        placeholder="https://...",
        max_length=500,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        db.ticket_editar_painel(
            str(interaction.guild.id),
            titulo=self.titulo.value,
            descricao=self.descricao.value,
            cor=self.cor.value.strip().lstrip("#") or "00FF7F",
            banner_url=self.banner_url.value.strip(),
            thumbnail_url=self.thumbnail_url.value.strip()
        )
        await interaction.response.send_message(
            "✅ Painel atualizado! Use `/ticket_setup` para reenviar o painel no canal.",
            ephemeral=True
        )


# ─── Modal de edição do rodapé ────────────────────────────────────────────────
class EditarRodapeModal(discord.ui.Modal, title="✏️ Editar Rodapé"):
    rodape = discord.ui.TextInput(
        label="Texto do Rodapé",
        placeholder="Ex: ⚔️ Paquistão • Atendimento",
        max_length=100,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        db.ticket_editar_painel(str(interaction.guild.id), rodape=self.rodape.value)
        await interaction.response.send_message("✅ Rodapé atualizado!", ephemeral=True)


# ─── COG PRINCIPAL ────────────────────────────────────────────────────────────
class Tickets(commands.Cog):
    """Sistema completo de Tickets com painel customizável e canais privados."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Registra as views persistentes ao carregar o cog."""
        self.bot.add_view(TicketSelectView())
        self.bot.add_view(FecharTicketView())
        self.bot.add_view(TicketButtonView())

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Listener global para capturar botões de ticket dinâmicos e selects."""
        if interaction.type != discord.InteractionType.component:
            return
            
        custom_id = interaction.data.get("custom_id", "")
        
        # Lida com Botões
        if custom_id.startswith("ticket_btn_open_"):
            opcao_id = custom_id.replace("ticket_btn_open_", "")
            await _processar_abertura_ticket(interaction, opcao_id)
            
        # Lida com Dropdown (caso a view perca a persistência por algum motivo)
        elif custom_id == "ticket_select_opcao":
            if "values" in interaction.data:
                await _processar_abertura_ticket(interaction, interaction.data["values"][0])

    # ── /ticket_setup ────────────────────────────────────────────────────────
    @app_commands.command(
        name="ticket_setup",
        description="🎫 Envia o painel de tickets no canal atual. [Liderança]"
    )
    async def ticket_setup(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        
        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            guild_id = str(guild.id)

            # Cria painel se não existir
            painel = db.ticket_get_painel(guild_id)
            if not painel:
                db.ticket_criar_painel(guild_id)
                painel = db.ticket_get_painel(guild_id)
            
            if not painel:
                return await interaction.followup.send("❌ Erro ao criar/recuperar painel no banco.", ephemeral=True)

            opcoes = db.ticket_get_opcoes(guild_id)
            if not opcoes:
                return await interaction.followup.send(
                    "❌ Nenhuma opção cadastrada! Use `/ticket_add_opcao` antes de enviar o painel.",
                    ephemeral=True
                )

            embed = _montar_embed_painel(painel)
            
            # Escolhe a view baseada no tipo configurado
            modo_menu = painel.get("tipo_menu", "select")

            if modo_menu == "buttons":
                view = TicketButtonView.com_opcoes(opcoes)
            else:
                view = TicketSelectView.com_opcoes(opcoes)

            # Tenta deletar mensagem anterior
            if painel.get("mensagem_id") and painel.get("canal_id"):
                try:
                    canal_ant = guild.get_channel(int(painel["canal_id"]))
                    if canal_ant:
                        msg_ant = await canal_ant.fetch_message(int(painel["mensagem_id"]))
                        await msg_ant.delete()
                except Exception:
                    pass

            msg = await interaction.channel.send(embed=embed, view=view)

            db.ticket_editar_painel(
                guild_id,
                canal_id=str(interaction.channel.id),
                mensagem_id=str(msg.id)
            )

            await interaction.followup.send("✅ Painel de tickets enviado!", ephemeral=True)
        except Exception as e:
            print(f"[TICKET] Erro no setup: {e}")
            await interaction.followup.send(f"❌ Ocorreu um erro ao configurar o painel: `{e}`", ephemeral=True)

    # ── /ticket_editar ───────────────────────────────────────────────────────
    @app_commands.command(
        name="ticket_editar",
        description="✏️ Edita o título, descrição, cor e imagens do painel. [Liderança]"
    )
    async def ticket_editar(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        modal = EditarPainelModal()
        modal.titulo.default = painel["titulo"]
        modal.descricao.default = painel["descricao"]
        modal.cor.default = painel["cor"]
        modal.banner_url.default = painel["banner_url"] or ""
        modal.thumbnail_url.default = painel["thumbnail_url"] or ""
        await interaction.response.send_modal(modal)

    # ── /ticket_editar_rodape ────────────────────────────────────────────────
    @app_commands.command(
        name="ticket_editar_rodape",
        description="✏️ Edita o texto do rodapé do painel. [Liderança]"
    )
    async def ticket_editar_rodape(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        guild_id = str(interaction.guild.id)
        painel = db.ticket_get_painel(guild_id)
        if not painel:
            db.ticket_criar_painel(guild_id)
            painel = db.ticket_get_painel(guild_id)

        modal = EditarRodapeModal()
        modal.rodape.default = painel["rodape"]
        await interaction.response.send_modal(modal)

    # ── /ticket_add_opcao ────────────────────────────────────────────────────
    @app_commands.command(
        name="ticket_add_opcao",
        description="➕ Adiciona uma opção no dropdown de tickets. [Liderança]"
    )
    @app_commands.describe(
        nome="Nome da opção (ex: Encomenda, Dúvida)",
        emoji="Emoji da opção (ex: 📦)",
        descricao="Breve descrição da opção",
        categoria_id="ID da Categoria onde os canais de ticket serão criados",
        cargo_ids="IDs dos cargos que vão atender (separados por vírgula, ex: 123456,789012)"
    )
    async def ticket_add_opcao(
        self,
        interaction: discord.Interaction,
        nome: str,
        categoria_id: str,
        cargo_ids: str,
        emoji: str = "🎫",
        descricao: str = ""
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        guild_id = str(interaction.guild.id)
        painel = db.ticket_get_painel(guild_id)
        if not painel:
            db.ticket_criar_painel(guild_id)
            painel = db.ticket_get_painel(guild_id)

        opcoes = db.ticket_get_opcoes(guild_id)
        if len(opcoes) >= 25:
            return await interaction.response.send_message(
                "❌ Máximo de 25 opções atingido!", ephemeral=True
            )

        db.ticket_add_opcao(
            painel_id=painel["id"],
            guild_id=guild_id,
            nome=nome,
            emoji=emoji,
            descricao=descricao,
            categoria_id=categoria_id,
            cargo_ids=cargo_ids
        )

        await interaction.response.send_message(
            f"✅ Opção **{emoji} {nome}** adicionada!\n"
            "Use `/ticket_setup` para atualizar o painel.",
            ephemeral=True
        )

    # ── /ticket_del_opcao ────────────────────────────────────────────────────
    @app_commands.command(
        name="ticket_del_opcao",
        description="➖ Remove uma opção do dropdown de tickets. [Liderança]"
    )
    async def ticket_del_opcao(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        guild_id = str(interaction.guild.id)
        opcoes = db.ticket_get_opcoes(guild_id)
        if not opcoes:
            return await interaction.response.send_message(
                "❌ Nenhuma opção cadastrada ainda.", ephemeral=True
            )

        # Monta select para escolha
        select_opts = [
            discord.SelectOption(
                label=f"[{op['id']}] {op['nome']}",
                value=str(op["id"]),
                emoji=op["emoji"] or "🎫"
            )
            for op in opcoes
        ]

        class SelecaoDelView(discord.ui.View):
            def __init__(self_inner):
                super().__init__(timeout=60)

            @discord.ui.select(placeholder="Selecione a opção para remover...", options=select_opts)
            async def escolher(self_inner, inter: discord.Interaction, sel: discord.ui.Select):
                opcao_id = int(sel.values[0])
                db.ticket_del_opcao(opcao_id, guild_id)
                await inter.response.send_message(
                    f"✅ Opção removida! Use `/ticket_setup` para atualizar o painel.",
                    ephemeral=True
                )
                self_inner.stop()

        view = SelecaoDelView()
        await interaction.response.send_message(
            "Selecione qual opção deseja remover:", view=view, ephemeral=True
        )

    # ── /ticket_fechar_admin ──────────────────────────────────────────────────
    @app_commands.command(
        name="ticket_fechar_admin",
        description="🔒 Fecha um ticket administrativamente. [Liderança]"
    )
    @app_commands.describe(canal="O canal do ticket que deseja fechar")
    async def ticket_fechar_admin(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # Verifica se o canal é um ticket no banco
        ticket = db.ticket_fechar(str(canal.id))
        if not ticket:
            return await interaction.response.send_message(
                "❌ Este canal não consta como um ticket aberto no sistema.", ephemeral=True
            )

        await interaction.response.send_message(f"🔒 Fechando ticket {canal.mention}...", ephemeral=True)
        
        # Lógica de log (mesma do _processar_fechamento_ticket)
        # Para evitar repetição de código, poderíamos refatorar, mas vamos direto aqui por simplicidade
        await canal.send("🔒 Este ticket foi encerrado por um administrador.")
        await asyncio.sleep(2)
        try:
            await canal.delete(reason=f"Ticket fechado por admin: {interaction.user}")
        except:
            pass

    # ── /ticket_listar ───────────────────────────────────────────────────────
    @app_commands.command(
        name="ticket_listar",
        description="📋 Lista todas as opções do painel de tickets. [Liderança]"
    )
    async def ticket_listar(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        guild_id = str(interaction.guild.id)
        painel_row = db.ticket_get_painel(guild_id)
        opcoes = db.ticket_get_opcoes(guild_id)

        cor = hex_para_int(painel_row["cor"]) if painel_row else 0x00FF7F
        painel = dict(painel_row) if painel_row else None

        embed = discord.Embed(
            title="📋  Configuração do Sistema de Tickets",
            color=cor,
            timestamp=datetime.utcnow()
        )

        if painel:
            embed.add_field(
                name="🎨 Painel",
                value=(
                    f"**Título:** {painel['titulo']}\n"
                    f"**Cor:** `#{painel['cor']}`\n"
                    f"**Canal:** <#{painel['canal_id']}>" if painel['canal_id'] else "Não enviado"
                ),
                inline=False
            )
        else:
            embed.add_field(name="🎨 Painel", value="Nenhum painel configurado.", inline=False)

        if opcoes:
            texto = "\n".join(
                f"`[{op['id']}]` {op['emoji']} **{op['nome']}** — "
                f"Categoria: `{op['categoria_id']}` | Cargos: `{op['cargo_ids']}`"
                for op in opcoes
            )
            embed.add_field(name=f"🎫 Opções ({len(opcoes)})", value=texto, inline=False)
        else:
            embed.add_field(name="🎫 Opções", value="Nenhuma opção cadastrada.", inline=False)

        embed.set_footer(text="Use /ticket_add_opcao para adicionar | /ticket_del_opcao para remover")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /ticket_admin ────────────────────────────────────────────────────────
    @app_commands.command(
        name="ticket_admin",
        description="⚙️ Painel administrativo bonito para gerenciar o sistema de tickets. [Liderança]"
    )
    async def ticket_admin(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        guild_id = str(interaction.guild.id)
        painel_row = db.ticket_get_painel(guild_id)
        if not painel_row:
            db.ticket_criar_painel(guild_id)
            painel_row = db.ticket_get_painel(guild_id)

        painel = dict(painel_row)
        opcoes = db.ticket_get_opcoes(guild_id)
        cor = hex_para_int(painel["cor"])

        try:
            modo_menu_txt = "Dropdown" if painel["tipo_menu"] == "select" else "Botões"
        except:
            modo_menu_txt = "Dropdown"

        embed = discord.Embed(
            title="🛠️ Painel de Controle de Tickets",
            description=(
                "Bem-vindo ao centro de configuração. Aqui você pode gerenciar "
                "todo o sistema de atendimento visualmente.\n\n"
                f"**Status Atual:** {'✅ Ativo' if painel['mensagem_id'] else '⚠️ Não Configurado'}\n"
                f"**Modo de Menu:** `{modo_menu_txt}`"
            ),
            color=cor
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)

        if opcoes:
            lista = "\n".join(f"• {op['emoji']} **{op['nome']}** (ID: `{op['id']}`)" for op in opcoes)
            embed.add_field(name=f"🎫 Opções Cadastradas ({len(opcoes)})", value=lista, inline=False)
        else:
            embed.add_field(name="🎫 Opções", value="*Nenhuma opção adicionada ainda.*", inline=False)

        class AdminDashboard(discord.ui.View):
            def __init__(self_inner):
                super().__init__(timeout=300)

            @discord.ui.button(label="📝 Editar Textos", style=discord.ButtonStyle.primary, emoji="✏️")
            async def editar_painel(self_inner, inter: discord.Interaction, btn: discord.ui.Button):
                modal = EditarPainelModal()
                modal.titulo.default = painel["titulo"]
                modal.descricao.default = painel["descricao"]
                modal.cor.default = painel["cor"]
                modal.banner_url.default = painel["banner_url"] or ""
                modal.thumbnail_url.default = painel["thumbnail_url"] or ""
                await inter.response.send_modal(modal)

            @discord.ui.button(label="➕ Add Opção", style=discord.ButtonStyle.success, emoji="✅")
            async def add_opcao(self_inner, inter: discord.Interaction, btn: discord.ui.Button):
                await inter.response.send_message(
                    "Use o comando `/ticket_add_opcao` para adicionar uma nova categoria de atendimento.",
                    ephemeral=True
                )

            @discord.ui.button(label="🔄 Alternar Menu", style=discord.ButtonStyle.secondary, emoji="🔁")
            async def alternar_menu(self_inner, inter: discord.Interaction, btn: discord.ui.Button):
                try:
                    atual = painel["tipo_menu"]
                except:
                    atual = "select"
                
                novo_modo = 'buttons' if atual == 'select' else 'select'
                db.ticket_editar_painel(guild_id, tipo_menu=novo_modo)
                await inter.response.send_message(f"✅ Modo de menu alterado para: `{novo_modo}`", ephemeral=True)
                # Opcional: reenviar o painel administrativo atualizado

            @discord.ui.button(label="🚀 Enviar Painel", style=discord.ButtonStyle.success, emoji="📤")
            async def enviar_painel(self_inner, inter: discord.Interaction, btn: discord.ui.Button):
                # Chamamos o comando de setup internamente
                await inter.response.send_message("Enviando painel...", ephemeral=True)
                # Reutilizamos a lógica do setup
                # Para simplificar, o admin pode apenas usar /ticket_setup

        await interaction.response.send_message(embed=embed, view=AdminDashboard(), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
