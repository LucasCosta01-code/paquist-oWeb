import discord
from discord import app_commands
from discord.ext import commands
import database as db
from config import (
    COR_PRINCIPAL, COR_SUCESSO, COR_ERRO, 
    CARGO_AUTO_ROLE_ID, CARGO_VISITANTE_ID, CARGO_RECRUTAMENTO_ID
)

class EntradaView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def check_link(self, interaction: discord.Interaction):
        """Verifica se o usuário está vinculado no banco de dados."""
        membro = db.get_membro(str(interaction.user.id))
        return membro is not None

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

        await member.add_roles(cargo_visitante, reason="Selecionou cargo de Visitante")
        
        # Se estiver vinculado, remove o cargo de 'vincular'
        is_linked = await self.check_link(interaction)
        msg = "✅ Você agora tem o cargo de **Visitante**!"
        
        if is_linked and cargo_vincular and cargo_vincular in member.roles:
            await member.remove_roles(cargo_vincular, reason="Usuário vinculado selecionou cargo")
            msg += "\n\n✨ Detectamos que você está vinculado! O cargo de 'Aguardando Vínculo' foi removido."
        elif not is_linked:
            msg += "\n\n⚠️ **Atenção:** Você ainda não vinculou seu Discord no site. Continue com o cargo de 'Aguardando Vínculo' até realizar o procedimento."

        await interaction.response.send_message(msg, ephemeral=True)

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
                title="🚫 Vínculo Obrigatório",
                description=(
                    "Para fazer o **Recrutamento**, você precisa primeiro vincular seu Discord no nosso site.\n\n"
                    "1️⃣ Acesse o site da Paquistão Web.\n"
                    "2️⃣ Faça login com seu Discord.\n"
                    "3️⃣ Após vincular, tente clicar aqui novamente."
                ),
                color=COR_ERRO
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Se chegou aqui, está vinculado
        await member.add_roles(cargo_recrutamento, reason="Selecionou cargo de Recrutamento")
        
        if cargo_vincular and cargo_vincular in member.roles:
            await member.remove_roles(cargo_vincular, reason="Usuário vinculado selecionou recrutamento")

        await interaction.response.send_message("✅ Você agora tem o cargo de **Recrutamento**! Aguarde um responsável.", ephemeral=True)

class Entrada(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(EntradaView(self.bot))

    @app_commands.command(name="painel_entrada", description="Envia o painel de seleção de cargos para novos membros.")
    async def painel_entrada(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Apenas administradores podem usar este comando.", ephemeral=True)

        embed = discord.Embed(
            title="⚔️  BEM-VINDO À TROPA PAQUISTÃO",
            description=(
                f"{'─' * 42}\n\n"
                "Para prosseguir, selecione uma das opções abaixo:\n\n"
                "👤 **Sou Visitante**\n"
                "Escolha esta opção se você veio apenas conhecer o servidor.\n\n"
                "⚔️ **Quero Recrutamento**\n"
                "Escolha esta opção se deseja entrar para a facção.\n"
                "*Obs: Requer vínculo obrigatório com o site.*\n\n"
                f"{'─' * 42}\n"
                "⚠️ **Atenção:** Caso não esteja vinculado, você manterá o cargo de 'Aguardando Vínculo'."
            ),
            color=COR_PRINCIPAL
        )
        embed.set_footer(text="⚔️ Paquistão Web • Sistema de Entrada")
        
        await interaction.response.send_message("Enviando painel...", ephemeral=True)
        await interaction.channel.send(embed=embed, view=EntradaView(self.bot))

async def setup(bot: commands.Bot):
    await bot.add_cog(Entrada(bot))
