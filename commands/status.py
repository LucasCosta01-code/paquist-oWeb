"""
commands/status.py - Comando /status
Exibe informações gerais e de segurança do servidor Discord.
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from config import (
    COR_PRINCIPAL,
    COR_SUCESSO,
    COR_ERRO,
    COR_AVISO,
    CARGOS_LIDERANCA,
)


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def _nivel_verificacao(nivel) -> tuple[str, str]:
    """Retorna emoji + descrição do nível de verificação do servidor."""
    mapa = {
        discord.VerificationLevel.none:    ("🔴", "Nenhuma – qualquer um pode entrar"),
        discord.VerificationLevel.low:     ("🟠", "Baixa – e-mail verificado"),
        discord.VerificationLevel.medium:  ("🟡", "Média – conta com +5 min"),
        discord.VerificationLevel.high:    ("🟢", "Alta – membro por +10 min"),
        discord.VerificationLevel.highest: ("🔵", "Máxima – celular verificado"),
    }
    return mapa.get(nivel, ("❓", str(nivel)))


def _nivel_filtro_conteudo(nivel) -> tuple[str, str]:
    """Retorna emoji + descrição do filtro de conteúdo explícito."""
    mapa = {
        discord.ContentFilter.disabled:        ("🔴", "Desativado"),
        discord.ContentFilter.no_role:         ("🟡", "Membros sem cargo"),
        discord.ContentFilter.all_members:     ("🟢", "Todos os membros"),
    }
    return mapa.get(nivel, ("❓", str(nivel)))


def _cor_seguranca(verificacao) -> int:
    """Retorna a cor do embed de acordo com o nível de verificação."""
    if verificacao in (discord.VerificationLevel.high, discord.VerificationLevel.highest):
        return COR_SUCESSO
    if verificacao == discord.VerificationLevel.medium:
        return COR_AVISO
    return COR_ERRO


def _formatar_data(dt: datetime) -> str:
    """Formata datetime para DD/MM/AAAA HH:MM UTC."""
    return dt.strftime("%d/%m/%Y %H:%M UTC")


# ─── COG ────────────────────────────────────────────────────────────────────────

class Status(commands.Cog):
    """Cog com o comando /status."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── /status ────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="status",
        description="📊 Exibe o status e informações de segurança do servidor."
    )
    async def status(self, interaction: discord.Interaction):
        """Exibe informações gerais e de segurança do servidor."""
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ Este comando só pode ser usado dentro de um servidor.",
                ephemeral=True
            )
            return

        # ── Dados gerais ────────────────────────────────────────────────────────
        total_membros  = guild.member_count or 0
        bots           = sum(1 for m in guild.members if m.bot)
        humanos        = total_membros - bots
        cargos         = len(guild.roles) - 1           # exclui @everyone
        canais_texto   = len(guild.text_channels)
        canais_voz     = len(guild.voice_channels)
        categorias     = len(guild.categories)
        emojis         = len(guild.emojis)
        criado_em      = _formatar_data(guild.created_at)

        # ── Segurança ────────────────────────────────────────────────────────────
        emoji_ver, desc_ver = _nivel_verificacao(guild.verification_level)
        emoji_fil, desc_fil = _nivel_filtro_conteudo(guild.explicit_content_filter)
        mfa_admin           = "✅ Ativado" if guild.mfa_level == discord.MFALevel.require_2fa else "❌ Desativado"

        # Canais com acesso público (@everyone com permissão de leitura)
        canais_publicos = 0
        everyone = guild.default_role
        for canal in guild.text_channels:
            perms = canal.permissions_for(everyone)
            if perms.read_messages:
                canais_publicos += 1

        # Quantos membros têm permissão de administrador (sem contar bots)
        admins = [
            m for m in guild.members
            if not m.bot and m.guild_permissions.administrator
        ]

        # Quantos cargos têm permissão de ban / kick
        cargos_ban  = sum(1 for r in guild.roles if r.permissions.ban_members)
        cargos_kick = sum(1 for r in guild.roles if r.permissions.kick_members)

        # ── Cor do embed de acordo com nível de segurança ────────────────────────
        cor = _cor_seguranca(guild.verification_level)

        # ── Monta o embed principal ──────────────────────────────────────────────
        embed = discord.Embed(
            title=f"📊 Status do Servidor — {guild.name}",
            color=cor,
            timestamp=datetime.now(timezone.utc)
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if guild.banner:
            embed.set_image(url=guild.banner.url)

        # Dono do servidor
        dono = guild.owner
        embed.add_field(
            name="👑 Proprietário",
            value=dono.mention if dono else "Desconhecido",
            inline=True
        )
        embed.add_field(
            name="📅 Criado em",
            value=criado_em,
            inline=True
        )
        embed.add_field(
            name="🆔 ID do Servidor",
            value=f"`{guild.id}`",
            inline=True
        )

        embed.add_field(name="\u200b", value="", inline=False)  # separador

        # ── Membros ──────────────────────────────────────────────────────────────
        embed.add_field(
            name="👥 Membros",
            value=(
                f"**Total:** {total_membros}\n"
                f"**Humanos:** {humanos}\n"
                f"**Bots:** {bots}"
            ),
            inline=True
        )

        # ── Estrutura ────────────────────────────────────────────────────────────
        embed.add_field(
            name="📂 Estrutura",
            value=(
                f"**Categorias:** {categorias}\n"
                f"**Canais texto:** {canais_texto}\n"
                f"**Canais voz:** {canais_voz}\n"
                f"**Cargos:** {cargos}\n"
                f"**Emojis:** {emojis}"
            ),
            inline=True
        )

        embed.add_field(name="\u200b", value="", inline=False)  # separador

        # ── Segurança ────────────────────────────────────────────────────────────
        embed.add_field(
            name="🔐 Segurança",
            value=(
                f"**Verificação:** {emoji_ver} {desc_ver}\n"
                f"**Filtro explícito:** {emoji_fil} {desc_fil}\n"
                f"**2FA para admins:** {mfa_admin}\n"
                f"**Canais públicos:** {canais_publicos} canal(is)\n"
                f"**Admins humanos:** {len(admins)} membro(s)\n"
                f"**Cargos com ban:** {cargos_ban} cargo(s)\n"
                f"**Cargos com kick:** {cargos_kick} cargo(s)"
            ),
            inline=False
        )

        # ── Aviso de risco ────────────────────────────────────────────────────────
        avisos = []
        if guild.verification_level in (discord.VerificationLevel.none, discord.VerificationLevel.low):
            avisos.append("⚠️ Verificação baixa — risco de raids e contas falsas.")
        if guild.explicit_content_filter == discord.ContentFilter.disabled:
            avisos.append("⚠️ Filtro de conteúdo explícito desativado.")
        if guild.mfa_level != discord.MFALevel.require_2fa:
            avisos.append("⚠️ 2FA não obrigatório para administradores.")
        if len(admins) > 5:
            avisos.append(f"⚠️ Muitos administradores ({len(admins)}) — reduza para maior segurança.")
        if canais_publicos > 10:
            avisos.append(f"⚠️ Muitos canais públicos ({canais_publicos}) — revise as permissões.")

        if avisos:
            embed.add_field(
                name="🚨 Alertas de Segurança",
                value="\n".join(avisos),
                inline=False
            )
        else:
            embed.add_field(
                name="✅ Segurança",
                value="Nenhum alerta detectado. Servidor bem configurado!",
                inline=False
            )

        embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)


# ─── SETUP ──────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(Status(bot))
