"""
checks.py - Verificações de permissão por cargo
Todas as funções de checar se o usuário tem permissão para executar um comando.
"""

import discord
from discord.ext import commands
from config import CARGOS_LIDERANCA, CARGOS_FARM


def tem_cargo(interaction: discord.Interaction, cargo_ids: set) -> bool:
    """
    Verifica se o usuário tem pelo menos um dos cargos listados.
    Retorna True se tiver permissão, False caso contrário.
    """
    if not interaction.guild:
        return False
    ids_do_usuario = {role.id for role in interaction.user.roles}
    return bool(ids_do_usuario & cargo_ids)


def is_lideranca(interaction: discord.Interaction) -> bool:
    """Verifica se o usuário é Fundador ou Sub-Fundador."""
    return tem_cargo(interaction, CARGOS_LIDERANCA)


def is_farm_ou_lideranca(interaction: discord.Interaction) -> bool:
    """Verifica se o usuário é Fundador, Sub-Fundador ou Gerente de Farm."""
    return tem_cargo(interaction, CARGOS_FARM)


async def sem_permissao(interaction: discord.Interaction):
    """Envia uma mensagem de erro de permissão padronizada."""
    embed = discord.Embed(
        title="🚫 Acesso Negado",
        description=(
            "Você **não tem permissão** para usar este comando.\n\n"
            "Apenas membros com os cargos autorizados podem executar esta ação."
        ),
        color=0xFF0000,
    )
    embed.set_footer(text="Sistema de Permissões da Facção")
    await interaction.response.send_message(embed=embed, ephemeral=True)
