"""
commands/monitoria.py - Sistema de Monitoria via DM (Modmail)
Permite que membros conversem com a liderança pela DM do bot usando Threads (Tópicos).
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import re

import checks
import utils
from config import COR_PRINCIPAL, COR_SUCESSO, COR_ERRO, COR_INFO, CANAL_MONITORIA_ID

def extrair_id_da_thread(thread_name: str) -> str:
    """Extrai o ID do usuário do nome da thread no formato 'Nome - ID'."""
    match = re.search(r'- (\d+)$', thread_name)
    if match:
        return match.group(1)
    return None

class Monitoria(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_or_create_thread(self, user: discord.User, guild: discord.Guild) -> discord.Thread:
        """Encontra ou cria a thread de monitoria para o usuário."""
        if not CANAL_MONITORIA_ID:
            return None
            
        canal = guild.get_channel(CANAL_MONITORIA_ID)
        if not canal or not isinstance(canal, discord.TextChannel):
            return None

        nome_thread = f"{user.display_name} - {user.id}"
        
        # Procurar nas threads ativas
        for thread in canal.threads:
            if thread.name == nome_thread and not thread.archived:
                return thread
                
        # Procurar nas threads arquivadas (opcional)
        async for thread in canal.archived_threads(limit=50):
            if thread.name == nome_thread:
                # Desarquivar
                await thread.edit(archived=False)
                return thread
                
        # Criar nova
        try:
            msg = await canal.send(
                embed=discord.Embed(
                    title="📞 Novo Chamado de Monitoria", 
                    description=f"Usuário: {user.mention} (`{user.id}`)\nTodas as mensagens enviadas aqui serão redirecionadas para a DM dele.",
                    color=COR_PRINCIPAL
                )
            )
            thread = await canal.create_thread(name=nome_thread, message=msg, type=discord.ChannelType.public_thread)
            return thread
        except discord.HTTPException:
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # 1. Se for uma mensagem enviada na DM para o bot
        if isinstance(message.channel, discord.DMChannel):
            if not CANAL_MONITORIA_ID:
                return
                
            # Achar a Guild (pegar a primeira onde o bot e o membro estão, ou definir no config)
            guild = None
            for g in self.bot.guilds:
                if g.get_channel(CANAL_MONITORIA_ID):
                    guild = g
                    break
            
            if not guild:
                return

            thread = await self.get_or_create_thread(message.author, guild)
            if thread:
                # Encaminhar a mensagem para a thread
                anexos = [await a.to_file() for a in message.attachments]
                embed = discord.Embed(description=message.content, color=COR_INFO, timestamp=datetime.now(timezone.utc))
                embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                await thread.send(embed=embed, files=anexos)

        # 2. Se for uma mensagem de Admin enviada dentro de uma Thread de Monitoria
        elif isinstance(message.channel, discord.Thread):
            if message.channel.parent_id == CANAL_MONITORIA_ID:
                user_id = extrair_id_da_thread(message.channel.name)
                if user_id:
                    user = self.bot.get_user(int(user_id))
                    if user:
                        # Encaminhar para o usuário
                        anexos = [await a.to_file() for a in message.attachments]
                        embed = discord.Embed(description=message.content, color=COR_SUCESSO, timestamp=datetime.now(timezone.utc))
                        embed.set_author(name=f"👮 Liderança ({message.author.display_name})", icon_url=message.author.display_avatar.url)
                        embed.set_footer(text="Para responder, basta digitar aqui.")
                        try:
                            await user.send(embed=embed, files=anexos)
                            await message.add_reaction("✅")
                        except discord.Forbidden:
                            await message.channel.send("❌ Não foi possível enviar a mensagem (DM fechada).")

    @app_commands.command(name="abrir_monitoria", description="📞 Abre uma conversa na DM com um membro.")
    @app_commands.describe(membro="Membro para contatar", mensagem="Mensagem inicial")
    async def abrir_monitoria(self, interaction: discord.Interaction, membro: discord.Member, mensagem: str):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
            
        await interaction.response.defer(ephemeral=True)
        
        thread = await self.get_or_create_thread(membro, interaction.guild)
        if not thread:
            return await interaction.followup.send("❌ Não foi possível criar/encontrar a thread de monitoria. Verifique o CANAL_MONITORIA_ID.")
            
        embed = discord.Embed(description=mensagem, color=COR_SUCESSO, timestamp=datetime.now(timezone.utc))
        embed.set_author(name=f"👮 Liderança ({interaction.user.display_name})", icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="Para responder, basta digitar aqui.")
        
        try:
            await membro.send(embed=embed)
            await thread.send(f"**Liderança ({interaction.user.display_name}) abriu o chamado:**\n{mensagem}")
            await interaction.followup.send(f"✅ Conversa iniciada em {thread.mention}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Não foi possível enviar a mensagem. A DM do membro pode estar fechada.")

class FecharMonitoriaView(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=60)
        self.user = user

    @discord.ui.button(label="Apenas Fechar Tópico", style=discord.ButtonStyle.secondary, emoji="✅")
    async def btn_fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._fechar_topico(interaction)
        
    @discord.ui.button(label="Remover Último Ponto", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def btn_remover(self, interaction: discord.Interaction, button: discord.ui.Button):
        import database as db
        removido = db.deletar_ultimo_ponto(str(self.user.id))
        
        if removido:
            await interaction.channel.send("🗑️ **Último registro de ponto removido do sistema.**")
        else:
            await interaction.channel.send("⚠️ Não foi possível encontrar nenhum ponto para remover.")
            
        await self._fechar_topico(interaction)

    async def _fechar_topico(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(title="🔒 Conversa Encerrada", description="A liderança encerrou este chamado.", color=COR_ERRO)
            await self.user.send(embed=embed)
        except:
            pass
        
        await interaction.response.edit_message(content="🔒 Fechando tópico...", view=None)
        await interaction.channel.edit(archived=True, locked=True)

    @app_commands.command(name="fechar_monitoria", description="🔒 Fecha/Arquiva o tópico de monitoria atual.")
    async def fechar_monitoria(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
            
        if not isinstance(interaction.channel, discord.Thread) or interaction.channel.parent_id != CANAL_MONITORIA_ID:
            return await interaction.response.send_message("❌ Use este comando dentro de uma thread de monitoria.", ephemeral=True)
            
        user_id = extrair_id_da_thread(interaction.channel.name)
        user = None
        if user_id:
            user = self.bot.get_user(int(user_id))
            
        if not user:
            # Força o fechamento direto se não achar o usuário
            await interaction.response.send_message("🔒 Usuário não encontrado. Fechando tópico...")
            await interaction.channel.edit(archived=True, locked=True)
            return

        embed = discord.Embed(
            title="❓ Confirmação de Fechamento",
            description="Você deseja apenas fechar este chamado ou também quer **remover/zerar** o último ponto batido por este membro?",
            color=COR_AVISO
        )
        view = FecharMonitoriaView(user)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(Monitoria(bot))
