"""
commands/verificacao_meta.py - Sistema de verificação automática de membros e metas
────────────────────────────────────────────────────────────────────────────────────
Quem tiver o cargo CARGO_OBRIGADO_META_ID (ID: 1492527673531171019) é OBRIGADO a:
  1. Estar registrado como membro no banco de dados
  2. Bater a meta semanal de farm

Funciona de duas formas:
  A) Automática → toda segunda-feira às 08:00 (BRT) verifica todo mundo
  B) Manual     → /verificar_membros  (comando da liderança, roda na hora)

Para cada membro com o cargo:
  ✓ Está no banco + bateu meta  → OK, nada acontece
  ✗ Não está no banco           → avisa a liderança (não pode cobrar farm de quem não está cadastrado)
  ✗ Está no banco + NÃO bateu  → registra punição automática + log
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, time
import asyncio

import database as db
import checks
import utils
from config import (
    CARGO_OBRIGADO_META_ID,
    META_FARM_SEMANAL,
    COR_ERRO,
    COR_SUCESSO,
    COR_AVISO,
    LOG_CHANNEL_ID,
)


# ─── HORA DA VERIFICAÇÃO AUTOMÁTICA ───────────────────────────────────────────
# Segunda-feira (weekday=0), às 11:00 UTC = 08:00 BRT
HORA_VERIFICACAO = time(hour=11, minute=0, tzinfo=timezone.utc)
DIA_VERIFICACAO  = 0  # 0 = segunda-feira


class VerificacaoMeta(commands.Cog):
    """Verifica se membros com o cargo obrigatório estão cadastrados e batendo a meta."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task_iniciada = False

    async def cog_load(self):
        """Inicia o loop quando o cog é carregado."""
        if not self._task_iniciada:
            self._task_iniciada = True
            self.bot.loop.create_task(self._loop_verificacao())

    # ──────────────────────────────────────────────────────────────────────────
    #   LOOP AUTOMÁTICO (toda segunda-feira)
    # ──────────────────────────────────────────────────────────────────────────
    async def _loop_verificacao(self):
        """Aguarda e executa a verificação toda segunda-feira."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            agora = datetime.now(timezone.utc)

            # Calcula quantos segundos até a próxima segunda às 11h UTC
            dias_ate_segunda = (DIA_VERIFICACAO - agora.weekday()) % 7
            if dias_ate_segunda == 0 and agora.time() >= HORA_VERIFICACAO:
                dias_ate_segunda = 7  # Já passou hoje, espera a próxima

            proxima = agora.replace(
                hour=HORA_VERIFICACAO.hour,
                minute=HORA_VERIFICACAO.minute,
                second=0,
                microsecond=0,
            )
            # Avança para o próximo dia correto
            from datetime import timedelta
            proxima += timedelta(days=dias_ate_segunda)

            espera = (proxima - agora).total_seconds()
            print(f"[META] Próxima verificação automática em {int(espera // 3600)}h {int((espera % 3600) // 60)}min")
            await asyncio.sleep(espera)

            # Executa em todos os servidores conectados
            for guild in self.bot.guilds:
                await self._executar_verificacao(guild, automatico=True)

    # ──────────────────────────────────────────────────────────────────────────
    #   LÓGICA CENTRAL DE VERIFICAÇÃO
    # ──────────────────────────────────────────────────────────────────────────
    async def _executar_verificacao(self, guild: discord.Guild, automatico: bool = False):
        """
        Verifica todos os membros com CARGO_OBRIGADO_META_ID no servidor.
        Retorna um dict com os resultados para exibição.
        """
        cargo = guild.get_role(CARGO_OBRIGADO_META_ID)
        if cargo is None:
            return None

        resultado = {
            "ok":           [],   # Cadastrado + bateu meta
            "sem_cadastro": [],   # Tem o cargo mas não está no banco
            "sem_meta":     [],   # Cadastrado mas não bateu a meta
        }

        for membro in cargo.members:
            if membro.bot:
                continue

            dados = db.get_membro(str(membro.id))

            if dados is None:
                # Não está cadastrado no banco
                resultado["sem_cadastro"].append(membro)

            elif dados["farm_semanal"] < META_FARM_SEMANAL:
                # Cadastrado mas não bateu a meta
                resultado["sem_meta"].append((membro, dados["farm_semanal"]))

                # Registra punição automática no banco
                db.aplicar_punicao(
                    str(membro.id),
                    "Não bateu a meta de farm semanal — verificação automática",
                    "meta_nao_batida",
                    "0",  # ID 0 = sistema automático
                    datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M"),
                )

                # Tenta avisar o membro por DM
                try:
                    dm_embed = discord.Embed(
                        title="⚠️ Meta de Farm Não Batida",
                        description=(
                            f"Olá, **{membro.display_name}**!\n\n"
                            f"Você **não bateu a meta semanal** de farm no servidor **{guild.name}**.\n\n"
                            f"**Seu farm esta semana:** `{dados['farm_semanal']:,}`\n"
                            f"**Meta exigida:** `{META_FARM_SEMANAL:,}`\n\n"
                            f"Uma punição foi registrada no seu histórico.\n"
                            f"Entre em contato com a liderança se tiver dúvidas."
                        ),
                        color=COR_ERRO,
                        timestamp=datetime.now(timezone.utc),
                    )
                    dm_embed.set_footer(text=f"⚔️ {guild.name} • Sistema Automático")
                    await membro.send(embed=dm_embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

            else:
                resultado["ok"].append(membro)

        # Envia log detalhado no canal de log do bot
        await self._enviar_log_verificacao(guild, resultado, automatico)

        return resultado

    # ──────────────────────────────────────────────────────────────────────────
    #   LOG DA VERIFICAÇÃO
    # ──────────────────────────────────────────────────────────────────────────
    async def _enviar_log_verificacao(self, guild: discord.Guild, resultado: dict, automatico: bool):
        """Envia um embed de log completo com todos os resultados."""
        if not LOG_CHANNEL_ID:
            return
        canal = self.bot.get_channel(LOG_CHANNEL_ID)
        if canal is None:
            return

        total = len(resultado["ok"]) + len(resultado["sem_cadastro"]) + len(resultado["sem_meta"])
        modo  = "🤖 Automática (toda segunda-feira)" if automatico else "👮 Manual (comando /verificar_membros)"

        embed = discord.Embed(
            title="📋  Verificação de Membros — Resultado",
            description=(
                f"**Cargo verificado:** <@&{CARGO_OBRIGADO_META_ID}>\n"
                f"**Meta semanal:** `{META_FARM_SEMANAL:,}`\n"
                f"**Total verificados:** `{total}`\n"
                f"**Modo:** {modo}"
            ),
            color=COR_AVISO,
            timestamp=datetime.now(timezone.utc),
        )

        # ── OK ─────────────────────────────────────────────────────────────────
        if resultado["ok"]:
            nomes_ok = "\n".join(f"✅ {m.mention}" for m in resultado["ok"][:20])
            if len(resultado["ok"]) > 20:
                nomes_ok += f"\n*... e mais {len(resultado['ok']) - 20}*"
            embed.add_field(
                name=f"✅ Bateram a meta ({len(resultado['ok'])})",
                value=nomes_ok,
                inline=False,
            )

        # ── Sem cadastro ───────────────────────────────────────────────────────
        if resultado["sem_cadastro"]:
            nomes_sc = "\n".join(f"⚠️ {m.mention} (`{m.id}`)" for m in resultado["sem_cadastro"][:20])
            embed.add_field(
                name=f"⚠️ Não cadastrados no sistema ({len(resultado['sem_cadastro'])})",
                value=nomes_sc + "\n*Use `/registrar` para cadastrá-los.*",
                inline=False,
            )

        # ── Sem meta ───────────────────────────────────────────────────────────
        if resultado["sem_meta"]:
            linhas = []
            for m, farm in resultado["sem_meta"][:20]:
                pct = int((farm / META_FARM_SEMANAL) * 100)
                linhas.append(f"❌ {m.mention} — `{farm:,}/{META_FARM_SEMANAL:,}` ({pct}%)")
            if len(resultado["sem_meta"]) > 20:
                linhas.append(f"*... e mais {len(resultado['sem_meta']) - 20}*")
            embed.add_field(
                name=f"❌ Não bateram a meta ({len(resultado['sem_meta'])})",
                value="\n".join(linhas),
                inline=False,
            )
            embed.add_field(
                name="🔨 Ação tomada",
                value="Punição registrada automaticamente no histórico de cada membro e DM enviada.",
                inline=False,
            )

        embed.set_footer(text="⚔️ Facção Bot • Sistema de Verificação de Metas")
        await canal.send(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════════
    #   /verificar_membros — Comando manual da liderança
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(
        name="verificar_membros",
        description="🔍 Verifica todos os membros com o cargo obrigatório (meta + cadastro). [Liderança]"
    )
    async def verificar_membros(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        await interaction.response.defer(ephemeral=False)

        resultado = await self._executar_verificacao(interaction.guild, automatico=False)

        if resultado is None:
            return await interaction.followup.send(
                embed=utils.embed_erro(
                    "Cargo Não Encontrado",
                    f"O cargo de verificação (ID `{CARGO_OBRIGADO_META_ID}`) não existe neste servidor."
                )
            )

        total     = len(resultado["ok"]) + len(resultado["sem_cadastro"]) + len(resultado["sem_meta"])
        ok_count  = len(resultado["ok"])
        sc_count  = len(resultado["sem_cadastro"])
        sm_count  = len(resultado["sem_meta"])

        # Embed de resumo público
        embed = discord.Embed(
            title="🔍  Verificação de Membros Concluída",
            color=COR_SUCESSO if sm_count == 0 and sc_count == 0 else COR_AVISO,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="👥 Total verificados",    value=f"`{total}`",    inline=True)
        embed.add_field(name="✅ Bateram meta",          value=f"`{ok_count}`", inline=True)
        embed.add_field(name="⚠️ Sem cadastro",          value=f"`{sc_count}`", inline=True)
        embed.add_field(name="❌ Não bateram a meta",    value=f"`{sm_count}`", inline=True)
        embed.add_field(
            name="📋 Detalhes",
            value=f"O log completo foi enviado no canal de logs do bot.",
            inline=False,
        )

        if sm_count > 0:
            embed.add_field(
                name="🔨 Punições",
                value=f"`{sm_count}` punições registradas automaticamente no histórico.",
                inline=False,
            )

        embed.set_footer(text="⚔️ Facção Bot • Sistema de Verificação")
        await interaction.followup.send(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════════
    #   /status_meta — Ver situação individual de qualquer membro
    # ══════════════════════════════════════════════════════════════════════════════
    @app_commands.command(
        name="status_meta",
        description="📊 Vê a situação de um membro: cadastro + progresso da meta. [Liderança]"
    )
    @app_commands.describe(membro="Mencione o membro a verificar")
    async def status_meta(self, interaction: discord.Interaction, membro: discord.Member):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # Verifica se tem o cargo obrigatório
        cargo = interaction.guild.get_role(CARGO_OBRIGADO_META_ID)
        tem_cargo = cargo in membro.roles if cargo else False

        dados = db.get_membro(str(membro.id))

        embed = discord.Embed(
            title=f"📊  Status — {membro.display_name}",
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=membro.display_avatar.url)

        # Cargo obrigatório
        embed.add_field(
            name="🎭 Cargo Obrigatório",
            value=f"{'✅ Tem o cargo' if tem_cargo else '➖ Não tem o cargo'} <@&{CARGO_OBRIGADO_META_ID}>",
            inline=False,
        )

        # Cadastro
        if dados is None:
            embed.add_field(name="📋 Cadastro", value="❌ **Não cadastrado** no sistema", inline=True)
            embed.color = COR_ERRO
        else:
            # Progresso da meta
            farm     = dados["farm_semanal"]
            bateu    = farm >= META_FARM_SEMANAL
            pct      = min(100, int((farm / META_FARM_SEMANAL) * 100))
            barras   = int(pct / 10)
            barra    = "█" * barras + "░" * (10 - barras)

            embed.add_field(name="📋 Cadastro",     value="✅ Registrado no sistema", inline=True)
            embed.add_field(name="🌾 Farm semanal", value=f"`{farm:,}`",              inline=True)
            embed.add_field(name="🎯 Meta",         value=f"`{META_FARM_SEMANAL:,}`", inline=True)
            embed.add_field(name="📈 Progresso",    value=f"`[{barra}]` {pct}%",      inline=False)
            embed.add_field(
                name="🏁 Status Meta",
                value="✅ **META BATIDA!**" if bateu else "❌ **Meta não batida**",
                inline=True,
            )
            embed.add_field(name="⚠️ Advertências", value=f"`{dados['advertencias']}`", inline=True)
            embed.add_field(name="🔨 Punições",      value=f"`{dados['punicoes']}`",     inline=True)

            embed.color = COR_SUCESSO if bateu else COR_ERRO

        embed.set_footer(text="⚔️ Facção Bot • Sistema de Verificação")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificacaoMeta(bot))
