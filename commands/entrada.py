import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone
import aiohttp
import database as db
from config import (
    COR_PRINCIPAL, COR_SUCESSO, COR_ERRO, 
    CARGO_AUTO_ROLE_ID, CARGO_VISITANTE_ID, CARGO_RECRUTAMENTO_ID, CARGO_VINCULADO_ID
)

class EntradaView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def check_link(self, interaction: discord.Interaction):
        """Verifica se o usuário está vinculado no banco de dados exclusivamente pelo Site (OAuth2)."""
        vinc = db.get_vinculo(str(interaction.user.id))
        return vinc is not None

    @discord.ui.button(
        label="Sou Visitante", 
        style=discord.ButtonStyle.secondary, 
        custom_id="entrada:visitante",
        emoji="👤"
    )
    async def visitante(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        cargo_visitante = interaction.guild.get_role(CARGO_VISITANTE_ID)
        cargo_vincular = interaction.guild.get_role(CARGO_AUTO_ROLE_ID)

        if not cargo_visitante:
            return await interaction.response.send_message("❌ Erro: Cargo de Visitante não encontrado.", ephemeral=True)

        is_linked = await self.check_link(interaction)
        
        # Adiciona cargo de visitante
        await member.add_roles(cargo_visitante, reason="Selecionou cargo de Visitante")
        
        embed = discord.Embed(
            title="👤  Acesso como Visitante",
            description=f"{'─' * 40}\n\n✅ Você agora tem o cargo de **Visitante**!",
            color=COR_SUCESSO
        )
        
        if is_linked:
            if cargo_vincular and cargo_vincular in member.roles:
                await member.remove_roles(cargo_vincular, reason="Membro vinculado acessou como visitante")
            embed.add_field(name="✨ Status de Vínculo", value="Detectamos que você está **Vinculado**! O cargo de espera foi removido.", inline=False)
        else:
            embed.add_field(name="⚠️ Status de Vínculo", value="Você ainda **não vinculou** seu Discord no site. Por segurança, você manterá o cargo de 'Aguardando Vínculo' até realizar o procedimento.", inline=False)

        embed.set_footer(text="⚔️ Paquistão Web • Sistema de Acesso")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Quero Recrutamento", 
        style=discord.ButtonStyle.success, 
        custom_id="entrada:recrutamento",
        emoji="⚔️"
    )
    async def recrutamento(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        cargo_recrutamento = interaction.guild.get_role(CARGO_RECRUTAMENTO_ID)
        cargo_vincular = interaction.guild.get_role(CARGO_AUTO_ROLE_ID)

        if not cargo_recrutamento:
            return await interaction.response.send_message("❌ Erro: Cargo de Recrutamento não encontrado.", ephemeral=True)

        is_linked = await self.check_link(interaction)
        
        if not is_linked:
            embed = discord.Embed(
                title="🚫  Vínculo Obrigatório",
                description=(
                    f"{'─' * 40}\n\n"
                    "Para fazer o **Recrutamento**, você precisa primeiro vincular seu Discord no nosso site.\n\n"
                    "1️⃣ Acesse o site da **Paquistão Web**.\n"
                    "2️⃣ Faça login com seu Discord.\n"
                    "3️⃣ Após vincular, clique aqui novamente.\n\n"
                    "⚠️ *Sem o vínculo, você não pode ser recrutado!*"
                ),
                color=COR_ERRO
            )
            embed.set_footer(text="⚔️ Paquistão Web • Bloqueio de Segurança")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Se chegou aqui, está vinculado
        await member.add_roles(cargo_recrutamento, reason="Selecionou cargo de Recrutamento (Vinculado)")
        
        if cargo_vincular and cargo_vincular in member.roles:
            await member.remove_roles(cargo_vincular, reason="Membro vinculado acessou recrutamento")

        embed = discord.Embed(
            title="⚔️  Iniciando Recrutamento",
            description=(
                f"{'─' * 40}\n\n"
                "✅ **Vínculo Detectado!**\n"
                "Você agora tem o cargo de **Recrutamento**.\n\n"
                "Aguarde em uma das salas de espera para que um responsável realize sua entrevista."
            ),
            color=COR_SUCESSO
        )
        embed.set_footer(text="⚔️ Paquistão Web • Sistema de Entrada")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Entrada(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(EntradaView(self.bot))
        if not self.verificar_vinculos_global.is_running():
            self.verificar_vinculos_global.start()

    def cog_unload(self):
        self.verificar_vinculos_global.cancel()

    @tasks.loop(minutes=4)
    async def verificar_vinculos_global(self):
        """Verifica todos os membros do servidor para ajustar o cargo de vínculo automaticamente (Real-time)."""
        print(f"🔄 [VARREDURA] Iniciando verificação de vínculos em {datetime.now()}...")
        
        for guild in self.bot.guilds:
            cargo_vincular = guild.get_role(CARGO_AUTO_ROLE_ID)
            cargo_vinculado = guild.get_role(CARGO_VINCULADO_ID)
            
            if not cargo_vincular and not cargo_vinculado:
                print(f"⚠️ [VARREDURA] Cargos não encontrados na guilda {guild.name}")
                continue

            count_vinculados = 0
            count_nao_vinculados = 0

            # Usa async for para iterar sobre todos os membros (mais robusto)
            async for member in guild.fetch_members(limit=None):
                if member.bot:
                    continue
                
                # Verifica vínculo no site (Discord API OAuth2)
                vinc_data = db.get_vinculo(str(member.id))
                is_linked = False
                
                if vinc_data:
                    # Tenta verificar se o token ainda é válido
                    token = vinc_data["access_token"]
                    if token:
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get('https://discord.com/api/users/@me', headers={'Authorization': f'Bearer {token}'}, timeout=5) as resp:
                                    if resp.status == 200:
                                        is_linked = True
                                    elif resp.status == 401:
                                        # Token expirado ou desautorizado! Remove do banco
                                        db.remover_vinculo(str(member.id))
                                        is_linked = False
                                    else:
                                        is_linked = True # Mantém por precaução
                        except:
                            is_linked = True # Erro de conexão, mantém status
                    else:
                        is_linked = True # Vínculo antigo sem token
                
                try:
                    if is_linked:
                        count_vinculados += 1
                        if cargo_vinculado and cargo_vinculado not in member.roles:
                            await member.add_roles(cargo_vinculado, reason="Automação: Vínculo ativo")
                        if cargo_vincular and cargo_vincular in member.roles:
                            await member.remove_roles(cargo_vincular, reason="Automação: Removendo aguardando vínculo")
                    else:
                        count_nao_vinculados += 1
                        if cargo_vinculado and cargo_vinculado in member.roles:
                            await member.remove_roles(cargo_vinculado, reason="Automação: Vínculo removido ou inexistente")
                        if cargo_vincular and cargo_vincular not in member.roles:
                            await member.add_roles(cargo_vincular, reason="Automação: Adicionando aguardando vínculo")
                except Exception as e:
                    continue

            print(f"✅ [VARREDURA] Guilda {guild.name} concluída. Vinculados: {count_vinculados} | Não Vinculados: {count_nao_vinculados}")

    @app_commands.command(name="varredura_vinculos", description="🔍 Força uma verificação de vínculo em todos os membros agora.")
    async def varredura_vinculos(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Apenas administradores podem usar este comando.", ephemeral=True)

        await interaction.response.send_message("🔍 Iniciando varredura de vínculos...", ephemeral=True)
        await self.verificar_vinculos_global()
        await interaction.followup.send("✅ Varredura concluída!", ephemeral=True)

    @app_commands.command(name="painel_entrada", description="Envia o painel de seleção de cargos para novos membros.")
    async def painel_entrada(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Apenas administradores podem usar este comando.", ephemeral=True)

        embed = discord.Embed(
            title="⚔️  BEM-VINDO À TROPA PAQUISTÃO",
            description=(
                f"{'─' * 42}\n\n"
                "Para prosseguir e ter acesso aos canais, selecione sua opção:\n\n"
                "👤 **Sou Visitante**\n"
                "Acesso básico para conhecer o servidor.\n\n"
                "⚔️ **Quero Recrutamento**\n"
                "Acesso para candidatos à facção.\n"
                "*(Requer vínculo obrigatório com o site)*\n\n"
                f"{'─' * 42}\n"
                "⚠️ **Atenção:** Se você não vincular seu Discord no site, manterá o cargo de 'Aguardando Vínculo' por segurança."
            ),
            color=COR_PRINCIPAL
        )
        embed.set_footer(text="⚔️ Paquistão Web • Sistema de Entrada")
        await interaction.response.send_message("Painel enviado!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=EntradaView(self.bot))

async def setup(bot: commands.Bot):
    await bot.add_cog(Entrada(bot))
