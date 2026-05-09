"""
commands/membros.py - Comandos de gerenciamento de membros
/registrar_membro, /remover_membro, /perfil_membro
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

import database as db
import checks
import utils
from config import COR_PRINCIPAL, COR_ERRO, COR_INFO


class Membros(commands.Cog):
    """Cog responsável por gerenciar membros da facção."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── /registrar_membro ─────────────────────────────────────────────────────
    @app_commands.command(name="registrar_membro", description="Registra um novo membro na facção.")
    @app_commands.describe(
        membro="Mencione o membro do Discord",
        id_jogo="ID do membro no jogo",
        cargo="Cargo do membro na facção"
    )
    async def registrar_membro(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        id_jogo: str,
        cargo: str
    ):
        # Verifica permissão: apenas liderança
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        data = utils.data_agora()
        sucesso = db.registrar_membro(
            discord_id=str(membro.id),
            nome=membro.display_name,
            id_jogo=id_jogo,
            cargo=cargo,
            data_entrada=data
        )

        if not sucesso:
            embed = utils.embed_erro(
                "Membro Já Registrado",
                f"{membro.mention} já está registrado no sistema da facção."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = utils.embed_sucesso(
            "Membro Registrado",
            f"O membro {membro.mention} foi adicionado com sucesso à facção!"
        )
        embed.add_field(name="👤 Nome", value=membro.display_name, inline=True)
        embed.add_field(name="🎮 ID no Jogo", value=id_jogo, inline=True)
        embed.add_field(name="🏅 Cargo", value=cargo, inline=True)
        embed.add_field(name="📅 Entrada", value=data, inline=True)
        embed.set_thumbnail(url=membro.display_avatar.url)

        await interaction.response.send_message(embed=embed)
        await utils.enviar_log(
            self.bot,
            "Membro Registrado",
            f"**{membro.display_name}** foi registrado por **{interaction.user.display_name}**.\n"
            f"Cargo: `{cargo}` | ID Jogo: `{id_jogo}`"
        )

    # ─── /remover_membro ───────────────────────────────────────────────────────
    @app_commands.command(name="remover_membro", description="Remove um membro da facção.")
    @app_commands.describe(
        membro="Mencione o membro do Discord",
        motivo="Motivo da remoção"
    )
    async def remover_membro(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: str
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        dados = db.get_membro(str(membro.id))
        if not dados or dados["status"] == "removido":
            embed = utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado no sistema.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        db.remover_membro(str(membro.id))

        embed = discord.Embed(
            title="🚪 Membro Removido",
            description=f"**{membro.display_name}** foi removido da facção.",
            color=COR_ERRO
        )
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.add_field(name="👮 Removido por", value=interaction.user.mention, inline=True)
        embed.add_field(name="📅 Data", value=utils.data_agora(), inline=True)
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")

        await interaction.response.send_message(embed=embed)
        await utils.enviar_log(
            self.bot,
            "Membro Removido",
            f"**{membro.display_name}** foi removido por **{interaction.user.display_name}**.\n"
            f"Motivo: `{motivo}`",
            cor=COR_ERRO
        )

    # ─── /perfil_membro ────────────────────────────────────────────────────────
    @app_commands.command(name="perfil_membro", description="Exibe o perfil completo de um membro.")
    @app_commands.describe(membro="Mencione o membro do Discord")
    async def perfil_membro(
        self,
        interaction: discord.Interaction,
        membro: discord.Member
    ):
        # Liderança e Gerente de Farm podem ver
        if not checks.is_farm_ou_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        dados = db.get_membro(str(membro.id))
        if not dados:
            embed = utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado no sistema.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Ícone de status
        icone_status = "🟢" if dados["status"] == "ativo" else "🔴"

        embed = discord.Embed(
            title=f"📋 Perfil │ {membro.display_name}",
            color=COR_PRINCIPAL
        )
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="🎮 ID no Jogo", value=dados["id_jogo"] or "—", inline=True)
        embed.add_field(name="🏅 Cargo", value=dados["cargo"] or "—", inline=True)
        embed.add_field(name=f"{icone_status} Status", value=dados["status"].capitalize(), inline=True)
        embed.add_field(name="📅 Entrada", value=dados["data_entrada"] or "—", inline=True)
        embed.add_field(name="🌾 Farm Total", value=f"`{dados['farm_total']:,}`", inline=True)
        embed.add_field(name="📅 Farm Semanal", value=f"`{dados['farm_semanal']:,}`", inline=True)
        embed.add_field(name="💣 C4 Entregue", value=f"`{dados['c4_total']:,}`", inline=True)
        embed.add_field(name="⚠️ Advertências", value=f"`{dados['advertencias']}`", inline=True)
        embed.add_field(name="🔨 Punições", value=f"`{dados['punicoes']}`", inline=True)
        embed.add_field(name="✅ Presenças", value=f"`{dados['presencas']}`", inline=True)
        embed.add_field(name="❌ Faltas", value=f"`{dados['faltas']}`", inline=True)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Notifica quando um membro da facção sai do servidor e o remove do banco."""
        dados = db.get_membro(str(member.id))
        if dados:
            db.remover_membro(str(member.id))
            from config import CANAL_AVISOS_ID
            canal = self.bot.get_channel(CANAL_AVISOS_ID)
            if canal:
                embed = discord.Embed(
                    title="🚪 Membro Saiu do Servidor",
                    description=f"O membro **{member.display_name}** ({member.mention}) saiu do grupo!\nEle foi removido automaticamente do banco de dados da facção.",
                    color=COR_ERRO
                )
                embed.add_field(name="Apelido/Nome", value=member.display_name, inline=True)
                if dados["id_jogo"]:
                    embed.add_field(name="ID no Jogo", value=dados["id_jogo"], inline=True)
                embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
                embed.set_footer(text="⚔️ Facção Bot • Notificação Automática")
                await canal.send(embed=embed)


async def setup(bot: commands.Bot):
    """Registra o Cog no bot."""
    await bot.add_cog(Membros(bot))
