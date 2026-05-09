"""
commands/metas.py - Sistema de Metas (C4 e Plásticos)
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

import database as db
import checks
import utils
from config import (
    COR_PRINCIPAL, COR_ERRO, COR_SUCESSO, COR_AVISO,
    CARGO_BATEU_META_ID, CARGO_NAO_BATEU_META_ID,
    CANAL_REGISTRO_META_ID, CARGO_META_OBRIGATORIO_ID,
    CANAL_PATENTES_ID,
)

TIPOS_ENTREGA = [
    app_commands.Choice(name="💣 C4", value="c4"),
    app_commands.Choice(name="🧱 Plásticos", value="plasticos"),
    app_commands.Choice(name="🦺 Colete", value="colete"),
    app_commands.Choice(name="🪢 Corda", value="corda"),
    app_commands.Choice(name="🎭 Capuz", value="capuz"),
    app_commands.Choice(name="🟢 Chave Verde", value="chave_verde"),
    app_commands.Choice(name="🔴 Chave Vermelha", value="chave_vermelha"),
    app_commands.Choice(name="🟡 Chave Amarela", value="chave_amarela"),
]

INFO_TIPOS = {
    "c4": ("C4", "💣"),
    "plasticos": ("Plásticos", "🧱"),
    "colete": ("Colete", "🦺"),
    "corda": ("Corda", "🪢"),
    "capuz": ("Capuz", "🎭"),
    "chave_verde": ("Chave Verde", "🟢"),
    "chave_vermelha": ("Chave Vermelha", "🔴"),
    "chave_amarela": ("Chave Amarela", "🟡"),
}


def _bateu_meta(totais: dict) -> bool:
    metas_ativas = db.get_metas_ativas()
    # Se não há metas ativas configuradas, ninguém bate
    if not metas_ativas:
        return False
    modo = db.get_modo_meta()
    
    if modo == "ou":
        for tipo, quantidade_necessaria in metas_ativas.items():
            if totais.get(tipo, 0) >= quantidade_necessaria:
                return True
        return False
    else:
        for tipo, quantidade_necessaria in metas_ativas.items():
            if totais.get(tipo, 0) < quantidade_necessaria:
                return False
        return True


def _barra(atual: int, meta: int) -> str:
    pct = min(100, int((atual / meta) * 100)) if meta > 0 else 0
    b = int(pct / 10)
    return f"`[{'█' * b}{'░' * (10 - b)}]` {pct}%"


def _tipo_info(tipo_val: str):
    nome, emoji = INFO_TIPOS.get(tipo_val, (tipo_val.title(), "📦"))
    metas_ativas = db.get_metas_ativas()
    meta_val = metas_ativas.get(tipo_val, 0)
    return nome, emoji, meta_val


class Metas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_membros_meta(self, guild: discord.Guild):
        """Retorna membros que têm o cargo obrigatório E estão registrados no banco."""
        cargo = guild.get_role(CARGO_META_OBRIGATORIO_ID)
        if not cargo:
            return []
        resultado = []
        for membro in cargo.members:
            if membro.bot:
                continue
            dados = db.get_membro(str(membro.id))
            if dados:
                resultado.append((membro, dados))
        return resultado

    # ── /registrar_meta ──────────────────────────────────────────────────
    @app_commands.command(name="registrar_meta", description="📦 Registra entrega de C4 ou Plásticos.")
    @app_commands.describe(membro="Membro", tipo="Tipo", quantidade="Quantidade")
    @app_commands.choices(tipo=TIPOS_ENTREGA)
    async def registrar_meta(self, interaction: discord.Interaction, membro: discord.Member,
                             tipo: app_commands.Choice[str], quantidade: int):
        if not checks.is_farm_ou_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        if quantidade <= 0:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Valor Inválido", "A quantidade deve ser maior que zero."), ephemeral=True)
        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Não Encontrado", f"{membro.mention} não está registrado."), ephemeral=True)

        db.registrar_entrega_meta(str(membro.id), tipo.value, quantidade, str(interaction.user.id), utils.data_agora())
        totais = db.get_total_por_tipo(str(membro.id))
        bateu = _bateu_meta(totais)
        nome, emoji, meta_val = _tipo_info(tipo.value)
        pct = min(100, int((totais.get(tipo.value, 0) / meta_val) * 100)) if meta_val > 0 else 0
        barra_visual = f"[ {'█' * int(pct / 10)}{'░' * (10 - int(pct / 10))} ]"

        embed = discord.Embed(
            title=f"{emoji} Entrega de {nome} Registrada",
            color=COR_SUCESSO if bateu else COR_AVISO,
            timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=membro.display_avatar.url)

        # Linha 1 — Membro | Entregou | Total do Ciclo
        try:
            id_jogo = dados['id_jogo'] or ''
        except (KeyError, IndexError):
            id_jogo = ''
        embed.add_field(name="👤 Membro", value=f"{membro.mention}\n`{id_jogo}`" if id_jogo else membro.mention, inline=True)
        embed.add_field(name="➕ Entregou", value=f"`{quantidade:,}`  {nome}", inline=True)
        embed.add_field(name=f"{emoji} {nome} do Ciclo", value=f"`{totais.get(tipo.value, 0):,}`", inline=True)

        # Linha 2 — Meta | Progresso | Barra
        embed.add_field(name="🎯 Meta", value=f"`{meta_val:,}`" if meta_val > 0 else "`Desativada`", inline=True)
        embed.add_field(name="📈 Progresso", value=f"`{pct}%`", inline=True)
        embed.add_field(name="📊 Barra", value=f"`{barra_visual}`", inline=True)

        # Linha 3 — Por
        embed.add_field(name="👮 Registrado por", value=interaction.user.mention, inline=False)

        # Status
        metas_ativas = db.get_metas_ativas()
        modo = db.get_modo_meta()
        
        if bateu:
            via = []
            for t_ativo, qtd_ativa in metas_ativas.items():
                if totais.get(t_ativo, 0) >= qtd_ativa:
                    tn, _, _ = _tipo_info(t_ativo)
                    via.append(tn)
            if not via:
                via = ["Desconhecido"]
            embed.add_field(name="🏁 Status", value=f"✅ **META BATIDA! ({' + '.join(via)})**", inline=False)
        else:
            if modo == "ou":
                if meta_val > 0:
                    falta = max(0, meta_val - totais.get(tipo.value, 0))
                    embed.add_field(name="🏁 Status", value=f"❌ **Faltam {falta:,}  {nome}**", inline=False)
                else:
                    embed.add_field(name="🏁 Status", value=f"⚠️ **Meta inativa para {nome}**", inline=False)
            else:
                faltam_lista = []
                for t_ativo, qtd_ativa in metas_ativas.items():
                    qtd_tem = totais.get(t_ativo, 0)
                    if qtd_tem < qtd_ativa:
                        tn, _, _ = _tipo_info(t_ativo)
                        faltam_lista.append(f"{qtd_ativa - qtd_tem:,} {tn}")
                if faltam_lista:
                    embed.add_field(name="🏁 Status", value=f"❌ **Falta: {', '.join(faltam_lista)}**", inline=False)
                else:
                    embed.add_field(name="🏁 Status", value=f"⚠️ **Meta inativa**", inline=False)

        embed.set_footer(text=f"⚔️ {interaction.guild.name} • Sistema de {nome}")
        await interaction.response.send_message(embed=embed)

        # Cargo automático
        if bateu:
            try:
                r_ok = interaction.guild.get_role(CARGO_BATEU_META_ID)
                r_no = interaction.guild.get_role(CARGO_NAO_BATEU_META_ID)
                if r_ok and r_ok not in membro.roles: await membro.add_roles(r_ok)
                if r_no and r_no in membro.roles: await membro.remove_roles(r_no)
            except discord.Forbidden:
                pass

        # Log no canal de registro
        canal = self.bot.get_channel(CANAL_REGISTRO_META_ID)
        if canal:
            le = discord.Embed(
                title=f"{emoji} Entrega de {nome} Registrada",
                color=COR_SUCESSO if bateu else COR_AVISO,
                timestamp=datetime.now(timezone.utc))
            le.set_thumbnail(url=membro.display_avatar.url)
            le.add_field(name="👤 Membro", value=f"{membro.mention}", inline=True)
            le.add_field(name="➕ Entregou", value=f"`{quantidade:,}`  {nome}", inline=True)
            le.add_field(name=f"{emoji} Ciclo", value=f"`{totais.get(tipo.value, 0):,}/{meta_val:,}`", inline=True)
            le.add_field(name="📈 Progresso", value=f"`{pct}%`", inline=True)
            le.add_field(name="👮 Por", value=interaction.user.mention, inline=True)
            le.add_field(name="📅 Data", value=f"`{utils.data_agora()}`", inline=True)
            if bateu:
                le.add_field(name="🏁 Status", value=f"✅ **META BATIDA! ({' + '.join(via)})**", inline=False)
            else:
                if modo == "ou":
                    if meta_val > 0:
                        falta = max(0, meta_val - totais.get(tipo.value, 0))
                        le.add_field(name="🏁 Status", value=f"❌ **Faltam {falta:,}  {nome}**", inline=False)
                    else:
                        le.add_field(name="🏁 Status", value=f"⚠️ **Meta inativa**", inline=False)
                else:
                    if faltam_lista:
                        le.add_field(name="🏁 Status", value=f"❌ **Falta: {', '.join(faltam_lista)}**", inline=False)
                    else:
                        le.add_field(name="🏁 Status", value=f"⚠️ **Meta inativa**", inline=False)
            le.set_footer(text=f"⚔️ {interaction.guild.name} • Sistema de {nome}")
            await canal.send(embed=le)

    # ── /editar_meta ─────────────────────────────────────────────────────
    @app_commands.command(name="editar_meta", description="✏️ Edita o total de entregas de um membro. [Liderança]")
    @app_commands.describe(membro="Membro", tipo="Tipo", nova_quantidade="Nova quantidade total")
    @app_commands.choices(tipo=TIPOS_ENTREGA)
    async def editar_meta(self, interaction: discord.Interaction, membro: discord.Member,
                          tipo: app_commands.Choice[str], nova_quantidade: int):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        if nova_quantidade < 0:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Valor Inválido", "Não pode ser negativo."), ephemeral=True)
        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Não Encontrado", f"{membro.mention} não está registrado."), ephemeral=True)

        antes = db.get_total_por_tipo(str(membro.id)).get(tipo.value, 0)
        db.editar_entrega_meta(str(membro.id), tipo.value, nova_quantidade, str(interaction.user.id), utils.data_agora())
        totais = db.get_total_por_tipo(str(membro.id))
        bateu = _bateu_meta(totais)
        nome, emoji, meta_val = _tipo_info(tipo.value)

        embed = discord.Embed(title=f"✏️  Entrega Editada — {nome}", color=COR_AVISO,
                              timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name=f"{emoji} Antes", value=f"`{antes:,}`", inline=True)
        embed.add_field(name=f"{emoji} Agora", value=f"`{nova_quantidade:,}`", inline=True)
        embed.add_field(name="📊 Progresso", value=_barra(nova_quantidade, meta_val), inline=False)
        embed.add_field(name="🏁 Status", value="✅ **META BATIDA!**" if bateu else "⏳ **Pendente**", inline=True)
        embed.add_field(name="👮 Por", value=interaction.user.mention, inline=True)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.response.send_message(embed=embed)

        # Atualiza cargos
        try:
            r_ok = interaction.guild.get_role(CARGO_BATEU_META_ID)
            r_no = interaction.guild.get_role(CARGO_NAO_BATEU_META_ID)
            if bateu:
                if r_ok and r_ok not in membro.roles: await membro.add_roles(r_ok)
                if r_no and r_no in membro.roles: await membro.remove_roles(r_no)
            else:
                if r_no and r_no not in membro.roles: await membro.add_roles(r_no)
                if r_ok and r_ok in membro.roles: await membro.remove_roles(r_ok)
        except discord.Forbidden:
            pass

        canal = self.bot.get_channel(CANAL_REGISTRO_META_ID)
        if canal:
            le = discord.Embed(title="✏️ Entrega Editada",
                description=f"**Membro:** {membro.mention}\n**Tipo:** {emoji} {nome}\n"
                            f"**Antes:** `{antes:,}` → **Agora:** `{nova_quantidade:,}`\n"
                            f"**Por:** {interaction.user.mention}",
                color=COR_AVISO, timestamp=datetime.now(timezone.utc))
            le.set_footer(text="⚔️ Facção Bot • Registro de Entregas")
            await canal.send(embed=le)

    # ── /meta ────────────────────────────────────────────────────────────
    @app_commands.command(name="meta", description="📊 Mostra quem bateu e quem não bateu a meta.")
    async def meta(self, interaction: discord.Interaction):
        await interaction.response.defer()
        membros = self._get_membros_meta(interaction.guild)
        if not membros:
            return await interaction.followup.send(
                embed=utils.embed_erro("Sem Membros", "Nenhum membro com o cargo obrigatório encontrado."))

        metas_ativas = db.get_metas_ativas()
        bateram, nao_bateram = [], []
        
        for obj, dados in membros:
            totais = db.get_total_por_tipo(str(obj.id))
            
            # Monta info dos itens ativos
            info_itens = []
            for t_ativo, qtd_ativa in metas_ativas.items():
                nome, emoji, _ = _tipo_info(t_ativo)
                qtd_entregue = totais.get(t_ativo, 0)
                info_itens.append(f"{emoji}`{qtd_entregue:,}/{qtd_ativa}`")
            info_str = " ".join(info_itens)
            
            if _bateu_meta(totais):
                via = []
                for t_ativo, qtd_ativa in metas_ativas.items():
                    if totais.get(t_ativo, 0) >= qtd_ativa:
                        nome, _, _ = _tipo_info(t_ativo)
                        via.append(nome)
                if not via: via = ["?"]
                bateram.append(f"✅ {obj.mention} — {info_str} *(via {' + '.join(via)})*")
            else:
                if not info_str: info_str = "*Sem metas ativas*"
                nao_bateram.append(f"❌ {obj.mention} — {info_str}")

        desc_meta = "\n".join([f"**{_tipo_info(k)[0]}:** `{v}` un." for k, v in metas_ativas.items()])
        if not desc_meta: desc_meta = "*Nenhuma meta ativa no momento.*"

        embed = discord.Embed(
            title="📊  Painel de Metas",
            description=f"**Cargo:** <@&{CARGO_META_OBRIGATORIO_ID}>\n"
                        f"{desc_meta}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=COR_PRINCIPAL, timestamp=datetime.now(timezone.utc))

        embed.add_field(name=f"✅ Bateram a Meta ({len(bateram)})",
                        value="\n".join(bateram[:20]) or "*Nenhum*", inline=False)
        embed.add_field(name=f"❌ Não Bateram ({len(nao_bateram)})",
                        value="\n".join(nao_bateram[:20]) or "*Todos bateram! 🎉*", inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.followup.send(embed=embed)

    # ── /verificar_metas ─────────────────────────────────────────────────
    @app_commands.command(name="verificar_metas", description="🔍 Verifica todos e atribui cargos. [Liderança]")
    async def verificar_metas(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        await interaction.response.defer()

        membros = self._get_membros_meta(interaction.guild)
        r_ok = interaction.guild.get_role(CARGO_BATEU_META_ID)
        r_no = interaction.guild.get_role(CARGO_NAO_BATEU_META_ID)
        ok_count, fail_count = 0, 0

        for obj, dados in membros:
            totais = db.get_total_por_tipo(str(obj.id))
            try:
                if _bateu_meta(totais):
                    ok_count += 1
                    if r_ok and r_ok not in obj.roles: await obj.add_roles(r_ok)
                    if r_no and r_no in obj.roles: await obj.remove_roles(r_no)
                else:
                    fail_count += 1
                    if r_no and r_no not in obj.roles: await obj.add_roles(r_no)
                    if r_ok and r_ok in obj.roles: await obj.remove_roles(r_ok)
            except discord.Forbidden:
                pass

        embed = discord.Embed(
            title="🔍  Verificação de Metas Concluída",
            color=COR_SUCESSO if fail_count == 0 else COR_AVISO,
            timestamp=datetime.now(timezone.utc))
        embed.add_field(name="👥 Total", value=f"`{ok_count + fail_count}`", inline=True)
        embed.add_field(name="✅ Bateram", value=f"`{ok_count}`", inline=True)
        embed.add_field(name="❌ Não Bateram", value=f"`{fail_count}`", inline=True)
        embed.add_field(name="🎭 Cargos", value="Cargos atualizados automaticamente!", inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.followup.send(embed=embed)

    # ── /parabenizar_metas ───────────────────────────────────────────────
    @app_commands.command(name="parabenizar_metas", description="🎉 Parabeniza todos que bateram a meta. [Liderança]")
    async def parabenizar_metas(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        await interaction.response.defer()

        membros = self._get_membros_meta(interaction.guild)
        lista = []
        for obj, dados in membros:
            totais = db.get_total_por_tipo(str(obj.id))
            if _bateu_meta(totais):
                lista.append(obj.mention)

        if not lista:
            return await interaction.followup.send(
                embed=utils.embed_erro("Ninguém", "Nenhum membro bateu a meta ainda."))

        embed = discord.Embed(
            title="🎉🏆  PARABÉNS AOS GUERREIROS!  🏆🎉",
            description=(
                f"Os seguintes membros **bateram a meta** e mostraram comprometimento!\n\n"
                f"{'  '.join(lista)}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔥 **Vocês são o orgulho da facção!** 🔥\n"
                f"Continuem assim e a vitória será nossa! 💪⚔️"
            ),
            color=0xFFD700, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.followup.send(embed=embed)

    # ── /punir_inativos ──────────────────────────────────────────────────
    @app_commands.command(name="punir_inativos", description="🔨 Pune membros que não bateram a meta. [Liderança]")
    async def punir_inativos(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        await interaction.response.defer()

        membros = self._get_membros_meta(interaction.guild)
        punidos = []
        metas_ativas = db.get_metas_ativas()
        
        for obj, dados in membros:
            totais = db.get_total_por_tipo(str(obj.id))
            if not _bateu_meta(totais):
                db.aplicar_punicao(str(obj.id), "Não bateu a meta semanal", "meta_nao_batida",
                                   str(interaction.user.id), utils.data_agora())
                punidos.append(obj.mention)
                try:
                    info_itens = []
                    for t_ativo, qtd_ativa in metas_ativas.items():
                        nome, emoji, _ = _tipo_info(t_ativo)
                        qtd_entregue = totais.get(t_ativo, 0)
                        info_itens.append(f"**{nome}:** `{qtd_entregue:,}/{qtd_ativa}`")
                    info_str = "\n".join(info_itens)
                    
                    dm = discord.Embed(
                        title="⚠️ Punição — Meta Não Batida",
                        description=(f"Você **não bateu a meta** no servidor **{interaction.guild.name}**.\n\n"
                                     f"{info_str}\n\n"
                                     f"Uma punição foi registrada no seu histórico."),
                        color=COR_ERRO, timestamp=datetime.now(timezone.utc))
                    await obj.send(embed=dm)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        embed = discord.Embed(
            title="🔨  Punição de Inativos Aplicada",
            description=f"**{len(punidos)}** membro(s) punido(s) por não bater a meta.\n\n"
                        + ("\n".join(punidos[:25]) if punidos else "*Nenhum membro para punir.*"),
            color=COR_ERRO, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.followup.send(embed=embed)

    # ── /add_punicao ─────────────────────────────────────────────────────
    @app_commands.command(name="add_punicao", description="🔨 Adiciona punição manual a um membro. [Liderança]")
    @app_commands.describe(membro="Membro", motivo="Motivo da punição")
    async def add_punicao(self, interaction: discord.Interaction, membro: discord.Member, motivo: str):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        dados = db.get_membro(str(membro.id))
        if not dados:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Não Encontrado", f"{membro.mention} não registrado."), ephemeral=True)

        db.aplicar_punicao(str(membro.id), motivo, "manual", str(interaction.user.id), utils.data_agora())
        dados_att = db.get_membro(str(membro.id))

        embed = discord.Embed(title="🔨  Punição Adicionada", color=COR_ERRO,
                              timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name="🔨 Total", value=f"`{dados_att['punicoes']}`", inline=True)
        embed.add_field(name="👮 Por", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo", value=f"```{motivo}```", inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.response.send_message(embed=embed)

    # ── /remover_punicao ─────────────────────────────────────────────────
    @app_commands.command(name="remover_punicao", description="✅ Remove a última punição de um membro. [Liderança]")
    @app_commands.describe(membro="Membro")
    async def remover_punicao(self, interaction: discord.Interaction, membro: discord.Member):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        removeu = db.remover_ultima_punicao(str(membro.id))
        if not removeu:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Sem Punições", f"{membro.mention} não possui punições."), ephemeral=True)

        dados = db.get_membro(str(membro.id))
        embed = discord.Embed(title="✅  Punição Removida", color=COR_SUCESSO,
                              timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name="🔨 Restantes", value=f"`{dados['punicoes'] if dados else 0}`", inline=True)
        embed.add_field(name="👮 Por", value=interaction.user.mention, inline=True)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.response.send_message(embed=embed)

    # ── /ver_punicoes ────────────────────────────────────────────────────
    @app_commands.command(name="ver_punicoes", description="📋 Mostra punições de um membro. [Liderança]")
    @app_commands.describe(membro="Membro")
    async def ver_punicoes(self, interaction: discord.Interaction, membro: discord.Member):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        lista = db.get_punicoes_lista(str(membro.id))
        dados = db.get_membro(str(membro.id))

        embed = discord.Embed(
            title=f"📋  Punições — {membro.display_name}",
            color=COR_ERRO if lista else COR_SUCESSO,
            timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="🔨 Total", value=f"`{dados['punicoes'] if dados else 0}`", inline=True)

        if lista:
            linhas = []
            for i, p in enumerate(lista[:10], 1):
                linhas.append(f"`{i}.` {p['motivo'] or 'Sem motivo'} — `{p['data']}`")
            embed.add_field(name="📜 Histórico", value="\n".join(linhas), inline=False)
        else:
            embed.add_field(name="📜 Histórico", value="*Nenhuma punição registrada.*", inline=False)

        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.response.send_message(embed=embed)

    # ── /resetar_metas ───────────────────────────────────────────────────
    @app_commands.command(name="resetar_metas", description="🔄 Reseta todas as entregas (novo período). [Liderança]")
    async def resetar_metas(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        db.resetar_entregas_meta()
        embed = discord.Embed(
            title="🔄  Metas Resetadas",
            description="Todas as entregas foram zeradas para um novo período!\n"
                        "Os membros precisam entregar novamente.",
            color=COR_AVISO, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.response.send_message(embed=embed)

    # ── /v — Verificar e salvar todos com o cargo ────────────────────────
    @app_commands.command(
        name="v",
        description="🔄 Sincroniza o banco com o Discord (adiciona quem tem cargo, remove quem não tem). [Liderança]"
    )
    async def v(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        cargo = guild.get_role(CARGO_META_OBRIGATORIO_ID)

        if not cargo:
            return await interaction.followup.send(
                embed=utils.embed_erro("Cargo Não Encontrado", f"O cargo `{CARGO_META_OBRIGATORIO_ID}` não existe.")
            )

        membros_db = db.get_todos_membros(status="ativo")
        db_ids = {m["discord_id"]: m for m in membros_db}

        removidos = []
        adicionados = []
        ja_registrados = 0

        # 1. Verifica no DB: quem está no banco, mas não tem o cargo no Discord
        for discord_id, dados in db_ids.items():
            membro = guild.get_member(int(discord_id))
            if not membro or cargo not in membro.roles:
                db.remover_membro(discord_id)
                nome = membro.display_name if membro else dados["nome"]
                removidos.append(nome)

        # 2. Verifica no Discord: quem tem o cargo, mas não está no DB
        for membro in cargo.members:
            if membro.bot:
                continue
            if str(membro.id) not in db_ids:
                db.registrar_membro(
                    discord_id=str(membro.id),
                    nome=membro.display_name,
                    id_jogo="—",
                    cargo="Membro",
                    data_entrada=utils.data_agora()
                )
                adicionados.append(membro.display_name)
            else:
                ja_registrados += 1

        embed = discord.Embed(
            title="🔄  Sincronização do Banco Concluída",
            description=(
                f"A verificação do cargo <@&{CARGO_META_OBRIGATORIO_ID}> foi finalizada.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=COR_SUCESSO if not removidos else COR_AVISO,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

        # Adicionados
        if adicionados:
            texto_add = "\n".join(f"✅ `{n}`" for n in adicionados[:25])
            if len(adicionados) > 25:
                texto_add += f"\n*... e mais {len(adicionados) - 25}*"
            embed.add_field(name=f"🆕 Novos Registrados ({len(adicionados)})", value=texto_add, inline=False)

        # Removidos
        if removidos:
            texto_rem = "\n".join(f"❌ `{n}`" for n in removidos[:25])
            if len(removidos) > 25:
                texto_rem += f"\n*... e mais {len(removidos) - 25}*"
            embed.add_field(name=f"🚫 Removidos do DB ({len(removidos)})", value=texto_rem, inline=False)

        # Já registrados
        if not adicionados and not removidos:
            embed.add_field(name="ℹ️ Status", value="✨ **Tudo 100% sincronizado!**\nNenhum membro novo ou removido.", inline=False)
        else:
            embed.add_field(name="📋 Mantidos no DB", value=f"`{ja_registrados}` membros regulares", inline=False)

        embed.set_footer(text=f"Executado por {interaction.user.display_name} • Sistema de Sincronização")
        await interaction.followup.send(embed=embed)

    # ── /r — Remover cargo e avisar a facção ─────────────────────────────
    @app_commands.command(name="r", description="🚫 Remove o cargo de um membro e avisa toda a facção. [Liderança]")
    @app_commands.describe(membro="Membro que vai perder o cargo", motivo="Motivo da remoção")
    async def r(self, interaction: discord.Interaction, membro: discord.Member, motivo: str):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        cargo = interaction.guild.get_role(CARGO_META_OBRIGATORIO_ID)
        if not cargo:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Cargo Não Encontrado", f"O cargo `{CARGO_META_OBRIGATORIO_ID}` não existe."),
                ephemeral=True)

        if cargo not in membro.roles:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Sem Cargo", f"{membro.mention} não possui o cargo <@&{CARGO_META_OBRIGATORIO_ID}>."),
                ephemeral=True)

        # Remove o cargo
        try:
            await membro.remove_roles(cargo)
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Sem Permissão", "O bot não tem permissão para remover este cargo."),
                ephemeral=True)

        # Remove também cargos de meta se tiver
        r_ok = interaction.guild.get_role(CARGO_BATEU_META_ID)
        r_no = interaction.guild.get_role(CARGO_NAO_BATEU_META_ID)
        try:
            if r_ok and r_ok in membro.roles: await membro.remove_roles(r_ok)
            if r_no and r_no in membro.roles: await membro.remove_roles(r_no)
        except discord.Forbidden:
            pass

        # Atualiza status no banco
        db.remover_membro(str(membro.id))

        # Embed de confirmação
        embed = discord.Embed(
            title="🚫  Membro Removido da Facção",
            color=COR_ERRO, timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="👤 Membro", value=f"{membro.mention}\n`{membro.id}`", inline=True)
        embed.add_field(name="👮 Removido por", value=interaction.user.mention, inline=True)
        embed.add_field(name="📅 Data", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
        embed.add_field(name="📝 Motivo", value=f"```{motivo}```", inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.response.send_message(embed=embed)

        # Avisa todos que têm o cargo (toda a facção)
        canal = self.bot.get_channel(CANAL_REGISTRO_META_ID)
        if canal:
            aviso = discord.Embed(
                title="⚠️  Membro Removido da Facção",
                description=(
                    f"O membro **{membro.display_name}** ({membro.mention}) foi **removido** da facção.\n\n"
                    f"**Motivo:** ```{motivo}```\n"
                    f"**Removido por:** {interaction.user.mention}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=COR_ERRO, timestamp=datetime.now(timezone.utc))
            aviso.set_thumbnail(url=membro.display_avatar.url)
            aviso.set_footer(text="⚔️ Facção Bot • Aviso Oficial")
            await canal.send(embed=aviso)

        # Tenta avisar o membro por DM
        try:
            dm = discord.Embed(
                title="🚫  Você foi Removido da Facção",
                description=(
                    f"Você foi removido da facção no servidor **{interaction.guild.name}**.\n\n"
                    f"**Motivo:** {motivo}\n"
                    f"**Por:** {interaction.user.display_name}\n\n"
                    f"Entre em contato com a liderança se tiver dúvidas."
                ),
                color=COR_ERRO, timestamp=datetime.now(timezone.utc))
            dm.set_footer(text=f"Servidor: {interaction.guild.name}")
            await membro.send(embed=dm)
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Log
        await utils.enviar_log(
            self.bot, "🚫 Membro Removido da Facção",
            f"**Membro:** {membro.mention} (`{membro.id}`)\n"
            f"**Motivo:** {motivo}\n"
            f"**Por:** {interaction.user.mention}",
            cor=COR_ERRO)

    # ── /up — Promover membro (subir patente) ────────────────────────────
    @app_commands.command(name="up", description="⬆️ Promove um membro — novo cargo + motivo. [Liderança]")
    @app_commands.describe(
        membro="Membro a ser promovido",
        novo_cargo="Novo cargo (patente) que o membro vai receber",
        motivo="Motivo da promoção"
    )
    async def up(self, interaction: discord.Interaction, membro: discord.Member,
                 novo_cargo: discord.Role, motivo: str):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # Adiciona o novo cargo
        try:
            await membro.add_roles(novo_cargo)
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Sem Permissão", "O bot não tem permissão para adicionar este cargo."),
                ephemeral=True)

        # Atualiza no banco
        dados = db.get_membro(str(membro.id))
        if dados:
            db.editar_cargo_membro(str(membro.id), novo_cargo.name)

        embed = discord.Embed(
            title="⬆️🎉  PROMOÇÃO!",
            description=(
                f"O membro {membro.mention} foi **PROMOVIDO**!\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0xFFD700, timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name="🎖️ Novo Cargo", value=novo_cargo.mention, inline=True)
        embed.add_field(name="👮 Promovido por", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo", value=f"```{motivo}```", inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Patentes")
        await interaction.response.send_message(embed=embed)

        # Avisa no canal de patentes
        canal = self.bot.get_channel(CANAL_PATENTES_ID)
        if canal:
            aviso = discord.Embed(
                title="⬆️🎉  PROMOÇÃO NA FACÇÃO!",
                description=(
                    f"**{membro.display_name}** ({membro.mention}) foi **promovido**!\n\n"
                    f"🎖️ **Novo Cargo:** {novo_cargo.mention}\n"
                    f"📝 **Motivo:** ```{motivo}```\n"
                    f"👮 **Por:** {interaction.user.mention}\n\n"
                    f"🔥 Parabéns! Continue assim! 💪"
                ),
                color=0xFFD700, timestamp=datetime.now(timezone.utc))
            aviso.set_thumbnail(url=membro.display_avatar.url)
            aviso.set_footer(text="⚔️ Facção Bot • Aviso Oficial")
            await canal.send(embed=aviso)

        # DM ao membro
        try:
            dm = discord.Embed(
                title="⬆️🎉  Você foi Promovido!",
                description=(
                    f"Parabéns! Você foi **promovido** na facção **{interaction.guild.name}**!\n\n"
                    f"🎖️ **Novo Cargo:** {novo_cargo.name}\n"
                    f"📝 **Motivo:** {motivo}\n"
                    f"👮 **Por:** {interaction.user.display_name}"
                ),
                color=0xFFD700, timestamp=datetime.now(timezone.utc))
            await membro.send(embed=dm)
        except (discord.Forbidden, discord.HTTPException):
            pass

        await utils.enviar_log(self.bot, "⬆️ Promoção",
            f"**Membro:** {membro.mention}\n**Novo Cargo:** {novo_cargo.name}\n"
            f"**Motivo:** {motivo}\n**Por:** {interaction.user.mention}")

    # ── /rup — Rebaixar membro (cair patente) ────────────────────────────
    @app_commands.command(name="rup", description="⬇️ Rebaixa um membro — remove cargo e dá novo. [Liderança]")
    @app_commands.describe(
        membro="Membro a ser rebaixado",
        cargo_removido="Cargo que será removido",
        novo_cargo="Novo cargo (inferior) que o membro vai receber",
        motivo="Motivo do rebaixamento"
    )
    async def rup(self, interaction: discord.Interaction, membro: discord.Member,
                  cargo_removido: discord.Role, novo_cargo: discord.Role, motivo: str):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # Remove o cargo antigo
        try:
            if cargo_removido in membro.roles:
                await membro.remove_roles(cargo_removido)
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Sem Permissão", "O bot não tem permissão para remover este cargo."),
                ephemeral=True)

        # Adiciona o novo cargo
        try:
            await membro.add_roles(novo_cargo)
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Sem Permissão", "O bot não tem permissão para adicionar este cargo."),
                ephemeral=True)

        # Atualiza no banco
        dados = db.get_membro(str(membro.id))
        if dados:
            db.editar_cargo_membro(str(membro.id), novo_cargo.name)

        embed = discord.Embed(
            title="⬇️  REBAIXAMENTO",
            color=COR_ERRO, timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(name="👤 Membro", value=membro.mention, inline=True)
        embed.add_field(name="🔻 Cargo Removido", value=cargo_removido.mention, inline=True)
        embed.add_field(name="🎖️ Novo Cargo", value=novo_cargo.mention, inline=True)
        embed.add_field(name="👮 Por", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Motivo", value=f"```{motivo}```", inline=False)
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Patentes")
        await interaction.response.send_message(embed=embed)

        # Avisa no canal de patentes
        canal = self.bot.get_channel(CANAL_PATENTES_ID)
        if canal:
            aviso = discord.Embed(
                title="⬇️  Membro Rebaixado",
                description=(
                    f"**{membro.display_name}** ({membro.mention}) foi **rebaixado**.\n\n"
                    f"🔻 **Cargo Removido:** {cargo_removido.mention}\n"
                    f"🎖️ **Novo Cargo:** {novo_cargo.mention}\n"
                    f"📝 **Motivo:** ```{motivo}```\n"
                    f"👮 **Por:** {interaction.user.mention}"
                ),
                color=COR_ERRO, timestamp=datetime.now(timezone.utc))
            aviso.set_thumbnail(url=membro.display_avatar.url)
            aviso.set_footer(text="⚔️ Facção Bot • Aviso Oficial")
            await canal.send(embed=aviso)

        # DM ao membro
        try:
            dm = discord.Embed(
                title="⬇️  Você foi Rebaixado",
                description=(
                    f"Você foi **rebaixado** na facção **{interaction.guild.name}**.\n\n"
                    f"🔻 **Cargo Removido:** {cargo_removido.name}\n"
                    f"🎖️ **Novo Cargo:** {novo_cargo.name}\n"
                    f"📝 **Motivo:** {motivo}\n"
                    f"👮 **Por:** {interaction.user.display_name}"
                ),
                color=COR_ERRO, timestamp=datetime.now(timezone.utc))
            await membro.send(embed=dm)
        except (discord.Forbidden, discord.HTTPException):
            pass

        await utils.enviar_log(self.bot, "⬇️ Rebaixamento",
            f"**Membro:** {membro.mention}\n**Removido:** {cargo_removido.name}\n"
            f"**Novo:** {novo_cargo.name}\n**Motivo:** {motivo}\n**Por:** {interaction.user.mention}",
            cor=COR_ERRO)


    # ── /config_meta ─────────────────────────────────────────────────────
    @app_commands.command(name="config_meta", description="⚙️ Configura a meta semanal de um item. (0 = desativar) [Liderança]")
    @app_commands.describe(tipo="Tipo de item", quantidade="Quantidade necessária (0 para desativar)")
    @app_commands.choices(tipo=TIPOS_ENTREGA)
    async def config_meta(self, interaction: discord.Interaction, tipo: app_commands.Choice[str], quantidade: int):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        if quantidade < 0:
            return await interaction.response.send_message(
                embed=utils.embed_erro("Valor Inválido", "A quantidade não pode ser negativa."), ephemeral=True)

        db.set_meta_ativa(tipo.value, quantidade)
        nome, emoji, _ = _tipo_info(tipo.value)

        if quantidade == 0:
            desc = f"A meta para **{emoji} {nome}** foi **desativada**."
        else:
            desc = f"A meta para **{emoji} {nome}** foi atualizada para **`{quantidade:,}`** unidades."

        embed = discord.Embed(title="⚙️  Configuração de Meta Atualizada", description=desc, color=COR_SUCESSO, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.response.send_message(embed=embed)

    # ── /metas_ativas ────────────────────────────────────────────────────
    @app_commands.command(name="metas_ativas", description="📋 Mostra quais são as metas ativas da facção.")
    async def metas_ativas(self, interaction: discord.Interaction):
        metas = db.get_metas_ativas()
        
        embed = discord.Embed(title="📋  Metas Ativas", color=COR_PRINCIPAL, timestamp=datetime.now(timezone.utc))
        if metas:
            linhas = []
            for t_ativo, qtd_ativa in metas.items():
                nome, emoji, _ = _tipo_info(t_ativo)
                linhas.append(f"**{emoji} {nome}:** `{qtd_ativa:,}` unidades")
            
            modo = db.get_modo_meta()
            if modo == "ou":
                texto_modo = "*Para bater a meta semanal, o membro deve atingir a quantidade de **UM** destes itens.*"
            else:
                texto_modo = "*Para bater a meta semanal, o membro deve atingir a quantidade de **TODOS** os itens ativos.*"
                
            embed.description = "\n".join(linhas) + f"\n\n{texto_modo}"
        else:
            embed.description = "Nenhuma meta está configurada no momento."
            
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.response.send_message(embed=embed)

    # ── /modo_meta ───────────────────────────────────────────────────────
    @app_commands.command(name="modo_meta", description="⚙️ Define se para bater a meta é preciso UM (ou) ou TODOS (e) os itens. [Liderança]")
    @app_commands.describe(modo="Modo de verificação de meta")
    @app_commands.choices(modo=[
        app_commands.Choice(name="Qualquer item (OU)", value="ou"),
        app_commands.Choice(name="Todos os itens (E)", value="e")
    ])
    async def modo_meta(self, interaction: discord.Interaction, modo: app_commands.Choice[str]):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        
        db.set_modo_meta(modo.value)
        if modo.value == "ou":
            desc = "Agora, basta bater a meta de **UM** dos itens ativos para cumprir a meta da semana."
        else:
            desc = "Agora, é necessário bater a meta de **TODOS** os itens ativos para cumprir a meta da semana."
            
        embed = discord.Embed(title="⚙️ Modo de Meta Atualizado", description=desc, color=COR_SUCESSO, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Metas")
        await interaction.response.send_message(embed=embed)

    # ── /lembrete_meta ───────────────────────────────────────────────────
    @app_commands.command(name="lembrete_meta", description="🔔 Envia um lembrete sobre as metas para a facção ou para um membro. [Liderança]")
    @app_commands.describe(membro="Opcional: Enviar DM apenas para este membro.")
    async def lembrete_meta(self, interaction: discord.Interaction, membro: discord.Member = None):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🔔 Lembrete de Metas",
            description=(
                "Salve, guerreiro! Passando para lembrar que você tem compromissos com a facção.\n\n"
                "**Verifique suas metas pendentes** batendo o comando `/metas` (se aplicável) e não esqueça de entregar tudo no prazo!\n\n"
                "A facção conta com seu esforço. 🚀"
            ),
            color=COR_AVISO,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"⚔️ {interaction.guild.name} • Avisos")
        
        if membro:
            try:
                await membro.send(embed=embed)
                await interaction.followup.send(f"✅ Lembrete de metas enviado com sucesso na DM de {membro.mention}!")
            except discord.Forbidden:
                await interaction.followup.send(f"❌ Não foi possível enviar DM para {membro.mention}. A DM dele pode estar fechada.")
        else:
            cargo = interaction.guild.get_role(CARGO_OBRIGADO_META_ID)
            if not cargo:
                return await interaction.followup.send("❌ Cargo de metas obrigatórias não encontrado no servidor.")
            
            enviados = 0
            erros = 0
            for m in cargo.members:
                if m.bot: continue
                try:
                    await m.send(embed=embed)
                    enviados += 1
                except discord.Forbidden:
                    erros += 1
            
            await interaction.followup.send(f"✅ Lembrete enviado para **{enviados}** membros com o cargo de meta.\n❌ Falhas (DM fechada): **{erros}**.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Metas(bot))
