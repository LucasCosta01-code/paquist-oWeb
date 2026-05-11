"""
commands/anti_link.py - Sistema de proteção contra links
Detecta, deleta e limpa links de todos os canais, exceto se enviados pelo Fundador.
"""

import discord
from discord import app_commands
from discord.ext import commands
import re
import asyncio
from datetime import datetime

import checks
import utils
from config import CARGO_FUNDADOR_ID, COR_ERRO, COR_SUCESSO

# Regex para detectar links (http, https, www)
LINK_REGEX = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE)

class AntiLink(commands.Cog):
    """Cog responsável por bloquear e limpar links do servidor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_founder(self, member: discord.Member) -> bool:
        """Verifica se o membro possui o cargo de Fundador."""
        return any(role.id == CARGO_FUNDADOR_ID for role in member.roles)

    # ─── EVENTO: on_message ──────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Monitora todas as mensagens em busca de links."""
        # Ignora bots e mensagens fora de guilda
        if message.author.bot or not message.guild:
            return

        # Verifica se contém link
        if LINK_REGEX.search(message.content):
            # Se NÃO for fundador, deleta
            if not self.is_founder(message.author):
                try:
                    await message.delete()
                    
                    # Envia aviso temporário
                    embed = discord.Embed(
                        title="🚫 Links Proibidos",
                        description=f"{message.author.mention}, você não tem permissão para enviar links neste servidor.",
                        color=COR_ERRO
                    )
                    aviso = await message.channel.send(embed=embed)
                    await asyncio.sleep(5)
                    await aviso.delete()
                    
                except discord.Forbidden:
                    print(f"[ERRO] Sem permissão para deletar mensagem em {message.channel.name}")
                except discord.NotFound:
                    pass

    # ─── COMANDO: /limpar_links_global ────────────────────────────────────────
    @app_commands.command(
        name="limpar_links_global",
        description="🛡️ Realiza uma varredura em TODOS os canais e remove links (exceto de Fundadores)."
    )
    async def limpar_links_global(self, interaction: discord.Interaction):
        """Varre todos os canais de texto do servidor em busca de links."""
        
        # Apenas liderança pode rodar o sweep
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        await interaction.response.defer(ephemeral=True)
        
        total_deletado = 0
        canais_processados = 0
        guild = interaction.guild

        embed_status = discord.Embed(
            title="🔍 Iniciando Varredura Global",
            description="Isso pode levar alguns minutos. O bot está percorrendo todos os canais de texto...",
            color=0x3498DB
        )
        msg_status = await interaction.followup.send(embed=embed_status, ephemeral=True)

        for channel in guild.text_channels:
            try:
                # Verifica se o bot tem permissão de ler e gerenciar mensagens no canal
                perms = channel.permissions_for(guild.me)
                if not perms.read_message_history or not perms.manage_messages:
                    continue

                canais_processados += 1
                
                # Varre as últimas 500 mensagens de cada canal (ajustável)
                # Usamos um limite para não travar o bot por horas em servidores gigantes
                async for message in channel.history(limit=500):
                    if LINK_REGEX.search(message.content):
                        # Verifica se o autor ainda está no server e se é fundador
                        # Se o autor saiu, deletamos o link de qualquer forma por segurança
                        is_founder_msg = False
                        if isinstance(message.author, discord.Member):
                            is_founder_msg = self.is_founder(message.author)
                        
                        if not is_founder_msg:
                            try:
                                await message.delete()
                                total_deletado += 1
                                # Pequeno delay para evitar rate limit agressivo
                                await asyncio.sleep(0.2)
                            except (discord.Forbidden, discord.NotFound):
                                continue

            except Exception as e:
                print(f"[ERRO] Falha ao processar canal {channel.name}: {e}")
                continue

        # Feedback final
        embed_final = discord.Embed(
            title="✅ Varredura Concluída",
            description=(
                f"A varredura global de links foi finalizada.\n\n"
                f"**Canais verificados:** {canais_processados}\n"
                f"**Links removidos:** {total_deletado}\n"
                f"**Regra aplicada:** Apenas links de **Fundadores** foram mantidos."
            ),
            color=COR_SUCESSO,
            timestamp=datetime.utcnow()
        )
        embed_final.set_footer(text=f"Executado por {interaction.user.display_name}")
        
        await interaction.followup.send(embed=embed_final, ephemeral=True)

        # Log da ação
        await utils.enviar_log(
            self.bot,
            "Varredura Global de Links",
            (
                f"**Executado por:** {interaction.user.mention}\n"
                f"**Total de links removidos:** {total_deletado}\n"
                f"**Canais processados:** {canais_processados}"
            ),
            cor=COR_SUCESSO
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(AntiLink(bot))
