"""
commands/punicoes.py - Sistema completo de punições da facção
─────────────────────────────────────────────────────────────
Comandos disponíveis:
  /advertir   → Registra uma advertência (banco de dados)
  /punir      → Registra uma punição (banco de dados)
  /silenciar  → Aplica timeout no Discord (mute temporário)
  /dessilenciar → Remove timeout
  /expulsar   → Kick do servidor
  /banir      → Ban do servidor
  /desbanir   → Reverte o ban

Todos os comandos:
  ✓ Verificam permissão (liderança)
  ✓ Enviam DM ao punido (quando possível)
  ✓ Postam embed público no canal
  ✓ Registram no canal de logs do bot
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone

import database as db
import checks
import utils
from config import COR_ERRO, COR_AVISO, COR_SUCESSO


# ─── CHOICES DE TIPO DE PUNIÇÃO (banco) ───────────────────────────────────────
TIPOS_PUNICAO = [
    app_commands.Choice(name="Suspensão",     value="suspensao"),
    app_commands.Choice(name="Rebaixamento",  value="rebaixamento"),
    app_commands.Choice(name="Expulsão",      value="expulsao"),
    app_commands.Choice(name="Multa de Farm", value="multa_farm"),
    app_commands.Choice(name="Outro",         value="outro"),
]

# ─── DURAÇÕES DE TIMEOUT ───────────────────────────────────────────────────────
DURACOES_TIMEOUT = [
    app_commands.Choice(name="60 segundos",  value=60),
    app_commands.Choice(name="5 minutos",    value=300),
    app_commands.Choice(name="10 minutos",   value=600),
    app_commands.Choice(name="30 minutos",   value=1800),
    app_commands.Choice(name="1 hora",       value=3600),
    app_commands.Choice(name="6 horas",      value=21600),
    app_commands.Choice(name="12 horas",     value=43200),
    app_commands.Choice(name="1 dia",        value=86400),
    app_commands.Choice(name="3 dias",       value=259200),
    app_commands.Choice(name="7 dias",       value=604800),
]

# ─── ESCOLHA DE DIAS DE MENSAGENS PARA BAN ────────────────────────────────────
DIAS_MENSAGENS_BAN = [
    app_commands.Choice(name="Não apagar",   value=0),
    app_commands.Choice(name="1 dia",        value=1),
    app_commands.Choice(name="3 dias",       value=3),
    app_commands.Choice(name="7 dias",       value=7),
]


def _embed_punicao(
    titulo: str,
    cor: int,
    membro: discord.Member,
    motivo: str,
    executor: discord.Member,
    extra_fields: list[tuple] = None,
) -> discord.Embed:
    """Monta um embed de punição padronizado e visual."""
    embed = discord.Embed(
        title=titulo,
        color=cor,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=membro.display_avatar.url)
    embed.add_field(name="👤 Membro",      value=f"{membro.mention}\n`{membro.id}`", inline=True)
    embed.add_field(name="👮 Executado por", value=executor.mention,                  inline=True)
    embed.add_field(name="📅 Data & Hora",  value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
    if extra_fields:
        for name, value, inline in extra_fields:
            embed.add_field(name=name, value=value, inline=inline)
    embed.add_field(name="📝 Motivo", value=f"```{motivo}```", inline=False)
    embed.set_footer(text="⚔️ Facção Bot • Sistema de Punições")
    return embed


async def _dm_punicao(membro: discord.Member, guild_name: str, titulo: str, descricao: str, cor: int):
    """Tenta enviar DM ao punido. Ignora se DM estiver fechada."""
    try:
        embed = discord.Embed(
            title=f"⚠️ {titulo}",
            description=descricao,
            color=cor,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Servidor: {guild_name}")
        await membro.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass  # DM fechada — não interrompe o fluxo


class Punicoes(commands.Cog):
    """Cog responsável pelo sistema completo de punições."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ══════════════════════════════════════════════════════════════════════════════
    #   /advertir — Registra advertência no banco
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="advertir", description="⚠️ Aplica uma advertência a um membro. [Liderança]")
    @app_commands.describe(membro="Mencione o membro", motivo="Motivo da advertência")
    async def advertir(self, interaction: discord.Interaction, membro: discord.Member, motivo: str):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado."),
                ephemeral=True,
            )

        db.aplicar_advertencia(str(membro.id), motivo, str(interaction.user.id), utils.data_agora())
        dados_att = db.get_membro(str(membro.id))

        embed = _embed_punicao(
            "⚠️  Advertência Aplicada", COR_AVISO, membro, motivo, interaction.user,
            extra_fields=[
                ("⚠️ Total de Advertências", f"`{dados_att['advertencias']}`", True),
            ]
        )
        await interaction.response.send_message(embed=embed)

        await _dm_punicao(
            membro, interaction.guild.name,
            "Você recebeu uma Advertência",
            f"Você foi advertido no servidor **{interaction.guild.name}**.\n\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.display_name}\n\n"
            f"Total de advertências: `{dados_att['advertencias']}`",
            COR_AVISO,
        )

        await utils.enviar_log(
            self.bot, "⚠️ Advertência Aplicada",
            f"**Membro:** {membro.mention} (`{membro.id}`)\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.mention}\n"
            f"**Total adv.:** `{dados_att['advertencias']}`",
            cor=COR_AVISO,
        )

    # ══════════════════════════════════════════════════════════════════════════════
    #   /radvertir — Remove última advertência
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="radvertir", description="✅ Remove a última advertência de um membro. [Liderança]")
    @app_commands.describe(membro="Mencione o membro")
    async def radvertir(self, interaction: discord.Interaction, membro: discord.Member):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado."),
                ephemeral=True,
            )

        removeu = db.remover_ultima_advertencia(str(membro.id))
        if not removeu:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Sem Advertências", f"{membro.mention} não possui advertências."),
                ephemeral=True,
            )

        dados_att = db.get_membro(str(membro.id))
        embed = discord.Embed(
            title="✅  Advertência Removida",
            color=COR_SUCESSO,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="👤 Membro", value=f"{membro.mention}\n`{membro.id}`", inline=True)
        embed.add_field(name="👮 Removido por", value=interaction.user.mention, inline=True)
        embed.add_field(name="⚠️ Advertências restantes", value=f"`{dados_att['advertencias']}`", inline=True)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Punições")
        await interaction.response.send_message(embed=embed)

        await utils.enviar_log(
            self.bot, "✅ Advertência Removida",
            f"**Membro:** {membro.mention} (`{membro.id}`)\n"
            f"**Por:** {interaction.user.mention}\n"
            f"**Restantes:** `{dados_att['advertencias']}`",
            cor=COR_SUCESSO,
        )

    # ══════════════════════════════════════════════════════════════════════════════
    #   /punir — Registra punição no banco
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="punir", description="🔨 Registra uma punição para um membro da facção. [Liderança]")
    @app_commands.describe(membro="Mencione o membro", tipo="Tipo de punição", motivo="Motivo da punição")
    @app_commands.choices(tipo=TIPOS_PUNICAO)
    async def punir(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        tipo: app_commands.Choice[str],
        motivo: str,
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado."),
                ephemeral=True,
            )

        db.aplicar_punicao(str(membro.id), motivo, tipo.value, str(interaction.user.id), utils.data_agora())
        dados_att = db.get_membro(str(membro.id))

        embed = _embed_punicao(
            "🔨  Punição Registrada", COR_ERRO, membro, motivo, interaction.user,
            extra_fields=[
                ("🔖 Tipo",             tipo.name,                           True),
                ("🔨 Total de Punições", f"`{dados_att['punicoes']}`",        True),
            ]
        )
        await interaction.response.send_message(embed=embed)

        await _dm_punicao(
            membro, interaction.guild.name,
            "Você recebeu uma Punição",
            f"Você foi punido no servidor **{interaction.guild.name}**.\n\n"
            f"**Tipo:** {tipo.name}\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.display_name}",
            COR_ERRO,
        )

        await utils.enviar_log(
            self.bot, "🔨 Punição Registrada",
            f"**Membro:** {membro.mention} (`{membro.id}`)\n"
            f"**Tipo:** {tipo.name}\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.mention}\n"
            f"**Total pun.:** `{dados_att['punicoes']}`",
            cor=COR_ERRO,
        )

    # ══════════════════════════════════════════════════════════════════════════════
    #   /silenciar — Timeout no Discord
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="silenciar", description="🔇 Silencia um membro por um tempo determinado. [Liderança]")
    @app_commands.describe(
        membro="Mencione o membro a ser silenciado",
        duracao="Duração do silêncio",
        motivo="Motivo do silêncio",
    )
    @app_commands.choices(duracao=DURACOES_TIMEOUT)
    async def silenciar(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        duracao: app_commands.Choice[int],
        motivo: str,
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # Não pode silenciar a si mesmo nem outros admins
        if membro == interaction.user:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Operação Inválida", "Você não pode silenciar a si mesmo."),
                ephemeral=True,
            )
        if membro.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Operação Negada", f"{membro.mention} é um administrador e não pode ser silenciado."),
                ephemeral=True,
            )

        until = datetime.now(timezone.utc) + timedelta(seconds=duracao.value)

        try:
            await membro.timeout(until, reason=f"[Bot] {interaction.user} | {motivo}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Sem Permissão",
                    "O bot não tem permissão para silenciar este membro.\n"
                    "Verifique se o cargo do bot está acima do cargo do membro.",
                ),
                ephemeral=True,
            )

        ts_fim = int(until.timestamp())
        embed = _embed_punicao(
            "🔇  Membro Silenciado", 0xFFA500, membro, motivo, interaction.user,
            extra_fields=[
                ("⏱️ Duração",     duracao.name,         True),
                ("🕐 Expira em",   f"<t:{ts_fim}:R>",    True),
                ("📅 Até",         f"<t:{ts_fim}:F>",    True),
            ]
        )
        await interaction.response.send_message(embed=embed)

        await _dm_punicao(
            membro, interaction.guild.name,
            "Você foi Silenciado",
            f"Você foi silenciado no servidor **{interaction.guild.name}**.\n\n"
            f"**Duração:** {duracao.name}\n"
            f"**Expira em:** <t:{ts_fim}:R>\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.display_name}",
            0xFFA500,
        )

        await utils.enviar_log(
            self.bot, "🔇 Membro Silenciado",
            f"**Membro:** {membro.mention} (`{membro.id}`)\n"
            f"**Duração:** {duracao.name}\n"
            f"**Expira:** <t:{ts_fim}:R>\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.mention}",
            cor=0xFFA500,
        )

    # ══════════════════════════════════════════════════════════════════════════════
    #   /dessilenciar — Remove timeout
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="dessilenciar", description="🔊 Remove o silêncio de um membro. [Liderança]")
    @app_commands.describe(
        membro="Mencione o membro",
        motivo="Motivo da remoção do silêncio (opcional)",
    )
    async def dessilenciar(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: str = "Sem motivo especificado.",
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        if not membro.is_timed_out():
            return await interaction.response.send_message(
                embed=utils.embed_erro("Membro Não Silenciado", f"{membro.mention} não está silenciado no momento."),
                ephemeral=True,
            )

        try:
            await membro.timeout(None, reason=f"[Bot] Removido por {interaction.user} | {motivo}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Sem Permissão", "O bot não tem permissão para remover o silêncio deste membro."),
                ephemeral=True,
            )

        embed = _embed_punicao(
            "🔊  Silêncio Removido", COR_SUCESSO, membro, motivo, interaction.user,
        )
        await interaction.response.send_message(embed=embed)

        await _dm_punicao(
            membro, interaction.guild.name,
            "Seu Silêncio foi Removido",
            f"Seu silêncio no servidor **{interaction.guild.name}** foi removido.\n\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.display_name}",
            COR_SUCESSO,
        )

        await utils.enviar_log(
            self.bot, "🔊 Silêncio Removido",
            f"**Membro:** {membro.mention} (`{membro.id}`)\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.mention}",
            cor=COR_SUCESSO,
        )

    # ══════════════════════════════════════════════════════════════════════════════
    #   /expulsar — Kick do servidor
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="expulsar", description="👢 Expulsa um membro do servidor. [Liderança]")
    @app_commands.describe(
        membro="Mencione o membro a ser expulso",
        motivo="Motivo da expulsão",
    )
    async def expulsar(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: str,
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        if membro == interaction.user:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Operação Inválida", "Você não pode se expulsar."),
                ephemeral=True,
            )
        if membro.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Operação Negada", f"{membro.mention} é administrador e não pode ser expulso."),
                ephemeral=True,
            )

        # Avisa antes de expulsar (DM primeiro, porque depois ele sai)
        await _dm_punicao(
            membro, interaction.guild.name,
            "Você foi Expulso do Servidor",
            f"Você foi expulso do servidor **{interaction.guild.name}**.\n\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.display_name}\n\n"
            f"Entre em contato com a liderança caso ache injusto.",
            COR_ERRO,
        )

        try:
            await membro.kick(reason=f"[Bot] {interaction.user} | {motivo}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Sem Permissão",
                    "O bot não tem permissão para expulsar este membro.\n"
                    "Verifique se o cargo do bot está acima do cargo do membro.",
                ),
                ephemeral=True,
            )

        embed = discord.Embed(
            title="👢  Membro Expulso",
            description=f"**{membro.display_name}** foi expulso do servidor.",
            color=COR_ERRO,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="👤 Membro",        value=f"{membro.mention}\n`{membro.id}`", inline=True)
        embed.add_field(name="👮 Executado por", value=interaction.user.mention,            inline=True)
        embed.add_field(name="📅 Data & Hora",   value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
        embed.add_field(name="📝 Motivo",        value=f"```{motivo}```",                  inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Punições")

        await interaction.response.send_message(embed=embed)

        await utils.enviar_log(
            self.bot, "👢 Membro Expulso",
            f"**Membro:** {membro.display_name} (`{membro.id}`)\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.mention}",
            cor=COR_ERRO,
        )

    # ══════════════════════════════════════════════════════════════════════════════
    #   /banir — Ban do servidor
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="banir", description="🔨 Bane um membro do servidor permanentemente. [Liderança]")
    @app_commands.describe(
        membro="Mencione o membro a ser banido",
        motivo="Motivo do ban",
        apagar_mensagens="Quantos dias de mensagens apagar (padrão: Não apagar)",
    )
    @app_commands.choices(apagar_mensagens=DIAS_MENSAGENS_BAN)
    async def banir(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: str,
        apagar_mensagens: app_commands.Choice[int] = None,
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        if membro == interaction.user:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Operação Inválida", "Você não pode se banir."),
                ephemeral=True,
            )
        if membro.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Operação Negada", f"{membro.mention} é administrador e não pode ser banido."),
                ephemeral=True,
            )

        dias = apagar_mensagens.value if apagar_mensagens else 0
        dias_label = apagar_mensagens.name if apagar_mensagens else "Não apagar"

        # DM antes do ban
        await _dm_punicao(
            membro, interaction.guild.name,
            "Você foi Banido do Servidor",
            f"Você foi **banido permanentemente** do servidor **{interaction.guild.name}**.\n\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.display_name}\n\n"
            f"Este ban é permanente. Entre em contato com a liderança pelo Discord se achar injusto.",
            COR_ERRO,
        )

        try:
            await membro.ban(
                reason=f"[Bot] {interaction.user} | {motivo}",
                delete_message_days=dias,
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Sem Permissão",
                    "O bot não tem permissão para banir este membro.\n"
                    "Verifique se o cargo do bot está acima do cargo do membro.",
                ),
                ephemeral=True,
            )

        embed = discord.Embed(
            title="🔨  Membro Banido",
            description=f"**{membro.display_name}** foi banido permanentemente do servidor.",
            color=0xFF0000,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="👤 Membro",            value=f"{membro.mention}\n`{membro.id}`", inline=True)
        embed.add_field(name="👮 Executado por",     value=interaction.user.mention,            inline=True)
        embed.add_field(name="📅 Data & Hora",       value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
        embed.add_field(name="🗑️ Mensagens apagadas", value=dias_label,                        inline=True)
        embed.add_field(name="📝 Motivo",            value=f"```{motivo}```",                  inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Punições")

        await interaction.response.send_message(embed=embed)

        await utils.enviar_log(
            self.bot, "🔨 Membro BANIDO",
            f"**Membro:** {membro.display_name} (`{membro.id}`)\n"
            f"**Motivo:** {motivo}\n"
            f"**Mensagens apagadas:** {dias_label}\n"
            f"**Por:** {interaction.user.mention}",
            cor=0xFF0000,
        )

    # ══════════════════════════════════════════════════════════════════════════════
    #   /desbanir — Reverte ban
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="desbanir", description="✅ Remove o ban de um usuário. [Liderança]")
    @app_commands.describe(
        user_id="ID do usuário banido (número)",
        motivo="Motivo da remoção do ban (opcional)",
    )
    async def desbanir(
        self,
        interaction: discord.Interaction,
        user_id: str,
        motivo: str = "Sem motivo especificado.",
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # Converte o ID
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message(
                embed=utils.embed_erro("ID Inválido", f"`{user_id}` não é um ID de usuário válido."),
                ephemeral=True,
            )

        # Busca na lista de banidos
        try:
            ban_entry = await interaction.guild.fetch_ban(discord.Object(id=uid))
        except discord.NotFound:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Usuário Não Banido", f"Nenhum ban encontrado para o ID `{uid}`."),
                ephemeral=True,
            )

        await interaction.guild.unban(ban_entry.user, reason=f"[Bot] {interaction.user} | {motivo}")

        embed = discord.Embed(
            title="✅  Ban Removido",
            description=f"**{ban_entry.user.display_name}** foi desbanido do servidor.",
            color=COR_SUCESSO,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=ban_entry.user.display_avatar.url)
        embed.add_field(name="👤 Usuário",       value=f"{ban_entry.user.mention}\n`{ban_entry.user.id}`", inline=True)
        embed.add_field(name="👮 Executado por", value=interaction.user.mention,                            inline=True)
        embed.add_field(name="📝 Motivo",        value=f"```{motivo}```",                                   inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Punições")

        await interaction.response.send_message(embed=embed)

        await utils.enviar_log(
            self.bot, "✅ Ban Removido",
            f"**Usuário:** {ban_entry.user.display_name} (`{ban_entry.user.id}`)\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.mention}",
            cor=COR_SUCESSO,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Punicoes(bot))
