"""
commands/bate_ponto.py - Sistema de Bate-Ponto para membros com cargo obrigatório
Permite que membros batam o ponto (entrada/saída) via botões interativos.
Registra tudo em logs com tempo de serviço calculado.
Gerencia cargos de "Em Serviço" e "Fora de Serviço" automaticamente.
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta

import database as db
from config import (
    COR_PRINCIPAL, COR_SUCESSO, COR_ERRO, COR_AVISO, COR_INFO,
    CARGO_OBRIGADO_META_ID, CARGOS_LIDERANCA,
    CANAL_LOG_PONTO_ID, CANAL_BATER_PONTO_ID,
    CARGO_EM_SERVICO_ID, CARGO_FORA_SERVICO_ID
)
import checks
import asyncio

_fora_da_call_desde = {} # discord_id (str) -> datetime
_aguardando_resposta = set() # discord_id (str)

# ─── CONFIGURAÇÃO DE CARGOS ───────────────────────────────────────────────────
CARGO_PONTO_ID = CARGO_OBRIGADO_META_ID


def formatar_duracao(segundos: int) -> str:
    """Formata uma duração em segundos para uma string legível."""
    if segundos < 60:
        return f"{segundos}s"
    elif segundos < 3600:
        minutos = segundos // 60
        segs = segundos % 60
        return f"{minutos}min {segs}s"
    else:
        horas = segundos // 3600
        minutos = (segundos % 3600) // 60
        segs = segundos % 60
        return f"{horas}h {minutos}min {segs}s"


async def gerenciar_cargos_ponto(member: discord.Member, batendo: bool):
    """Adiciona/remove cargos de serviço ao bater/parar ponto."""
    guild = member.guild
    cargo_em_servico = guild.get_role(CARGO_EM_SERVICO_ID)
    cargo_fora_servico = guild.get_role(CARGO_FORA_SERVICO_ID)

    try:
        if batendo:
            # Bater ponto: adiciona "Em Serviço", remove "Fora de Serviço"
            if cargo_em_servico:
                await member.add_roles(cargo_em_servico, reason="Bate-Ponto: Entrada")
            if cargo_fora_servico and cargo_fora_servico in member.roles:
                await member.remove_roles(cargo_fora_servico, reason="Bate-Ponto: Entrada")
        else:
            # Parar ponto: adiciona "Fora de Serviço", remove "Em Serviço"
            if cargo_fora_servico:
                await member.add_roles(cargo_fora_servico, reason="Bate-Ponto: Saída")
            if cargo_em_servico and cargo_em_servico in member.roles:
                await member.remove_roles(cargo_em_servico, reason="Bate-Ponto: Saída")
    except discord.Forbidden:
        print(f"[BATE-PONTO] Sem permissão para gerenciar cargos de {member.display_name}")
    except Exception as e:
        print(f"[BATE-PONTO] Erro ao gerenciar cargos: {e}")


# ═══════════════════════════════════════════════════════════════════
#  VIEW DOS BOTÕES DE BATE-PONTO
# ═══════════════════════════════════════════════════════════════════

class BatePontoView(discord.ui.View):
    """View persistente com os botões de Bater Ponto e Parar Ponto."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="  Bater Ponto",
        style=discord.ButtonStyle.success,
        custom_id="bateponto:bater",
        emoji="🟢",
        row=0
    )
    async def bater_ponto(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Registra a entrada do membro."""
        member = interaction.user
        cargo_ids = {role.id for role in member.roles}

        if CARGO_PONTO_ID not in cargo_ids:
            embed = discord.Embed(
                title="🚫  Acesso Negado",
                description="Você **não possui o cargo** necessário para bater ponto.",
                color=COR_ERRO
            )
            embed.set_footer(text="⚔️ Sistema de Bate-Ponto")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        ponto_aberto = db.get_ponto_aberto(str(member.id))
        if ponto_aberto:
            embed = discord.Embed(
                title="⚠️  Ponto Já Aberto",
                description=(
                    f"Você já tem um ponto **aberto** desde:\n"
                    f"```📅 {ponto_aberto['entrada']}```\n"
                    f"Use o botão **🔴 Parar Ponto** para encerrar primeiro."
                ),
                color=COR_AVISO
            )
            embed.set_footer(text="⚔️ Sistema de Bate-Ponto")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        agora = (datetime.utcnow() - timedelta(hours=3))
        data_formatada = agora.strftime("%d/%m/%Y às %H:%M:%S")
        db.registrar_ponto_entrada(str(member.id), agora.isoformat())

        # Gerencia cargos
        await gerenciar_cargos_ponto(member, batendo=True)

        embed_confirmacao = discord.Embed(
            title="✅  Ponto Registrado!",
            description=(
                f"Seu ponto foi **aberto** com sucesso!\n\n"
                f"⏰ **Entrada:** `{data_formatada}`\n\n"
                f"🏷️ Cargo **Em Serviço** adicionado!\n\n"
                f"Quando terminar, clique em **🔴 Parar Ponto**."
            ),
            color=COR_SUCESSO
        )
        embed_confirmacao.set_thumbnail(url=member.display_avatar.url)
        embed_confirmacao.set_footer(text="⚔️ Sistema de Bate-Ponto")
        embed_confirmacao.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=embed_confirmacao, ephemeral=True)

        canal_log = self.bot.get_channel(CANAL_LOG_PONTO_ID)
        if canal_log:
            embed_log = discord.Embed(
                title="🟢  Ponto Aberto",
                description=f"{'─' * 42}",
                color=0x2ECC71
            )
            embed_log.add_field(name="👤  Membro", value=f"{member.mention}\n`{member.display_name}`", inline=True)
            embed_log.add_field(name="⏰  Entrada", value=f"```{data_formatada}```", inline=True)
            embed_log.add_field(name="🏷️  Cargo", value=f"```🟢 Em Serviço```", inline=True)
            embed_log.set_thumbnail(url=member.display_avatar.url)
            embed_log.set_footer(text="⚔️ Paquistão Web • Log de Entrada")
            embed_log.timestamp = datetime.utcnow()
            await canal_log.send(embed=embed_log)

    @discord.ui.button(
        label="  Parar Ponto",
        style=discord.ButtonStyle.danger,
        custom_id="bateponto:parar",
        emoji="🔴",
        row=0
    )
    async def parar_ponto(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Registra a saída do membro e calcula o tempo de serviço."""
        member = interaction.user
        cargo_ids = {role.id for role in member.roles}

        if CARGO_PONTO_ID not in cargo_ids:
            embed = discord.Embed(
                title="🚫  Acesso Negado",
                description="Você **não possui o cargo** necessário para bater ponto.",
                color=COR_ERRO
            )
            embed.set_footer(text="⚔️ Sistema de Bate-Ponto")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        ponto_aberto = db.get_ponto_aberto(str(member.id))
        if not ponto_aberto:
            embed = discord.Embed(
                title="⚠️  Nenhum Ponto Aberto",
                description="Você **não tem nenhum ponto** aberto no momento.\n\nUse o botão **🟢 Bater Ponto** para iniciar.",
                color=COR_AVISO
            )
            embed.set_footer(text="⚔️ Sistema de Bate-Ponto")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        agora = (datetime.utcnow() - timedelta(hours=3))
        entrada_dt = datetime.fromisoformat(ponto_aberto['entrada'])
        segundos_total = int((agora - entrada_dt).total_seconds())
        duracao_formatada = formatar_duracao(segundos_total)
        data_saida = agora.strftime("%d/%m/%Y às %H:%M:%S")
        data_entrada = entrada_dt.strftime("%d/%m/%Y às %H:%M:%S")

        db.fechar_ponto(ponto_aberto['id'], agora.isoformat(), segundos_total)

        # Gerencia cargos
        await gerenciar_cargos_ponto(member, batendo=False)

        embed_confirmacao = discord.Embed(
            title="🔴  Ponto Encerrado!",
            description=(
                f"Seu ponto foi **fechado** com sucesso!\n\n"
                f"⏰ **Entrada:** `{data_entrada}`\n"
                f"⏰ **Saída:** `{data_saida}`\n"
                f"⏱️ **Tempo de Serviço:** `{duracao_formatada}`\n\n"
                f"🏷️ Cargo **Fora de Serviço** adicionado!"
            ),
            color=COR_ERRO
        )
        embed_confirmacao.set_thumbnail(url=member.display_avatar.url)
        embed_confirmacao.set_footer(text="⚔️ Sistema de Bate-Ponto")
        embed_confirmacao.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=embed_confirmacao, ephemeral=True)

        canal_log = self.bot.get_channel(CANAL_LOG_PONTO_ID)
        if canal_log:
            embed_log = discord.Embed(
                title="🔴  Ponto Fechado",
                description=f"{'─' * 42}",
                color=0xE74C3C
            )
            embed_log.add_field(name="👤  Membro", value=f"{member.mention}\n`{member.display_name}`", inline=True)
            embed_log.add_field(name="⏰  Entrada", value=f"```{data_entrada}```", inline=True)
            embed_log.add_field(name="⏰  Saída", value=f"```{data_saida}```", inline=True)
            embed_log.add_field(name="⏱️  Tempo", value=f"```{duracao_formatada}```", inline=False)
            embed_log.add_field(name="🏷️  Cargo", value=f"```🔴 Fora de Serviço```", inline=True)
            embed_log.set_thumbnail(url=member.display_avatar.url)
            embed_log.set_footer(text="⚔️ Paquistão Web • Log de Saída")
            embed_log.timestamp = datetime.utcnow()
            await canal_log.send(embed=embed_log)

    @discord.ui.button(
        label="  Meu Histórico",
        style=discord.ButtonStyle.secondary,
        custom_id="bateponto:historico",
        emoji="📊",
        row=1
    )
    async def meu_historico(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mostra o histórico de pontos do membro."""
        member = interaction.user
        cargo_ids = {role.id for role in member.roles}

        if CARGO_PONTO_ID not in cargo_ids:
            embed = discord.Embed(title="🚫  Acesso Negado", description="Você **não possui o cargo** necessário.", color=COR_ERRO)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        registros = db.get_historico_ponto(str(member.id), limite=10)
        if not registros:
            embed = discord.Embed(title="📊  Histórico de Ponto", description="Você ainda **não possui** registros de ponto.", color=COR_INFO)
            embed.set_footer(text="⚔️ Sistema de Bate-Ponto")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title=f"📊  Histórico de Ponto │ {member.display_name}",
            description="─────────────────────────────\nÚltimos **10** registros:\n",
            color=COR_PRINCIPAL
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        tempo_total = 0

        for i, reg in enumerate(registros, 1):
            entrada_dt = datetime.fromisoformat(reg['entrada'])
            entrada_fmt = entrada_dt.strftime("%d/%m às %H:%M")
            if reg['saida']:
                saida_fmt = datetime.fromisoformat(reg['saida']).strftime("%d/%m às %H:%M")
                duracao_fmt = formatar_duracao(reg['duracao_segundos'] or 0)
                tempo_total += reg['duracao_segundos'] or 0
                status = "🔴 Fechado"
            else:
                saida_fmt = "—"
                duracao_fmt = "⏳ Em andamento"
                status = "🟢 Aberto"
            embed.add_field(name=f"#{i} │ {status}", value=f"📥 `{entrada_fmt}` → 📤 `{saida_fmt}`\n⏱️ **{duracao_fmt}**", inline=False)

        embed.add_field(name="─────────────────────────────", value=f"⏱️ **Tempo Total:** `{formatar_duracao(tempo_total)}`", inline=False)
        embed.set_footer(text="⚔️ Sistema de Bate-Ponto • Histórico")
        embed.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ═══════════════════════════════════════════════════════════════════
#  AUDITORIA VIEW
# ═══════════════════════════════════════════════════════════════════

class AuditoriaPontoView(discord.ui.View):
    def __init__(self, member: discord.Member, bot: commands.Bot):
        super().__init__(timeout=None)
        self.member = member
        self.bot = bot

    @discord.ui.button(label="Fechar Ponto Agora", style=discord.ButtonStyle.danger, emoji="🔴")
    async def btn_fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in _aguardando_resposta:
            _aguardando_resposta.remove(str(interaction.user.id))
        
        ponto_aberto = db.get_ponto_aberto(str(interaction.user.id))
        if ponto_aberto:
            entrada = datetime.fromisoformat(ponto_aberto['entrada'])
            saida = (datetime.utcnow() - timedelta(hours=3))
            duracao = int((saida - entrada).total_seconds())
            db.fechar_ponto(ponto_aberto['id'], saida.isoformat(), duracao)
            await gerenciar_cargos_ponto(self.member, False)
            
            await interaction.response.send_message("Seu ponto foi fechado com sucesso.", ephemeral=True)
            self.stop()
            try: await interaction.message.edit(view=None)
            except: pass
            
            # Avisa nos logs do bate-ponto
            canal_log = self.bot.get_channel(CANAL_LOG_PONTO_ID)
            if canal_log:
                data_entrada = entrada.strftime("%d/%m/%Y às %H:%M:%S")
                data_saida = saida.strftime("%d/%m/%Y às %H:%M:%S")
                duracao_formatada = formatar_duracao(duracao)
                
                embed_log = discord.Embed(
                    title="🔴  Ponto Fechado (Auditoria Manual)",
                    description=f"**Motivo:** Membro clicou em fechar pela DM da auditoria.\n─────────────────────────────",
                    color=0xE74C3C
                )
                embed_log.add_field(name="👤  Membro", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
                embed_log.add_field(name="⏰  Entrada", value=f"```{data_entrada}```", inline=True)
                embed_log.add_field(name="⏰  Saída", value=f"```{data_saida}```", inline=True)
                embed_log.add_field(name="⏱️  Tempo de Serviço", value=f"```{duracao_formatada}```", inline=False)
                embed_log.add_field(name="🏷️  Cargo", value=f"```🔴 Fora de Serviço```", inline=True)
                embed_log.add_field(name="📊  Status", value="```🔴 FORA DE SERVIÇO```", inline=True)
                embed_log.set_thumbnail(url=interaction.user.display_avatar.url)
                embed_log.set_footer(text="⚔️ Sistema de Bate-Ponto • Log de Saída (Auditoria)")
                embed_log.timestamp = datetime.utcnow()
                await canal_log.send(embed=embed_log)
        else:
            await interaction.response.send_message("Seu ponto já está fechado.", ephemeral=True)

    @discord.ui.button(label="Estou em Serviço (Manter)", style=discord.ButtonStyle.success, emoji="🟢")
    async def btn_manter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) in _aguardando_resposta:
            _aguardando_resposta.remove(str(interaction.user.id))
        
        await interaction.response.send_message("Ok! Seu ponto foi mantido aberto.", ephemeral=True)
        self.stop()
        try: await interaction.message.edit(view=None)
        except: pass

# ═══════════════════════════════════════════════════════════════════
#  COG PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

class BatePonto(commands.Cog):
    """Cog responsável pelo sistema de bate-ponto."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Registra a View persistente, envia/recupera o painel fixo e inicia verificação."""
        self.bot.add_view(BatePontoView(self.bot))
        print("[BATE-PONTO] View persistente registrada.")

        # Envia ou recupera o painel fixo no canal
        await self._garantir_painel_fixo()

        if not self.verificar_cargos_ponto.is_running():
            self.verificar_cargos_ponto.start()
            
        if not self.auditoria_voz.is_running():
            self.auditoria_voz.start()

    def cog_unload(self):
        self.verificar_cargos_ponto.cancel()
        self.auditoria_voz.cancel()

    def _criar_embed_painel(self) -> discord.Embed:
        """Cria o embed do painel de bate-ponto."""
        embed = discord.Embed(
            title="⚔️  SISTEMA DE BATE-PONTO",
            description=(
                f"{'─' * 30}\n\n"
                "**Registre sua entrada e saída de serviço.**\n"
                "O sistema calcula automaticamente seu tempo\n"
                "e gerencia seus cargos de serviço.\n\n"
                f"{'─' * 30}\n\n"
                "🟢 **Bater Ponto** → Entrada + Cargo **Em Serviço**\n"
                "🔴 **Parar Ponto** → Saída + Cargo **Fora de Serviço**\n"
                "📊 **Meu Histórico** → Seus últimos registros\n\n"
                f"{'─' * 30}\n\n"
                f"🏷️ **Em Serviço:** <@&{CARGO_EM_SERVICO_ID}>\n"
                f"🏷️ **Fora de Serviço:** <@&{CARGO_FORA_SERVICO_ID}>\n\n"
                "⚠️ *Lembre-se de parar o ponto ao encerrar!*"
            ),
            color=0x2ECC71  # Verde
        )
        embed.set_footer(text="⚔️ Paquistão Web • Sistema de Bate-Ponto")
        embed.timestamp = datetime.utcnow()
        return embed

    async def _garantir_painel_fixo(self):
        """Garante que o painel fixo existe no canal. Recupera o existente ou cria um novo."""
        canal = self.bot.get_channel(CANAL_BATER_PONTO_ID)
        if not canal:
            print("[BATE-PONTO] Canal de bate-ponto não encontrado.")
            return

        # Tenta recuperar o ID salvo no banco
        msg_id_salvo = db.get_config("painel_ponto_msg_id")

        if msg_id_salvo:
            try:
                msg = await canal.fetch_message(int(msg_id_salvo))
                # Atualiza o embed e a view (caso o bot tenha reiniciado)
                await msg.edit(embed=self._criar_embed_painel(), view=BatePontoView(self.bot))
                print(f"[BATE-PONTO] Painel fixo recuperado (ID: {msg_id_salvo})")
                return
            except (discord.NotFound, discord.HTTPException):
                print("[BATE-PONTO] Painel anterior não encontrado, criando novo...")

        # Cria novo painel
        msg = await canal.send(embed=self._criar_embed_painel(), view=BatePontoView(self.bot))
        db.set_config("painel_ponto_msg_id", str(msg.id))
        print(f"[BATE-PONTO] Novo painel fixo enviado (ID: {msg.id})")

    # ─── VERIFICAÇÃO AUTOMÁTICA DE CARGOS ──────────────────────────────────────
    @tasks.loop(minutes=5)
    async def verificar_cargos_ponto(self):
        """Verifica a cada 5 min se os cargos de serviço estão corretos."""
        for guild in self.bot.guilds:
            cargo_membro = guild.get_role(CARGO_PONTO_ID)
            cargo_em = guild.get_role(CARGO_EM_SERVICO_ID)
            cargo_fora = guild.get_role(CARGO_FORA_SERVICO_ID)
            if not cargo_membro or not cargo_em or not cargo_fora:
                continue

            for member in cargo_membro.members:
                ponto_aberto = db.get_ponto_aberto(str(member.id))
                try:
                    if ponto_aberto:
                        if cargo_em not in member.roles:
                            await member.add_roles(cargo_em, reason="Verificação automática de ponto")
                        if cargo_fora in member.roles:
                            await member.remove_roles(cargo_fora, reason="Verificação automática de ponto")
                    else:
                        if cargo_em in member.roles:
                            await member.remove_roles(cargo_em, reason="Verificação automática de ponto")
                        if cargo_fora not in member.roles:
                            await member.add_roles(cargo_fora, reason="Verificação automática de ponto")
                except Exception:
                    pass

    @verificar_cargos_ponto.before_loop
    async def before_verificar(self):
        await self.bot.wait_until_ready()

    # ─── AUDITORIA DE VOZ (VARREDURA) ──────────────────────────────────────────
    @tasks.loop(minutes=1)
    async def auditoria_voz(self):
        """Verifica se membros com ponto aberto estão fora de call por muito tempo."""
        ativa = db.get_config("auditoria_ponto_ativa")
        if ativa != "1":
            return

        limite_fora = int(db.get_config("auditoria_tempo_fora") or "60")
        
        for guild in self.bot.guilds:
            cargo_membro = guild.get_role(CARGO_PONTO_ID)
            if not cargo_membro:
                continue

            for member in cargo_membro.members:
                if str(member.id) in _aguardando_resposta:
                    continue # Já enviou DM, aguardando resposta

                ponto_aberto = db.get_ponto_aberto(str(member.id))
                if not ponto_aberto:
                    if str(member.id) in _fora_da_call_desde:
                        del _fora_da_call_desde[str(member.id)]
                    continue

                # Membro tem ponto aberto. Está em call?
                if member.voice and member.voice.channel:
                    if str(member.id) in _fora_da_call_desde:
                        del _fora_da_call_desde[str(member.id)]
                else:
                    # Não está em call
                    agora = (datetime.utcnow() - timedelta(hours=3))
                    if str(member.id) not in _fora_da_call_desde:
                        _fora_da_call_desde[str(member.id)] = agora
                    else:
                        tempo_fora = (agora - _fora_da_call_desde[str(member.id)]).total_seconds() / 60
                        if tempo_fora >= limite_fora:
                            # Estourou o tempo, envia DM
                            self.bot.loop.create_task(self.enviar_auditoria_dm(member))
                            _aguardando_resposta.add(str(member.id))
                            del _fora_da_call_desde[str(member.id)]

    @auditoria_voz.before_loop
    async def before_auditoria(self):
        await self.bot.wait_until_ready()

    async def enviar_auditoria_dm(self, member: discord.Member, instantaneo: bool = False):
        """Envia DM de auditoria aguardando resposta do membro."""
        limite_resp = int(db.get_config("auditoria_tempo_resposta") or "15")
        
        embed = discord.Embed(
            title="⚠️ Auditoria de Bate-Ponto",
            description=(
                f"Olá! O sistema identificou que você está com o **Ponto Aberto**, mas não "
                f"está em nenhum canal de voz da facção "
                f"{'há muito tempo' if not instantaneo else 'neste momento'}.\n\n"
                f"Você tem **{limite_resp} minutos** para responder clicando em um dos botões abaixo.\n"
                f"Caso contrário, seu ponto será **FECHADO AUTOMATICAMENTE**."
            ),
            color=COR_AVISO
        )
        embed.set_footer(text="⚔️ Facção Bot • Auditoria Automática")
        
        view = AuditoriaPontoView(member, self.bot)
        try:
            msg = await member.send(embed=embed, view=view)
            
            # Espera o tempo de resposta
            await asyncio.sleep(limite_resp * 60)
            
            if str(member.id) in _aguardando_resposta:
                # Membro não respondeu! Fecha o ponto.
                _aguardando_resposta.remove(str(member.id))
                
                ponto_aberto = db.get_ponto_aberto(str(member.id))
                if ponto_aberto:
                    # Fecha o ponto
                    entrada = datetime.fromisoformat(ponto_aberto['entrada'])
                    saida = (datetime.utcnow() - timedelta(hours=3))
                    duracao = int((saida - entrada).total_seconds())
                    
                    db.fechar_ponto(ponto_aberto['id'], saida.isoformat(), duracao)
                    await gerenciar_cargos_ponto(member, False)
                    
                    # Edita a msg da DM
                    embed_timeout = discord.Embed(title="❌ Tempo Esgotado", description="Seu ponto foi fechado automaticamente por inatividade.", color=COR_ERRO)
                    try: await msg.edit(embed=embed_timeout, view=None)
                    except: pass
                    
                    # Avisa nos logs do bate-ponto
                    canal_log = self.bot.get_channel(CANAL_LOG_PONTO_ID)
                    if canal_log:
                        data_entrada = entrada.strftime("%d/%m/%Y às %H:%M:%S")
                        data_saida = saida.strftime("%d/%m/%Y às %H:%M:%S")
                        duracao_formatada = formatar_duracao(duracao)
                        
                        embed_log = discord.Embed(
                            title="🔴  Ponto Fechado (Auditoria Automática)",
                            description=f"**Motivo:** Não respondeu à DM no tempo limite ({limite_resp} min).\n─────────────────────────────",
                            color=0xE74C3C
                        )
                        embed_log.add_field(name="👤  Membro", value=f"{member.mention}\n`{member.display_name}`", inline=True)
                        embed_log.add_field(name="⏰  Entrada", value=f"```{data_entrada}```", inline=True)
                        embed_log.add_field(name="⏰  Saída", value=f"```{data_saida}```", inline=True)
                        embed_log.add_field(name="⏱️  Tempo de Serviço", value=f"```{duracao_formatada}```", inline=False)
                        embed_log.add_field(name="🏷️  Cargo", value=f"```🔴 Fora de Serviço```", inline=True)
                        embed_log.add_field(name="📊  Status", value="```🔴 FORA DE SERVIÇO```", inline=True)
                        embed_log.set_thumbnail(url=member.display_avatar.url)
                        embed_log.set_footer(text="⚔️ Sistema de Bate-Ponto • Log de Saída (Auditoria)")
                        embed_log.timestamp = datetime.utcnow()
                        await canal_log.send(embed=embed_log)
        except (discord.Forbidden, discord.HTTPException):
            # Não conseguiu mandar DM. Remove do controle e fecha o ponto se necessário (opcional)
            if str(member.id) in _aguardando_resposta:
                _aguardando_resposta.remove(str(member.id))

    # ─── COMANDOS DE AUDITORIA ──────────────────────────────────────────────────
    @app_commands.command(name="config_auditoria", description="⚙️ Configura a varredura automática de voz do Bate-Ponto.")
    @app_commands.describe(ativar="Ativar ou desativar o sistema automático", minutos_fora="Minutos fora de call para ativar", minutos_resposta="Minutos para responder DM")
    async def config_auditoria(self, interaction: discord.Interaction, ativar: bool, minutos_fora: int = 60, minutos_resposta: int = 15):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        
        db.set_config("auditoria_ponto_ativa", "1" if ativar else "0")
        db.set_config("auditoria_tempo_fora", str(minutos_fora))
        db.set_config("auditoria_tempo_resposta", str(minutos_resposta))
        
        status = "🟢 Ativado" if ativar else "🔴 Desativado"
        embed = discord.Embed(title="⚙️ Configuração de Auditoria de Voz", description=f"O sistema de varredura automática de voz foi atualizado.", color=COR_SUCESSO)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Limite Fora de Call", value=f"{minutos_fora} min", inline=True)
        embed.add_field(name="Tempo de Resposta", value=f"{minutos_resposta} min", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="varredura_ponto", description="🔍 Força uma auditoria de voz agora com todos de ponto aberto.")
    async def varredura_ponto(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        await interaction.response.defer()
        
        cargo_membro = interaction.guild.get_role(CARGO_PONTO_ID)
        notificados = 0
        
        if cargo_membro:
            for member in cargo_membro.members:
                if str(member.id) in _aguardando_resposta:
                    continue
                ponto_aberto = db.get_ponto_aberto(str(member.id))
                if ponto_aberto and not (member.voice and member.voice.channel):
                    # Ponto aberto mas fora da call
                    _aguardando_resposta.add(str(member.id))
                    self.bot.loop.create_task(self.enviar_auditoria_dm(member, instantaneo=True))
                    notificados += 1

        embed = discord.Embed(title="🔍 Varredura Concluída", description=f"Foram identificados e notificados **{notificados}** membros que estão com ponto aberto fora da call.", color=COR_AVISO)
        await interaction.followup.send(embed=embed)
        
        canal_log = self.bot.get_channel(CANAL_LOG_PONTO_ID)
        if canal_log:
            embed_log = embed.copy()
            embed_log.set_footer(text=f"Executado por {interaction.user.display_name}")
            await canal_log.send(embed=embed_log)

    # ─── /painel_ponto ─────────────────────────────────────────────────────────
    @app_commands.command(name="painel_ponto", description="Reenvia o painel fixo de bate-ponto no canal.")
    async def painel_ponto(self, interaction: discord.Interaction):
        """Força o reenvio do painel fixo (apaga o anterior)."""
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        if interaction.channel_id != CANAL_BATER_PONTO_ID:
            embed = discord.Embed(title="⚠️  Canal Incorreto", description=f"Use em <#{CANAL_BATER_PONTO_ID}>.", color=COR_AVISO)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Tenta apagar o painel anterior
        msg_id_antigo = db.get_config("painel_ponto_msg_id")
        if msg_id_antigo:
            try:
                msg_antiga = await interaction.channel.fetch_message(int(msg_id_antigo))
                await msg_antiga.delete()
            except Exception:
                pass

        # Envia novo painel
        await interaction.response.send_message("✅ Painel reenviado!", ephemeral=True, delete_after=3)
        msg = await interaction.channel.send(embed=self._criar_embed_painel(), view=BatePontoView(self.bot))
        db.set_config("painel_ponto_msg_id", str(msg.id))


    # ─── /historico_ponto ─────────────────────────────────────────────────────
    @app_commands.command(name="historico_ponto", description="Veja o histórico de ponto de um membro (liderança).")
    @app_commands.describe(membro="Membro para consultar o histórico")
    async def historico_ponto(self, interaction: discord.Interaction, membro: discord.Member):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        registros = db.get_historico_ponto(str(membro.id), limite=15)
        if not registros:
            embed = discord.Embed(title=f"📊  Histórico │ {membro.display_name}", description="Este membro **não possui** registros.", color=COR_INFO)
            embed.set_thumbnail(url=membro.display_avatar.url)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(title=f"📊  Histórico de Ponto │ {membro.display_name}", description="─────────────────────────────\n", color=COR_PRINCIPAL)
        embed.set_thumbnail(url=membro.display_avatar.url)
        tempo_total = 0

        for i, reg in enumerate(registros, 1):
            entrada_fmt = datetime.fromisoformat(reg['entrada']).strftime("%d/%m às %H:%M")
            if reg['saida']:
                saida_fmt = datetime.fromisoformat(reg['saida']).strftime("%d/%m às %H:%M")
                duracao_fmt = formatar_duracao(reg['duracao_segundos'] or 0)
                tempo_total += reg['duracao_segundos'] or 0
                status = "🔴 Fechado"
            else:
                saida_fmt, duracao_fmt, status = "—", "⏳ Em andamento", "🟢 Aberto"
            embed.add_field(name=f"#{i} │ {status}", value=f"📥 `{entrada_fmt}` → 📤 `{saida_fmt}`\n⏱️ **{duracao_fmt}**", inline=False)

        embed.add_field(name="─────────────────────────────", value=f"⏱️ **Tempo Total:** `{formatar_duracao(tempo_total)}`", inline=False)
        embed.set_footer(text="⚔️ Sistema de Bate-Ponto • Consulta")
        embed.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ─── /ranking_ponto ───────────────────────────────────────────────────────
    @app_commands.command(name="ranking_ponto", description="Ranking de horas de serviço dos membros.")
    async def ranking_ponto(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        ranking = db.get_ranking_ponto(limite=15)
        if not ranking:
            embed = discord.Embed(title="📊  Ranking de Ponto", description="Nenhum registro encontrado.", color=COR_INFO)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(title="🏆  Ranking de Horas de Serviço", description="─────────────────────────────\n", color=0xFFD700)
        medalhas = ["🥇", "🥈", "🥉"]

        for i, reg in enumerate(ranking):
            medalha = medalhas[i] if i < 3 else f"**{i + 1}.**"
            tempo_fmt = formatar_duracao(reg['tempo_total'] or 0)
            member = interaction.guild.get_member(int(reg['discord_id']))
            nome = member.display_name if member else f"ID: {reg['discord_id']}"
            embed.add_field(name=f"{medalha} {nome}", value=f"⏱️ `{tempo_fmt}` │ 📋 `{reg['total_pontos']} registros`", inline=False)

        embed.set_footer(text="⚔️ Sistema de Bate-Ponto • Ranking")
        embed.timestamp = datetime.utcnow()
        await interaction.response.send_message(embed=embed)


    # ─── /parar_ponto_admin ───────────────────────────────────────────────────
    @app_commands.command(name="parar_ponto_admin", description="🔴 Remove um membro do bate-ponto ativamente. [Liderança]")
    @app_commands.describe(membro="Membro que será retirado do ponto", motivo="Motivo da retirada")
    async def parar_ponto_admin(self, interaction: discord.Interaction, membro: discord.Member, motivo: str):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
            
        ponto_aberto = db.get_ponto_aberto(str(membro.id))
        if not ponto_aberto:
            embed = discord.Embed(
                title="⚠️  Nenhum Ponto Aberto",
                description=f"O membro {membro.mention} **não tem nenhum ponto** aberto no momento.",
                color=COR_AVISO
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        agora = (datetime.utcnow() - timedelta(hours=3))
        entrada_dt = datetime.fromisoformat(ponto_aberto['entrada'])
        segundos_total = int((agora - entrada_dt).total_seconds())
        duracao_formatada = formatar_duracao(segundos_total)
        data_saida = agora.strftime("%d/%m/%Y às %H:%M:%S")
        data_entrada = entrada_dt.strftime("%d/%m/%Y às %H:%M:%S")

        db.fechar_ponto(ponto_aberto['id'], agora.isoformat(), segundos_total)

        # Gerencia cargos
        await gerenciar_cargos_ponto(membro, batendo=False)

        # Resposta ao admin
        embed_admin = discord.Embed(
            title="🔴  Ponto Encerrado por Admin",
            description=(
                f"O ponto de {membro.mention} foi **fechado**.\n\n"
                f"⏱️ **Tempo de Serviço:** `{duracao_formatada}`\n"
                f"📝 **Motivo:** {motivo}"
            ),
            color=COR_ERRO
        )
        await interaction.response.send_message(embed=embed_admin)

        # DM ao membro
        try:
            dm = discord.Embed(
                title="🔴  Seu Ponto foi Encerrado",
                description=(
                    f"Seu ponto no servidor **{interaction.guild.name}** foi encerrado por um administrador.\n\n"
                    f"⏰ **Entrada:** `{data_entrada}`\n"
                    f"⏰ **Saída:** `{data_saida}`\n"
                    f"⏱️ **Tempo:** `{duracao_formatada}`\n\n"
                    f"📝 **Motivo:** {motivo}\n"
                    f"👮 **Por:** {interaction.user.display_name}"
                ),
                color=COR_ERRO, timestamp=(datetime.utcnow() - timedelta(hours=3))
            )
            await membro.send(embed=dm)
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Log no canal do bate-ponto
        canal_log = self.bot.get_channel(CANAL_LOG_PONTO_ID)
        if canal_log:
            embed_log = discord.Embed(
                title="🔴  Ponto Fechado (Admin)",
                description=f"**Motivo:** {motivo}\n**Encerrado por:** {interaction.user.mention}\n─────────────────────────────",
                color=0xE74C3C
            )
            embed_log.add_field(name="👤  Membro", value=f"{membro.mention}\n`{membro.display_name}`", inline=True)
            embed_log.add_field(name="⏰  Entrada", value=f"```{data_entrada}```", inline=True)
            embed_log.add_field(name="⏰  Saída", value=f"```{data_saida}```", inline=True)
            embed_log.add_field(name="⏱️  Tempo de Serviço", value=f"```{duracao_formatada}```", inline=False)
            embed_log.add_field(name="🏷️  Cargo", value=f"```🔴 Fora de Serviço```", inline=True)
            embed_log.add_field(name="📊  Status", value="```🔴 FORA DE SERVIÇO```", inline=True)
            embed_log.set_thumbnail(url=membro.display_avatar.url)
            embed_log.set_footer(text="⚔️ Sistema de Bate-Ponto • Log de Saída (Admin)")
            embed_log.timestamp = datetime.utcnow()
            await canal_log.send(embed=embed_log)

    # ─── /abrir_ponto_admin ────────────────────────────────────────────────────
    @app_commands.command(name="abrir_ponto_admin", description="✅ Abre o bate-ponto de um membro manualmente. [Liderança]")
    @app_commands.describe(membro="Membro que terá o ponto aberto", motivo="Motivo da abertura")
    async def abrir_ponto_admin(self, interaction: discord.Interaction, membro: discord.Member, motivo: str):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        await interaction.response.defer()

        ponto_aberto = db.get_ponto_aberto(str(membro.id))
        if ponto_aberto:
            embed = utils.embed_erro("Já Aberto", f"O membro {membro.mention} já está com o ponto **ABERTO**.")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        agora = (datetime.utcnow() - timedelta(hours=3))
        data_formatada = agora.strftime("%d/%m/%Y às %H:%M:%S")
        db.registrar_ponto_entrada(str(membro.id), agora.isoformat())

        # Gerencia cargos
        await gerenciar_cargos_ponto(membro, batendo=True)

        # Resposta no canal
        embed = discord.Embed(
            title="✅  Ponto Aberto (Admin)",
            description=f"O ponto de {membro.mention} foi aberto manualmente por {interaction.user.mention}.",
            color=COR_SUCESSO, timestamp=(datetime.utcnow() - timedelta(hours=3))
        )
        embed.add_field(name="⏰ Entrada", value=f"`{data_formatada}`", inline=True)
        embed.add_field(name="📝 Motivo", value=f"`{motivo}`", inline=True)
        await interaction.followup.send(embed=embed)

        # DM ao membro
        try:
            dm = discord.Embed(
                title="✅  Seu Ponto foi Aberto",
                description=(
                    f"Seu ponto no servidor **{interaction.guild.name}** foi aberto por um administrador.\n\n"
                    f"⏰ **Entrada:** `{data_formatada}`\n"
                    f"📝 **Motivo:** {motivo}\n"
                    f"👮 **Por:** {interaction.user.display_name}"
                ),
                color=COR_SUCESSO, timestamp=(datetime.utcnow() - timedelta(hours=3))
            )
            await membro.send(embed=dm)
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Log no canal do bate-ponto
        canal_log = self.bot.get_channel(CANAL_LOG_PONTO_ID)
        if canal_log:
            embed_log = discord.Embed(
                title="✅  Ponto Aberto (Admin)",
                description=f"**Motivo:** {motivo}\n**Aberto por:** {interaction.user.mention}\n─────────────────────────────",
                color=COR_SUCESSO
            )
            embed_log.add_field(name="👤  Membro", value=f"{membro.mention}\n`{membro.display_name}`", inline=True)
            embed_log.add_field(name="⏰  Entrada", value=f"```{data_formatada}```", inline=True)
            embed_log.add_field(name="🏷️  Cargo", value=f"```🟢 Em Serviço```", inline=True)
            embed_log.set_thumbnail(url=membro.display_avatar.url)
            embed_log.set_footer(text="⚔️ Sistema de Bate-Ponto • Log de Entrada (Admin)")
            embed_log.timestamp = datetime.utcnow()
            await canal_log.send(embed=embed_log)

    # ─── /verificar_call ───────────────────────────────────────────────────────
    @app_commands.command(name="verificar_call", description="🔍 Verifica o status do bate-ponto dos membros na sua call atual. [Liderança]")
    async def verificar_call(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
            
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("❌ Você precisa estar em um canal de voz para usar este comando.", ephemeral=True)
            
        canal_voz = interaction.user.voice.channel
        membros = canal_voz.members
        
        if len(membros) <= 1 and membros[0].id == interaction.user.id:
            return await interaction.response.send_message("❌ Só tem você no canal de voz.", ephemeral=True)
            
        embed = discord.Embed(
            title=f"🔍 Auditoria de Call: {canal_voz.name}",
            description="Status do bate-ponto dos membros nesta call:",
            color=COR_INFO, timestamp=datetime.utcnow()
        )
        
        texto = ""
        for m in membros:
            if m.bot: continue
            
            ponto_aberto = db.get_ponto_aberto(str(m.id))
            if ponto_aberto:
                entrada_dt = datetime.fromisoformat(ponto_aberto['entrada'])
                segundos = int(((datetime.utcnow() - timedelta(hours=3)) - entrada_dt).total_seconds())
                duracao = formatar_duracao(segundos)
                texto += f"🟢 {m.mention} - **Ponto Aberto** (`{duracao}`)\n"
            else:
                texto += f"🔴 {m.mention} - Ponto Fechado\n"
                
        if not texto:
            texto = "Nenhum membro válido na call."
            
        embed.add_field(name="Membros", value=texto, inline=False)
        embed.set_footer(text="⚔️ Sistema de Bate-Ponto • Varredura de Call")
        await interaction.response.send_message(embed=embed)
        
        canal_log = self.bot.get_channel(CANAL_LOG_PONTO_ID)
        if canal_log:
            embed_log = embed.copy()
            embed_log.set_footer(text=f"Executado por {interaction.user.display_name}")
            await canal_log.send(embed=embed_log)


async def setup(bot: commands.Bot):
    """Registra o Cog no bot."""
    await bot.add_cog(BatePonto(bot))
