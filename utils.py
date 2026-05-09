"""
utils.py - Funções utilitárias reutilizáveis
Embeds padrão, envio de logs, formatações.
"""

import discord
from datetime import datetime
from config import COR_PRINCIPAL, COR_ERRO, COR_SUCESSO, LOG_CHANNEL_ID


def embed_padrao(titulo: str, descricao: str = "", cor: int = COR_PRINCIPAL) -> discord.Embed:
    """Cria um embed padrão do bot com rodapé e timestamp."""
    embed = discord.Embed(title=titulo, description=descricao, color=cor)
    embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")
    embed.timestamp = datetime.utcnow()
    return embed


def embed_sucesso(titulo: str, descricao: str = "") -> discord.Embed:
    """Embed verde de sucesso."""
    return embed_padrao(f"✅  {titulo}", descricao, COR_SUCESSO)


def embed_erro(titulo: str, descricao: str = "") -> discord.Embed:
    """Embed vermelho de erro."""
    return embed_padrao(f"❌  {titulo}", descricao, COR_ERRO)


def data_agora() -> str:
    """Retorna a data/hora atual formatada no fuso de Brasília (UTC-3)."""
    from datetime import timedelta
    agora_br = datetime.utcnow() - timedelta(hours=3)
    return agora_br.strftime("%d/%m/%Y %H:%M")


async def enviar_log(bot: discord.Client, titulo: str, descricao: str, cor: int = COR_PRINCIPAL):
    """Envia uma mensagem de log no canal configurado."""
    if not LOG_CHANNEL_ID:
        return  # Canal de log não configurado
    canal = bot.get_channel(LOG_CHANNEL_ID)
    if canal:
        embed = discord.Embed(title=f"📋 LOG │ {titulo}", description=descricao, color=cor)
        embed.timestamp = datetime.utcnow()
        embed.set_footer(text="Sistema de Logs da Facção")
        await canal.send(embed=embed)
