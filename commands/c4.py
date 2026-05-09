"""
commands/c4.py - Comandos de entrega de C4
/entregar_c4, /ranking_c4
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

import database as db
import checks
import utils
from config import COR_PRINCIPAL, COR_ERRO, COR_SUCESSO


class C4(commands.Cog):
    """Cog responsável por gerenciar entregas de C4."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── /entregar_c4 ──────────────────────────────────────────────────────────
    @app_commands.command(name="entregar_c4", description="Registra entrega de C4 de um membro.")
    @app_commands.describe(
        membro="Mencione o membro",
        quantidade="Quantidade de C4 entregue"
    )
    async def entregar_c4(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        quantidade: int
    ):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        if quantidade <= 0:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Valor Inválido", "A quantidade deve ser maior que zero."), ephemeral=True
            )

        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado."), ephemeral=True
            )

        db.entregar_c4(str(membro.id), quantidade, str(interaction.user.id), utils.data_agora())
        dados_atualizados = db.get_membro(str(membro.id))

        embed = utils.embed_sucesso("Entrega de C4 Registrada")
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name="💣 Quantidade", value=f"`{quantidade:,}`", inline=True)
        embed.add_field(name="💣 Total do Membro", value=f"`{dados_atualizados['c4_total']:,}`", inline=True)
        embed.add_field(name="👮 Registrado por", value=interaction.user.mention, inline=True)
        embed.add_field(name="📅 Data", value=utils.data_agora(), inline=True)
        embed.set_thumbnail(url=membro.display_avatar.url)

        await interaction.response.send_message(embed=embed)
        await utils.enviar_log(
            self.bot,
            "C4 Entregue",
            f"**{membro.display_name}** entregou `{quantidade}` C4. Total: `{dados_atualizados['c4_total']}`.\n"
            f"Registrado por: **{interaction.user.display_name}**"
        )

    # ─── /ranking_c4 ───────────────────────────────────────────────────────────
    @app_commands.command(name="ranking_c4", description="Exibe o ranking de entregas de C4.")
    async def ranking_c4(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        ranking = db.get_ranking_c4(10)

        embed = discord.Embed(
            title="💣 Ranking de Entregas de C4",
            description="Os **10 maiores entregadores** de C4:",
            color=COR_PRINCIPAL
        )

        if not ranking:
            embed.description = "Nenhuma entrega de C4 registrada ainda."
        else:
            medalhas = ["🥇", "🥈", "🥉"]
            linhas = []
            for i, row in enumerate(ranking):
                icone = medalhas[i] if i < 3 else f"`{i+1}.`"
                membro_obj = interaction.guild.get_member(int(row["discord_id"]))
                nome = membro_obj.display_name if membro_obj else row["nome"]
                linhas.append(f"{icone} **{nome}** — `{row['c4_total']:,}` C4")
            embed.description = "\n".join(linhas)

        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(C4(bot))
