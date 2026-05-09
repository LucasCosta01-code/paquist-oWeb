"""
commands/boas_vindas.py - Sistema de Boas-Vindas para novos membros
Envia um embed bonito via webhook quando um novo membro entra no servidor.
"""

import discord
from discord.ext import commands
from datetime import datetime
import aiohttp

from config import WEBHOOK_BOAS_VINDAS


# ─── CONFIGURAÇÃO DO WEBHOOK ──────────────────────────────────────────────────
WEBHOOK_URL = WEBHOOK_BOAS_VINDAS


class BoasVindas(commands.Cog):
    """Cog responsável por enviar boas-vindas para novos membros via webhook."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Disparado quando um novo membro entra no servidor."""
        guild = member.guild
        membro_numero = guild.member_count

        # ── Monta o embed de boas-vindas ─────────────────────────────────────
        embed = {
            "title": "👋  Bem-vindo(a) à Família!",
            "description": (
                f"## {member.mention} acabou de chegar!\n\n"
                f"Seja muito bem-vindo(a) ao **{guild.name}**! 🎉\n"
                f"Estamos felizes em ter você conosco.\n\n"
                f"─────────────────────────────\n"
                f"📜 **Leia as regras** do servidor\n"
                f"💬 **Apresente-se** nos canais de bate-papo\n"
                f"🤝 **Interaja** com a comunidade\n"
                f"─────────────────────────────"
            ),
            "color": 0xB22222,  # Vermelho escuro (firebrick) - cor principal
            "thumbnail": {
                "url": member.display_avatar.url
            },
            "fields": [
                {
                    "name": "👤  Membro",
                    "value": f"```{member.display_name}```",
                    "inline": True
                },
                {
                    "name": "🔢  Você é o membro Nº",
                    "value": f"```{membro_numero}```",
                    "inline": True
                },
                {
                    "name": "📅  Entrou em",
                    "value": f"```{datetime.now().strftime('%d/%m/%Y às %H:%M')}```",
                    "inline": True
                },
                {
                    "name": "🏠  Servidor",
                    "value": f"```{guild.name}```",
                    "inline": False
                }
            ],
            "image": {
                "url": (
                    guild.banner.url if guild.banner
                    else "https://i.imgur.com/4M34hi2.png"
                )
            },
            "footer": {
                "text": f"⚔️ {guild.name} • Sistema de Boas-Vindas",
                "icon_url": guild.icon.url if guild.icon else None
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        # ── Envia via webhook ────────────────────────────────────────────────
        payload = {
            "username": guild.name,
            "avatar_url": guild.icon.url if guild.icon else None,
            "embeds": [embed]
        }

        # Remove None values do payload
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(WEBHOOK_URL, json=payload) as resp:
                    if resp.status == 204 or resp.status == 200:
                        print(f"[BOAS-VINDAS] Embed enviado para {member.display_name}")
                    else:
                        print(f"[BOAS-VINDAS] Erro ao enviar webhook: {resp.status}")
        except Exception as e:
            print(f"[BOAS-VINDAS] Erro ao enviar webhook: {e}")


async def setup(bot: commands.Bot):
    """Registra o Cog no bot."""
    await bot.add_cog(BoasVindas(bot))
