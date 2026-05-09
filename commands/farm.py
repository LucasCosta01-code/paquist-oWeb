"""
commands/farm.py - Comandos de gerenciamento de farm
/adicionar_farm, /remover_farm, /ranking_farm, /ver_meta, /relatorio_farm, /punir_meta
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

import database as db
import checks
import utils
from config import COR_PRINCIPAL, COR_ERRO, COR_SUCESSO, COR_AVISO, META_FARM_SEMANAL


class Farm(commands.Cog):
    """Cog responsável por gerenciar farm da facção."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── /adicionar_farm ───────────────────────────────────────────────────────
    @app_commands.command(name="adicionar_farm", description="Adiciona farm a um membro da facção.")
    @app_commands.describe(
        membro="Mencione o membro",
        quantidade="Quantidade de farm",
        tipo="Tipo do farm (ex: drogas, roubo, etc.)"
    )
    async def adicionar_farm(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        quantidade: int,
        tipo: str
    ):
        if not checks.is_farm_ou_lideranca(interaction):
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

        db.adicionar_farm(str(membro.id), quantidade, tipo, str(interaction.user.id), utils.data_agora())
        dados_atualizados = db.get_membro(str(membro.id))

        # Verifica se bateu a meta após adição
        bateu_meta = dados_atualizados["farm_semanal"] >= META_FARM_SEMANAL
        icone_meta = "🏆 Meta Batida!" if bateu_meta else f"📊 {dados_atualizados['farm_semanal']}/{META_FARM_SEMANAL}"

        embed = utils.embed_sucesso("Farm Adicionado")
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name="🌾 Quantidade", value=f"`+{quantidade:,}`", inline=True)
        embed.add_field(name="📦 Tipo", value=tipo, inline=True)
        embed.add_field(name="📈 Farm Semanal", value=icone_meta, inline=True)
        embed.add_field(name="🌾 Farm Total", value=f"`{dados_atualizados['farm_total']:,}`", inline=True)
        embed.add_field(name="👮 Registrado por", value=interaction.user.mention, inline=True)
        embed.set_thumbnail(url=membro.display_avatar.url)

        await interaction.response.send_message(embed=embed)
        await utils.enviar_log(
            self.bot,
            "Farm Adicionado",
            f"**+{quantidade:,}** de farm adicionado para **{membro.display_name}** por **{interaction.user.display_name}**.\n"
            f"Tipo: `{tipo}` | Semanal: `{dados_atualizados['farm_semanal']:,}`"
        )

    # ─── /remover_farm ─────────────────────────────────────────────────────────
    @app_commands.command(name="remover_farm", description="Remove farm de um membro.")
    @app_commands.describe(
        membro="Mencione o membro",
        quantidade="Quantidade a remover",
        motivo="Motivo da remoção"
    )
    async def remover_farm(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        quantidade: int,
        motivo: str
    ):
        if not checks.is_farm_ou_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado."), ephemeral=True
            )

        db.remover_farm(str(membro.id), quantidade, str(interaction.user.id), utils.data_agora(), motivo)

        embed = discord.Embed(title="🔻 Farm Removido", color=COR_AVISO)
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name="🌾 Removido", value=f"`-{quantidade:,}`", inline=True)
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.add_field(name="👮 Removido por", value=interaction.user.mention, inline=True)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()
        embed.set_thumbnail(url=membro.display_avatar.url)

        await interaction.response.send_message(embed=embed)
        await utils.enviar_log(
            self.bot,
            "Farm Removido",
            f"**-{quantidade:,}** de farm removido de **{membro.display_name}** por **{interaction.user.display_name}**.\n"
            f"Motivo: `{motivo}`",
            cor=COR_AVISO
        )

    # ─── /ranking_farm ─────────────────────────────────────────────────────────
    @app_commands.command(name="ranking_farm", description="Exibe o ranking de farm semanal (Top 10).")
    async def ranking_farm(self, interaction: discord.Interaction):
        if not checks.is_farm_ou_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        ranking = db.get_ranking_farm(10)

        embed = discord.Embed(
            title="🏆 Ranking de Farm Semanal",
            description="Os **10 maiores farmadores** da semana:",
            color=COR_PRINCIPAL
        )

        if not ranking:
            embed.description = "Nenhum dado de farm registrado ainda."
        else:
            medalhas = ["🥇", "🥈", "🥉"]
            linhas = []
            for i, row in enumerate(ranking):
                icone = medalhas[i] if i < 3 else f"`{i+1}.`"
                membro_obj = interaction.guild.get_member(int(row["discord_id"]))
                nome = membro_obj.display_name if membro_obj else row["nome"]
                linhas.append(f"{icone} **{nome}** — `{row['farm_semanal']:,}` farm")
            embed.description = "\n".join(linhas)

        embed.add_field(name="📊 Meta Semanal", value=f"`{META_FARM_SEMANAL:,}`", inline=True)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed)

    # ─── /ver_meta ─────────────────────────────────────────────────────────────
    @app_commands.command(name="ver_meta", description="Verifica se um membro bateu a meta de farm.")
    @app_commands.describe(membro="Mencione o membro")
    async def ver_meta(self, interaction: discord.Interaction, membro: discord.Member):
        if not checks.is_farm_ou_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado."), ephemeral=True
            )

        semanal   = dados["farm_semanal"]
        bateu     = semanal >= META_FARM_SEMANAL
        porcentagem = min(100, int((semanal / META_FARM_SEMANAL) * 100))
        barras    = int(porcentagem / 10)
        barra_str = "█" * barras + "░" * (10 - barras)

        cor = COR_SUCESSO if bateu else COR_ERRO
        status_txt = "✅ **META BATIDA!**" if bateu else "❌ **META NÃO BATIDA**"

        embed = discord.Embed(
            title=f"📊 Meta de Farm │ {membro.display_name}",
            color=cor
        )
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="🌾 Farm Semanal", value=f"`{semanal:,}`", inline=True)
        embed.add_field(name="🎯 Meta", value=f"`{META_FARM_SEMANAL:,}`", inline=True)
        embed.add_field(name="📈 Progresso", value=f"`{porcentagem}%`", inline=True)
        embed.add_field(name="📉 Barra", value=f"`[{barra_str}]`", inline=False)
        embed.add_field(name="🏁 Status", value=status_txt, inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed)

    # ─── /relatorio_farm ───────────────────────────────────────────────────────
    @app_commands.command(name="relatorio_farm", description="Gera um relatório geral de farm da facção.")
    async def relatorio_farm(self, interaction: discord.Interaction):
        if not checks.is_farm_ou_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        membros       = db.get_todos_membros()
        ranking       = db.get_ranking_farm(5)
        sem_meta      = db.get_membros_sem_meta(META_FARM_SEMANAL)
        total_farmado = sum(m["farm_semanal"] for m in membros)
        bateram_meta  = [m for m in membros if m["farm_semanal"] >= META_FARM_SEMANAL]

        embed = discord.Embed(
            title="📊 Relatório de Farm Semanal",
            color=COR_PRINCIPAL
        )
        embed.add_field(name="👥 Total de Membros", value=f"`{len(membros)}`", inline=True)
        embed.add_field(name="🌾 Farm Total (semana)", value=f"`{total_farmado:,}`", inline=True)
        embed.add_field(name="🎯 Meta", value=f"`{META_FARM_SEMANAL:,}`", inline=True)
        embed.add_field(name="✅ Bateram Meta", value=f"`{len(bateram_meta)}`", inline=True)
        embed.add_field(name="❌ Sem Meta", value=f"`{len(sem_meta)}`", inline=True)

        # Top 5
        if ranking:
            top_txt = "\n".join(
                f"`{i+1}.` **{r['nome']}** — `{r['farm_semanal']:,}`"
                for i, r in enumerate(ranking)
            )
            embed.add_field(name="🏆 Top 5 Farmadores", value=top_txt, inline=False)

        # Sem meta
        if sem_meta:
            sm_txt = "\n".join(f"• **{m['nome']}** — `{m['farm_semanal']:,}`" for m in sem_meta[:8])
            embed.add_field(name="⚠️ Não Bateram a Meta", value=sm_txt, inline=False)

        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed)

    # ─── /punir_meta ───────────────────────────────────────────────────────────
    @app_commands.command(name="punir_meta", description="Aplica punição a membro que não bateu a meta de farm.")
    @app_commands.describe(membro="Mencione o membro", motivo="Motivo da punição")
    async def punir_meta(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        motivo: str
    ):
        if not checks.is_farm_ou_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Membro Não Encontrado", f"{membro.mention} não está registrado."), ephemeral=True
            )

        db.aplicar_punicao(
            str(membro.id),
            motivo,
            "Não bateu a meta de farm",
            str(interaction.user.id),
            utils.data_agora()
        )

        embed = discord.Embed(
            title="🔨 Punição por Meta de Farm",
            description=f"{membro.mention} foi punido por não atingir a meta semanal.",
            color=COR_ERRO
        )
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.add_field(name="🌾 Farm Semanal", value=f"`{dados['farm_semanal']:,} / {META_FARM_SEMANAL:,}`", inline=True)
        embed.add_field(name="👮 Aplicado por", value=interaction.user.mention, inline=True)
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
        embed.timestamp = datetime.utcnow()

        await interaction.response.send_message(embed=embed)
        await utils.enviar_log(
            self.bot,
            "Punição por Meta",
            f"**{membro.display_name}** punido por **{interaction.user.display_name}**.\nMotivo: `{motivo}`",
            cor=COR_ERRO
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Farm(bot))
