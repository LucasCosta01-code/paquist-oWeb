"""
commands/reunioes.py - Comandos de reuniões e presenças
/marcar_reuniao, /confirmar_presenca, /justificar_ausencia, /aprovar_ausencia, /recusar_ausencia
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

import database as db
import checks
import utils
from config import COR_PRINCIPAL, COR_SUCESSO, COR_ERRO, COR_AVISO


# Opções de status de presença
STATUS_PRESENCA = [
    app_commands.Choice(name="✅ Presente",    value="presente"),
    app_commands.Choice(name="❌ Falta",        value="falta"),
    app_commands.Choice(name="📋 Justificado", value="justificado"),
]


class Reunioes(commands.Cog):
    """Cog responsável por reuniões, presenças e ausências."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── /marcar_reuniao ───────────────────────────────────────────────────────
    @app_commands.command(name="marcar_reuniao", description="Marca uma nova reunião da facção.")
    @app_commands.describe(
        titulo="Título da reunião",
        data="Data da reunião (ex: 27/04/2025)",
        horario="Horário da reunião (ex: 20:00)",
        descricao="Descrição ou pauta da reunião"
    )
    async def marcar_reuniao(
        self,
        interaction: discord.Interaction,
        titulo: str,
        data: str,
        horario: str,
        descricao: str
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        reuniao_id = db.marcar_reuniao(titulo, data, horario, descricao, str(interaction.user.id))

        embed = discord.Embed(
            title="📅 Reunião Marcada",
            description=f"Uma nova reunião foi agendada para a facção!",
            color=COR_PRINCIPAL
        )
        embed.add_field(name="📌 ID", value=f"`#{reuniao_id}`", inline=True)
        embed.add_field(name="📋 Título", value=titulo, inline=True)
        embed.add_field(name="📅 Data", value=data, inline=True)
        embed.add_field(name="⏰ Horário", value=horario, inline=True)
        embed.add_field(name="📝 Pauta", value=descricao, inline=False)
        embed.add_field(name="👮 Criada por", value=interaction.user.mention, inline=True)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed)
        await utils.enviar_log(
            self.bot,
            "Reunião Marcada",
            f"**{interaction.user.display_name}** marcou a reunião **'{titulo}'** para {data} às {horario}.\nID: `#{reuniao_id}`"
        )

    # ─── /confirmar_presenca ───────────────────────────────────────────────────
    @app_commands.command(name="confirmar_presenca", description="Registra a presença de um membro em uma reunião.")
    @app_commands.describe(
        reuniao_id="ID da reunião (número)",
        membro="Mencione o membro",
        status="Status de presença",
        justificativa="Justificativa (obrigatório se justificado)"
    )
    @app_commands.choices(status=STATUS_PRESENCA)
    async def confirmar_presenca(
        self,
        interaction: discord.Interaction,
        reuniao_id: int,
        membro: discord.Member,
        status: app_commands.Choice[str],
        justificativa: str = ""
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        reuniao = db.get_reuniao(reuniao_id)
        if not reuniao:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Reunião Não Encontrada", f"Nenhuma reunião com ID `#{reuniao_id}` encontrada."),
                ephemeral=True
            )

        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado."), ephemeral=True
            )

        db.confirmar_presenca(reuniao_id, str(membro.id), status.value, justificativa)

        icones = {"presente": "✅", "falta": "❌", "justificado": "📋"}
        icone = icones.get(status.value, "❓")

        embed = utils.embed_sucesso("Presença Registrada")
        embed.add_field(name="📌 Reunião", value=f"**{reuniao['titulo']}** (ID `#{reuniao_id}`)", inline=False)
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name=f"{icone} Status", value=status.name, inline=True)
        if justificativa:
            embed.add_field(name="📝 Justificativa", value=justificativa, inline=False)
        embed.set_thumbnail(url=membro.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    # ─── /justificar_ausencia ──────────────────────────────────────────────────
    @app_commands.command(name="justificar_ausencia", description="Solicita justificativa de ausência à liderança.")
    @app_commands.describe(
        data="Data da ausência (ex: 27/04/2025)",
        motivo="Motivo da ausência"
    )
    async def justificar_ausencia(
        self,
        interaction: discord.Interaction,
        data: str,
        motivo: str
    ):
        # Qualquer membro registrado pode usar este comando
        dados = db.get_membro(str(interaction.user.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Não Registrado",
                    "Você não está registrado no sistema da facção. Peça para a liderança te registrar."
                ),
                ephemeral=True
            )

        ausencia_id = db.registrar_ausencia(str(interaction.user.id), motivo, data)

        embed = discord.Embed(
            title="📋 Ausência Solicitada",
            description="Sua ausência foi registrada e está **aguardando aprovação** da liderança.",
            color=COR_AVISO
        )
        embed.add_field(name="📌 ID", value=f"`#{ausencia_id}`", inline=True)
        embed.add_field(name="📅 Data", value=data, inline=True)
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await utils.enviar_log(
            self.bot,
            "Ausência Solicitada",
            f"**{interaction.user.display_name}** solicitou ausência para `{data}`.\nMotivo: `{motivo}` | ID: `#{ausencia_id}`",
            cor=COR_AVISO
        )

    # ─── /aprovar_ausencia ─────────────────────────────────────────────────────
    @app_commands.command(name="aprovar_ausencia", description="Aprova a solicitação de ausência de um membro.")
    @app_commands.describe(
        ausencia_id="ID da ausência",
        membro="Mencione o membro (para confirmação)"
    )
    async def aprovar_ausencia(
        self,
        interaction: discord.Interaction,
        ausencia_id: int,
        membro: discord.Member
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        ausencia = db.get_ausencia(ausencia_id)
        if not ausencia or ausencia["discord_id"] != str(membro.id):
            return await interaction.response.send_message(
                embed=utils.embed_erro("Ausência Não Encontrada", f"Ausência `#{ausencia_id}` não encontrada para {membro.mention}."),
                ephemeral=True
            )

        if ausencia["status"] != "pendente":
            return await interaction.response.send_message(
                embed=utils.embed_erro("Já Processada", f"Esta ausência já foi **{ausencia['status']}**."),
                ephemeral=True
            )

        db.aprovar_ausencia(ausencia_id, str(interaction.user.id))

        embed = utils.embed_sucesso("Ausência Aprovada")
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name="📌 ID da Ausência", value=f"`#{ausencia_id}`", inline=True)
        embed.add_field(name="📅 Data", value=ausencia["data"], inline=True)
        embed.add_field(name="📝 Motivo", value=ausencia["motivo"], inline=False)
        embed.add_field(name="👮 Aprovado por", value=interaction.user.mention, inline=True)

        await interaction.response.send_message(embed=embed)
        await utils.enviar_log(
            self.bot,
            "Ausência Aprovada",
            f"Ausência `#{ausencia_id}` de **{membro.display_name}** aprovada por **{interaction.user.display_name}**.",
            cor=COR_SUCESSO
        )

    # ─── /recusar_ausencia ─────────────────────────────────────────────────────
    @app_commands.command(name="recusar_ausencia", description="Recusa a solicitação de ausência de um membro.")
    @app_commands.describe(
        ausencia_id="ID da ausência",
        membro="Mencione o membro",
        motivo="Motivo da recusa"
    )
    async def recusar_ausencia(
        self,
        interaction: discord.Interaction,
        ausencia_id: int,
        membro: discord.Member,
        motivo: str
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        ausencia = db.get_ausencia(ausencia_id)
        if not ausencia or ausencia["discord_id"] != str(membro.id):
            return await interaction.response.send_message(
                embed=utils.embed_erro("Ausência Não Encontrada", f"Ausência `#{ausencia_id}` não encontrada para {membro.mention}."),
                ephemeral=True
            )

        if ausencia["status"] != "pendente":
            return await interaction.response.send_message(
                embed=utils.embed_erro("Já Processada", f"Esta ausência já foi **{ausencia['status']}**."),
                ephemeral=True
            )

        db.recusar_ausencia(ausencia_id, str(interaction.user.id))

        embed = discord.Embed(
            title="❌ Ausência Recusada",
            description=f"A ausência de {membro.mention} foi **recusada**.",
            color=COR_ERRO
        )
        embed.add_field(name="📌 ID", value=f"`#{ausencia_id}`", inline=True)
        embed.add_field(name="📅 Data", value=ausencia["data"], inline=True)
        embed.add_field(name="📝 Motivo da Recusa", value=motivo, inline=False)
        embed.add_field(name="👮 Recusado por", value=interaction.user.mention, inline=True)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed)
        await utils.enviar_log(
            self.bot,
            "Ausência Recusada",
            f"Ausência `#{ausencia_id}` de **{membro.display_name}** recusada por **{interaction.user.display_name}**.\nMotivo: `{motivo}`",
            cor=COR_ERRO
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reunioes(bot))
