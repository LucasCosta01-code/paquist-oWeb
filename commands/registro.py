"""
commands/registro.py - Sistema de Registro de Entrada
Cria um painel com botões para novos membros escolherem se querem ser 'Recrutado' ou 'Visitante'.
"""

import discord
from discord import app_commands
from discord.ext import commands
from config import COR_PRINCIPAL

# IDs dos cargos
CARGO_RECRUTADO_ID = 1501834943657939097
CARGO_VISITANTE_ID = 1497655589365350522

class RegistroView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent View

    @discord.ui.button(label="Recrutado", style=discord.ButtonStyle.success, custom_id="btn_registro_recrutado", emoji="⚔️")
    async def btn_recrutado(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(CARGO_RECRUTADO_ID)
        visitante_role = interaction.guild.get_role(CARGO_VISITANTE_ID)
        
        if not role:
            await interaction.response.send_message("Cargo de recrutado não encontrado.", ephemeral=True)
            return
        
        try:
            if visitante_role in interaction.user.roles:
                await interaction.user.remove_roles(visitante_role)
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Você agora é um **Recrutado**! Bem-vindo!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Eu não tenho permissão para adicionar este cargo.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro: {e}", ephemeral=True)

    @discord.ui.button(label="Visitante", style=discord.ButtonStyle.secondary, custom_id="btn_registro_visitante", emoji="👋")
    async def btn_visitante(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(CARGO_VISITANTE_ID)
        recrutado_role = interaction.guild.get_role(CARGO_RECRUTADO_ID)
        
        if not role:
            await interaction.response.send_message("Cargo de visitante não encontrado.", ephemeral=True)
            return
        
        try:
            if recrutado_role in interaction.user.roles:
                await interaction.user.remove_roles(recrutado_role)
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Você agora é um **Visitante**!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Eu não tenho permissão para adicionar este cargo.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro: {e}", ephemeral=True)

class Registro(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Registra a view como persistente
        self.bot.add_view(RegistroView())

    @app_commands.command(name="setup_registro", description="Envia o painel de registro (Recrutado ou Visitante) no canal atual.")
    @app_commands.default_permissions(administrator=True)
    async def setup_registro(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👋 Bem-vindo! Escolha seu caminho",
            description=(
                "Para ter acesso ao servidor, por favor escolha uma das opções abaixo:\n\n"
                "⚔️ **Recrutado:** Se você veio para fazer parte da facção.\n"
                "👋 **Visitante:** Se você está apenas de passagem ou visitando."
            ),
            color=COR_PRINCIPAL
        )
        embed.set_footer(text="Selecione um dos botões abaixo para receber o seu cargo.")
        
        await interaction.channel.send(embed=embed, view=RegistroView())
        await interaction.response.send_message("Painel de registro criado com sucesso!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Registro(bot))
