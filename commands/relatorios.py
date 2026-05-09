"""
commands/relatorios.py - Comandos de relatórios e administração
/relatorio_geral, /resetar_semana
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

import database as db
import checks
import utils
from config import (
    COR_PRINCIPAL, COR_ERRO, COR_SUCESSO, COR_AVISO, META_FARM_SEMANAL,
    META_C4_MINIMA, META_PLASTICOS_MINIMA, CARGO_META_OBRIGATORIO_ID,
)


def _barra(atual: int, meta: int) -> str:
    pct = min(100, int((atual / meta) * 100)) if meta > 0 else 0
    b = int(pct / 10)
    return f"[{'█' * b}{'░' * (10 - b)}] {pct}%"


class Relatorios(commands.Cog):
    """Cog responsável por relatórios gerais e administração."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── /relatorio_geral ──────────────────────────────────────────────────────
    @app_commands.command(name="relatorio_geral", description="📊 Relatório completo da facção com metas e membros.")
    async def relatorio_geral(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        await interaction.response.defer()
        stats = db.get_estatisticas_gerais()

        # ═══════════════ EMBED 1: VISÃO GERAL ═══════════════
        e1 = discord.Embed(
            title="📊  RELATÓRIO GERAL DA FACÇÃO",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 Gerado em: `{utils.data_agora()}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=COR_PRINCIPAL, timestamp=datetime.now(timezone.utc))

        e1.add_field(name="👥 Membros Ativos", value=f"```{stats['total_membros']}```", inline=True)
        e1.add_field(name="🌾 Farm Total", value=f"```{stats['total_farm']:,}```", inline=True)
        e1.add_field(name="💣 C4 Total", value=f"```{stats['total_c4']:,}```", inline=True)
        e1.add_field(name="⚠️ Advertências", value=f"```{stats['total_advertencias']}```", inline=True)
        e1.add_field(name="🔨 Punições", value=f"```{stats['total_punicoes']}```", inline=True)
        e1.add_field(name="✅ Presenças", value=f"```{stats['total_presencas']}```", inline=True)

        # Top 3
        if stats["top_ativos"]:
            medalhas = ["🥇", "🥈", "🥉"]
            top_txt = "\n".join(
                f"{medalhas[i]} **{r['nome']}** — `{r['farm_semanal']:,}` farm"
                for i, r in enumerate(stats["top_ativos"])
            )
            e1.add_field(name="🏆 Top Membros (Farm Semanal)", value=top_txt, inline=False)

        e1.set_footer(text="⚔️ Facção Bot • Relatório Geral  │  Página 1/3")
        await interaction.followup.send(embed=e1)

        # ═══════════════ COLETA DE DADOS DE METAS ═══════════════
        cargo = interaction.guild.get_role(CARGO_META_OBRIGATORIO_ID)
        membros_meta = []
        if cargo:
            for membro in cargo.members:
                if membro.bot:
                    continue
                dados = db.get_membro(str(membro.id))
                if dados:
                    totais = db.get_total_por_tipo(str(membro.id))
                    membros_meta.append((membro, dados, totais))

        bateram = []
        nao_bateram = []
        for membro, dados, totais in membros_meta:
            bateu_c4 = totais["c4"] >= META_C4_MINIMA
            bateu_pl = totais["plasticos"] >= META_PLASTICOS_MINIMA
            if bateu_c4 or bateu_pl:
                via = []
                if bateu_c4:
                    via.append("💣 C4")
                if bateu_pl:
                    via.append("🧱 Plásticos")
                bateram.append((membro, totais, " + ".join(via)))
            else:
                falta_c4 = max(0, META_C4_MINIMA - totais["c4"])
                falta_pl = max(0, META_PLASTICOS_MINIMA - totais["plasticos"])
                nao_bateram.append((membro, totais, falta_c4, falta_pl))

        total_meta = len(bateram) + len(nao_bateram)
        pct_geral = int((len(bateram) / total_meta) * 100) if total_meta > 0 else 0

        # ═══════════════ EMBED 2: TODOS OS MEMBROS — STATUS DA META ═══════════════
        e2 = discord.Embed(
            title="📋  STATUS DE METAS — TODOS OS MEMBROS",
            description=(
                f"**Meta C4:** `{META_C4_MINIMA}` un.  •  **Meta Plásticos:** `{META_PLASTICOS_MINIMA}` un.\n"
                f"**Progresso geral:** `{len(bateram)}/{total_meta}` membros ({pct_geral}%)\n"
                f"`{_barra(len(bateram), total_meta)}`\n"
                f"✅ Bateram: **{len(bateram)}** │ ❌ Pendentes: **{len(nao_bateram)}**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=COR_PRINCIPAL, timestamp=datetime.now(timezone.utc))

        # Quem BATEU — com tipo de meta
        if bateram:
            linhas = []
            for i, (m, t, via) in enumerate(bateram, 1):
                linhas.append(
                    f"`{i:02d}.` ✅ {m.mention}\n"
                    f"　　🏆 **META BATIDA** via: {via}\n"
                    f"　　💣 C4: `{t['c4']}/{META_C4_MINIMA}` `{_barra(t['c4'], META_C4_MINIMA)}`\n"
                    f"　　🧱 PL: `{t['plasticos']}/{META_PLASTICOS_MINIMA}` `{_barra(t['plasticos'], META_PLASTICOS_MINIMA)}`"
                )
            # Discord tem limite de 1024 por field, dividir se necessário
            texto_bateram = "\n".join(linhas)
            if len(texto_bateram) <= 1024:
                e2.add_field(name=f"✅ Bateram a Meta ({len(bateram)})", value=texto_bateram, inline=False)
            else:
                meio = len(linhas) // 2
                e2.add_field(name=f"✅ Bateram a Meta ({len(bateram)}) [1/2]", value="\n".join(linhas[:meio]), inline=False)
                e2.add_field(name=f"✅ Bateram a Meta [2/2]", value="\n".join(linhas[meio:]), inline=False)
        else:
            e2.add_field(name="✅ Bateram (0)", value="*Nenhum membro bateu a meta ainda.*", inline=False)

        e2.set_footer(text="⚔️ Facção Bot • Relatório Geral  │  Página 2/3")
        await interaction.channel.send(embed=e2)

        # ═══════════════ EMBED 3: QUEM NÃO BATEU — QUANTO FALTA ═══════════════
        e3 = discord.Embed(
            title="❌  MEMBROS PENDENTES — QUANTO FALTA",
            description=(
                f"**Pendentes:** `{len(nao_bateram)}` membro(s)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=COR_ERRO, timestamp=datetime.now(timezone.utc))

        if nao_bateram:
            linhas = []
            for i, (m, t, fc4, fpl) in enumerate(nao_bateram, 1):
                linhas.append(
                    f"`{i:02d}.` ❌ {m.mention}\n"
                    f"　　💣 C4: `{t['c4']}/{META_C4_MINIMA}` — ⚠️ falta **{fc4}** — `{_barra(t['c4'], META_C4_MINIMA)}`\n"
                    f"　　🧱 PL: `{t['plasticos']}/{META_PLASTICOS_MINIMA}` — ⚠️ falta **{fpl}** — `{_barra(t['plasticos'], META_PLASTICOS_MINIMA)}`"
                )
            texto_nao = "\n".join(linhas)
            if len(texto_nao) <= 1024:
                e3.add_field(name=f"⏳ Pendentes ({len(nao_bateram)})", value=texto_nao, inline=False)
            else:
                meio = len(linhas) // 2
                e3.add_field(name=f"⏳ Pendentes ({len(nao_bateram)}) [1/2]", value="\n".join(linhas[:meio]), inline=False)
                e3.add_field(name=f"⏳ Pendentes [2/2]", value="\n".join(linhas[meio:]), inline=False)
        else:
            e3.add_field(name="🎉 Todos Bateram!", value="*Parabéns! Todos os membros bateram a meta!* 🏆", inline=False)

        # Membros parados (sem farm)
        if stats["parados"]:
            parados_txt = ", ".join(f"**{m['nome']}**" for m in stats["parados"][:15])
            e3.add_field(name=f"😴 Sem Farm esta Semana ({len(stats['parados'])})", value=parados_txt, inline=False)

        e3.set_footer(text="⚔️ Facção Bot • Relatório Geral  │  Página 3/3")
        await interaction.channel.send(embed=e3)

    # ─── /resetar_semana ───────────────────────────────────────────────────────
    @app_commands.command(name="resetar_semana", description="Reseta o farm semanal e as metas da semana.")
    async def resetar_semana(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # Confirmação via View com botões
        embed = discord.Embed(
            title="⚠️ Confirmação Necessária",
            description=(
                "Você está prestes a **resetar o farm semanal** de todos os membros.\n\n"
                "Esta ação **não pode ser desfeita**.\n\n"
                "Deseja continuar?"
            ),
            color=COR_AVISO
        )
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Gerenciamento")

        view = ConfirmacaoResetView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    # ─── /destaques ────────────────────────────────────────────────────────────
    @app_commands.command(name="destaques", description="🌟 Mostra o top 3 membros mais ativos e exemplares da facção.")
    async def destaques(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        await interaction.response.defer()

        medalhas = ["🥇", "🥈", "🥉"]

        embed = discord.Embed(
            title="🌟  DESTAQUES DA FACÇÃO",
            description="Reconhecimento dos guerreiros mais ativos desta semana!",
            color=0xFFD700, timestamp=datetime.now(timezone.utc)
        )

        # 1. Top Bate-Ponto
        rk_ponto = db.get_ranking_ponto(limite=3)
        if rk_ponto:
            txt = ""
            for i, p in enumerate(rk_ponto):
                duracao = utils.formatar_duracao(p['tempo_total'])
                txt += f"{medalhas[i]} <@{p['discord_id']}> — `{duracao}`\n"
            embed.add_field(name="⏱️ Top Ponto", value=txt, inline=False)
        else:
            embed.add_field(name="⏱️ Top Ponto", value="*Nenhum registro.*", inline=False)

        # 2. Top Farm
        rk_farm = db.get_ranking_farm(limite=3)
        if rk_farm:
            txt = ""
            for i, f in enumerate(rk_farm):
                txt += f"{medalhas[i]} <@{f['discord_id']}> — `{f['farm_semanal']:,}` farm\n"
            embed.add_field(name="🌾 Top Farm Semanal", value=txt, inline=False)
        else:
            embed.add_field(name="🌾 Top Farm Semanal", value="*Nenhum registro.*", inline=False)

        # 3. Top Metas
        rk_metas = db.get_ranking_metas(limite=3)
        if rk_metas:
            txt = ""
            for i, m in enumerate(rk_metas):
                txt += f"{medalhas[i]} <@{m['discord_id']}> — `{m['total_entregas']:,}` itens\n"
            embed.add_field(name="📦 Maiores Entregadores", value=txt, inline=False)
        else:
            embed.add_field(name="📦 Maiores Entregadores", value="*Nenhuma entrega.*", inline=False)

        # 4. Exemplares
        exemplares = db.get_membros_exemplares(limite=5)
        if exemplares:
            txt = ", ".join(f"<@{e['discord_id']}>" for e in exemplares)
            embed.add_field(name="⭐ Membros Exemplares (Sem Punições e Ativos)", value=txt, inline=False)
        
        embed.set_footer(text="⚔️ Facção Bot • Sistema de Organização")
        await interaction.followup.send(embed=embed)

    # ─── /inativos ─────────────────────────────────────────────────────────────
    @app_commands.command(name="inativos", description="🧹 Mostra membros que não têm ponto, farm nem metas recentes.")
    async def inativos(self, interaction: discord.Interaction):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)
        await interaction.response.defer()

        membros_inativos = db.get_inativos()
        
        embed = discord.Embed(
            title="🧹 MEMBROS INATIVOS",
            description="Membros que estão com 0 farm na semana e nenhuma entrega de meta registrada.",
            color=COR_ERRO, timestamp=datetime.now(timezone.utc)
        )

        if membros_inativos:
            txt = "\n".join(f"❌ <@{m['discord_id']}> (`{m['discord_id']}`)" for m in membros_inativos)
            # split if too long
            if len(txt) > 1024:
                meio = len(membros_inativos) // 2
                t1 = "\n".join(f"❌ <@{m['discord_id']}>" for m in membros_inativos[:meio])
                t2 = "\n".join(f"❌ <@{m['discord_id']}>" for m in membros_inativos[meio:])
                embed.add_field(name=f"Inativos ({len(membros_inativos)}) [1/2]", value=t1, inline=False)
                embed.add_field(name="Inativos [2/2]", value=t2, inline=False)
            else:
                embed.add_field(name=f"Total: {len(membros_inativos)}", value=txt, inline=False)
        else:
            embed.add_field(name="Status", value="✅ Não há membros inativos nesta semana!", inline=False)

        embed.set_footer(text="⚔️ Facção Bot • Sistema de Organização")
        await interaction.followup.send(embed=embed)


class ConfirmacaoResetView(discord.ui.View):
    """View com botões de confirmação para o reset semanal."""

    def __init__(self, autor: discord.User):
        super().__init__(timeout=30)
        self.autor = autor

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Apenas quem enviou o comando pode confirmar."""
        return interaction.user.id == self.autor.id

    @discord.ui.button(label="✅ Confirmar Reset", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        db.resetar_farm_semanal()

        embed = utils.embed_sucesso(
            "Semana Resetada!",
            "O **farm semanal** de todos os membros foi zerado.\n"
            "Uma nova semana de competição começa agora! 🚀"
        )
        embed.add_field(name="👮 Executado por", value=interaction.user.mention, inline=True)
        embed.add_field(name="📅 Data", value=utils.data_agora(), inline=True)

        await interaction.response.edit_message(embed=embed, view=None)
        await utils.enviar_log(
            interaction.client,
            "Semana Resetada",
            f"O farm semanal foi resetado por **{interaction.user.display_name}**.",
            cor=COR_SUCESSO
        )

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✋ Reset Cancelado",
            description="O reset semanal foi cancelado. Nenhum dado foi alterado.",
            color=COR_ERRO
        )
        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Relatorios(bot))
