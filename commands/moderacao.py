"""
commands/moderacao.py - Comandos de moderação do servidor
/limpar      → Apaga N mensagens do canal (apenas liderança)
/add_membro  → Dá o cargo de Membro da Facção a um usuário (apenas liderança)
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

import checks
import utils
from config import CARGO_MEMBRO_ID


class Moderacao(commands.Cog):
    """Cog responsável por comandos de moderação do servidor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── /limpar ───────────────────────────────────────────────────────────────
    @app_commands.command(
        name="limpar",
        description="🧹 Apaga mensagens do canal (Sem limites). [Apenas Liderança]"
    )
    @app_commands.describe(
        quantidade="Número de mensagens a apagar (ex: 10, 100, 1000, 5000...)"
    )
    async def limpar(
        self,
        interaction: discord.Interaction,
        quantidade: app_commands.Range[int, 1, 9999],
    ):
        # ── Permissão ───────────────────────────────────────────────────────────
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # ── Confirma antes de executar (resposta efêmera) ───────────────────────
        await interaction.response.defer(ephemeral=True)

        # ── Executa o purge ─────────────────────────────────────────────────────
        apagadas = await interaction.channel.purge(limit=quantidade)
        total = len(apagadas)

        # ── Feedback ao admin ───────────────────────────────────────────────────
        embed = discord.Embed(
            title="🧹  Canal Limpo",
            description=(
                f"**{total}** mensagem(ns) foram apagadas com sucesso.\n"
                f"Canal: {interaction.channel.mention}"
            ),
            color=0x2ECC71,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(
            text=f"Executado por {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        # ── Log ─────────────────────────────────────────────────────────────────
        await utils.enviar_log(
            self.bot,
            "Canal Limpo",
            (
                f"**{total}** mensagens apagadas em {interaction.channel.mention}\n"
                f"Executado por: **{interaction.user.display_name}**"
            ),
        )

    # ─── /add_membro ───────────────────────────────────────────────────────────
    @app_commands.command(
        name="add_membro",
        description="➕ Adiciona um usuário à facção dando o cargo de Membro. [Apenas Liderança]"
    )
    @app_commands.describe(
        usuario="Mencione o usuário a ser adicionado à facção",
        motivo="Motivo da entrada (opcional)"
    )
    async def add_membro(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        motivo: str = "Sem motivo especificado.",
    ):
        # ── Permissão ───────────────────────────────────────────────────────────
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # ── Busca o cargo pelo ID ───────────────────────────────────────────────
        cargo = interaction.guild.get_role(CARGO_MEMBRO_ID)

        if cargo is None:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Cargo Não Encontrado",
                    f"O cargo de Membro (ID `{CARGO_MEMBRO_ID}`) não foi encontrado neste servidor.\n"
                    "Verifique o ID em `config.py`."
                ),
                ephemeral=True,
            )

        # ── Verifica se já tem o cargo ──────────────────────────────────────────
        if cargo in usuario.roles:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Já é Membro",
                    f"{usuario.mention} já possui o cargo {cargo.mention}."
                ),
                ephemeral=True,
            )

        # ── Aplica o cargo ──────────────────────────────────────────────────────
        try:
            await usuario.add_roles(cargo, reason=f"Adicionado por {interaction.user} | {motivo}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Sem Permissão",
                    "O bot não tem permissão para gerenciar cargos.\n"
                    "Certifique-se de que o cargo do bot está **acima** do cargo de Membro."
                ),
                ephemeral=True,
            )

        # ── Embed de boas-vindas (público) ──────────────────────────────────────
        embed = discord.Embed(
            title="⚔️  Novo Membro da Facção!",
            description=(
                f"Bem-vindo(a) à facção, {usuario.mention}! 🎉\n\n"
                f"Você recebeu o cargo {cargo.mention} e agora faz parte dos nossos.\n"
                f"Seja leal, disciplinado e represente nossa bandeira com orgulho."
            ),
            color=0xFFD700,   # Dourado — cor de celebração
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="👮 Adicionado por",    value=interaction.user.mention, inline=True)
        embed.add_field(name="📋 Motivo",            value=f"`{motivo}`",            inline=True)
        embed.add_field(name="🏷️ Cargo recebido",   value=cargo.mention,            inline=True)
        embed.set_thumbnail(url=usuario.display_avatar.url)

        if interaction.guild.icon:
            embed.set_author(
                name=interaction.guild.name,
                icon_url=interaction.guild.icon.url,
            )

        embed.set_footer(
            text="⚔️ Facção Bot • Gerenciamento de Membros",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None,
        )

        await interaction.response.send_message(embed=embed)

        # ── DM ao novo membro ───────────────────────────────────────────────────
        try:
            dm_embed = discord.Embed(
                title="⚔️  Você entrou na Facção!",
                description=(
                    f"Olá, **{usuario.display_name}**!\n\n"
                    f"Você foi adicionado(a) à facção no servidor **{interaction.guild.name}**.\n"
                    f"Cargo concedido: **{cargo.name}**\n\n"
                    f"Seja bem-vindo(a) e bom jogo! 🎮"
                ),
                color=0xFFD700,
                timestamp=datetime.utcnow(),
            )
            dm_embed.set_footer(text="⚔️ Facção Bot")
            await usuario.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # Usuário com DM fechada — não quebra o comando

        # ── Log ─────────────────────────────────────────────────────────────────
        await utils.enviar_log(
            self.bot,
            "Membro Adicionado à Facção",
            (
                f"**Usuário:** {usuario.mention} (`{usuario.id}`)\n"
                f"**Cargo:** {cargo.mention}\n"
                f"**Motivo:** {motivo}\n"
                f"**Adicionado por:** {interaction.user.display_name}"
            ),
            cor=0xFFD700,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderacao(bot))
