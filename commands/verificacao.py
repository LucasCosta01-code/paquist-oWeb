"""
commands/verificacao.py - Sistema de Verificação de Cargo em Massa

Comandos:
  /verm             → Mostra membros COM e SEM o cargo alvo. Oferece botão
                      interativo para dar o cargo a todos que não têm.
  /verificar_cargo  → Escaneia e atribui o cargo automaticamente para todos.
  /add_adm          → Concede permissão de uso dos comandos deste módulo a um cargo.
  /remove_adm       → Remove permissão de uso de um cargo.

Cargo alvo (obrigatório para todos): 1492527673531171019
Cargo com permissão máxima fixa:     1494537507310800928 (CARGO_FUNDADOR_ID)
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

import checks
import utils
import database as db
from config import (
    CARGO_FUNDADOR_ID,
    COR_PRINCIPAL, COR_SUCESSO, COR_ERRO, COR_AVISO,
)

# ─── CONSTANTES ────────────────────────────────────────────────────────────────
# Cargo que TODOS os membros devem ter
CARGO_ALVO_ID = 1492527673531171019

# Cargos fixos que sempre têm permissão para usar os comandos deste módulo
CARGOS_FIXOS_PERM = {CARGO_FUNDADOR_ID}

# Limite de nomes exibidos por campo no embed
_MAX_LISTA = 25


# ─── HELPERS DE BANCO DE DADOS ─────────────────────────────────────────────────
def _criar_tabela_perm():
    """Cria a tabela de cargos com permissão ADM de verificação."""
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verificacao_adm (
            cargo_id TEXT PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()


def _get_cargos_adm() -> set:
    """Retorna todos os IDs de cargo com permissão (banco + fixos)."""
    conn = db.get_connection()
    rows = conn.execute("SELECT cargo_id FROM verificacao_adm").fetchall()
    conn.close()
    ids = {int(r["cargo_id"]) for r in rows}
    return ids | CARGOS_FIXOS_PERM


def _add_cargo_adm(cargo_id: int) -> bool:
    """Adiciona um cargo ao banco. Retorna False se já existir."""
    conn = db.get_connection()
    try:
        conn.execute("INSERT INTO verificacao_adm (cargo_id) VALUES (?)", (str(cargo_id),))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def _remove_cargo_adm(cargo_id: int) -> bool:
    """Remove um cargo do banco. Retorna False se não existia."""
    conn = db.get_connection()
    cur = conn.execute("DELETE FROM verificacao_adm WHERE cargo_id = ?", (str(cargo_id),))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def _tem_permissao(interaction: discord.Interaction) -> bool:
    """Verifica se o usuário tem algum cargo com permissão de verificação."""
    cargos_perm = _get_cargos_adm()
    ids_usuario = {role.id for role in interaction.user.roles}
    return bool(ids_usuario & cargos_perm)


# ─── HELPER: formata lista de membros ─────────────────────────────────────────
def _formatar_lista(membros: list[discord.Member], limite: int = _MAX_LISTA) -> str:
    """Formata lista de membros para exibição em embed."""
    if not membros:
        return "_Nenhum_"
    linhas = [f"• `{m.display_name}`" for m in membros[:limite]]
    texto = "\n".join(linhas)
    if len(membros) > limite:
        texto += f"\n_... e mais {len(membros) - limite} membros_"
    return texto


# ─── VIEW COM BOTÃO: Dar Cargo ─────────────────────────────────────────────────
class ViewDarCargo(discord.ui.View):
    """
    View com dois botões:
    ✅ Dar Cargo a Todos  → atribui o cargo alvo a todos da lista `sem_cargo`
    ❌ Cancelar          → desativa os botões sem fazer nada
    """

    def __init__(
        self,
        sem_cargo: list[discord.Member],
        cargo_alvo: discord.Role,
        autor_id: int,
        bot: commands.Bot,
    ):
        super().__init__(timeout=120)  # Expira em 2 minutos
        self.sem_cargo  = sem_cargo
        self.cargo_alvo = cargo_alvo
        self.autor_id   = autor_id
        self.bot        = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Só o usuário que rodou o comando pode usar os botões."""
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "❌ Apenas quem usou o comando pode interagir com esses botões.",
                ephemeral=True,
            )
            return False
        return True

    # ── Botão: Dar Cargo ──────────────────────────────────────────────────────
    @discord.ui.button(
        label="✅  Dar Cargo a Todos",
        style=discord.ButtonStyle.success,
        custom_id="dar_cargo_btn",
    )
    async def dar_cargo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)

        atribuidos = 0
        erros: list[str] = []

        for membro in self.sem_cargo:
            try:
                await membro.add_roles(
                    self.cargo_alvo,
                    reason=f"Adicionado via /verm por {interaction.user}",
                )
                atribuidos += 1
            except discord.Forbidden:
                erros.append(f"`{membro.display_name}` — sem permissão")
            except discord.HTTPException as e:
                erros.append(f"`{membro.display_name}` — erro: {e}")

        # Desativa todos os botões
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        # Embed de resultado
        cor = COR_SUCESSO if not erros else COR_AVISO
        embed = discord.Embed(
            title="✅  Cargo Atribuído com Sucesso!",
            color=cor,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="🏷️ Cargo",        value=self.cargo_alvo.mention, inline=True)
        embed.add_field(name="✅ Atribuídos",   value=f"`{atribuidos}`",       inline=True)
        embed.add_field(name="❌ Erros",        value=f"`{len(erros)}`",       inline=True)

        if erros:
            embed.add_field(
                name="⚠️ Membros com erro",
                value="\n".join(erros[:10]),
                inline=False,
            )

        embed.set_footer(
            text=f"Executado por {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.followup.send(embed=embed)

        # Log
        await utils.enviar_log(
            self.bot,
            "Cargo Atribuído via /verm",
            (
                f"**Cargo:** {self.cargo_alvo.mention}\n"
                f"**Atribuídos:** `{atribuidos}`\n"
                f"**Erros:** `{len(erros)}`\n"
                f"**Executado por:** {interaction.user.mention}"
            ),
            cor=cor,
        )
        self.stop()

    # ── Botão: Cancelar ───────────────────────────────────────────────────────
    @discord.ui.button(
        label="❌  Cancelar",
        style=discord.ButtonStyle.danger,
        custom_id="cancelar_cargo_btn",
    )
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(
            "🚫 Ação cancelada. Nenhum cargo foi atribuído.", ephemeral=True
        )
        self.stop()

    async def on_timeout(self):
        """Desativa os botões após o timeout."""
        for item in self.children:
            item.disabled = True


# ─── COG ───────────────────────────────────────────────────────────────────────
class Verificacao(commands.Cog):
    """Cog de verificação de cargo em massa e controle de permissões ADM."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        _criar_tabela_perm()

    # ─── /verm ───────────────────────────────────────────────────────────────
    @app_commands.command(
        name="verm",
        description="👥 Ver membros COM e SEM o cargo alvo. Opção de dar cargo aos que não têm. [ADM]"
    )
    async def verm(self, interaction: discord.Interaction):
        # ── Permissão ────────────────────────────────────────────────────────
        if not _tem_permissao(interaction):
            return await checks.sem_permissao(interaction)

        await interaction.response.defer(thinking=True)

        guild      = interaction.guild
        cargo_alvo = guild.get_role(CARGO_ALVO_ID)

        if cargo_alvo is None:
            return await interaction.followup.send(
                embed=utils.embed_erro(
                    "Cargo Não Encontrado",
                    f"O cargo alvo (ID `{CARGO_ALVO_ID}`) não existe neste servidor.\n"
                    "Verifique o ID em `commands/verificacao.py`."
                ),
                ephemeral=True,
            )

        # ── Carrega todos os membros (garante cache completo) ────────────────
        await guild.chunk()

        com_cargo:  list[discord.Member] = []
        sem_cargo:  list[discord.Member] = []

        for membro in guild.members:
            if membro.bot:
                continue   # Ignora bots
            if cargo_alvo in membro.roles:
                com_cargo.append(membro)
            else:
                sem_cargo.append(membro)

        total_humanos = len(com_cargo) + len(sem_cargo)

        # ── Embed principal ──────────────────────────────────────────────────
        cor = COR_SUCESSO if not sem_cargo else COR_AVISO

        embed = discord.Embed(
            title="👥  Verificação de Membros",
            color=cor,
            timestamp=datetime.utcnow(),
        )

        # Linha de resumo
        embed.description = (
            f"**Cargo verificado:** {cargo_alvo.mention}\n"
            f"**Total de humanos:** `{total_humanos}`  |  "
            f"**Com cargo:** `{len(com_cargo)}`  |  "
            f"**Sem cargo:** `{len(sem_cargo)}`"
        )

        # Campo: COM cargo
        embed.add_field(
            name=f"✅  Com o Cargo  ({len(com_cargo)})",
            value=_formatar_lista(com_cargo),
            inline=False,
        )

        # Campo: SEM cargo
        alerta = "⚠️" if sem_cargo else "✅"
        embed.add_field(
            name=f"{alerta}  Sem o Cargo  ({len(sem_cargo)})",
            value=_formatar_lista(sem_cargo),
            inline=False,
        )

        embed.set_footer(
            text=f"Solicitado por {interaction.user.display_name}  •  Bots ignorados",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_author(
            name=guild.name,
            icon_url=guild.icon.url if guild.icon else None,
        )

        # ── View com botão (só aparece se houver membros sem cargo) ──────────
        view = None
        if sem_cargo:
            view = ViewDarCargo(
                sem_cargo=sem_cargo,
                cargo_alvo=cargo_alvo,
                autor_id=interaction.user.id,
                bot=self.bot,
            )

        await interaction.followup.send(embed=embed, view=view)

    # ─── /verificar_cargo ────────────────────────────────────────────────────
    @app_commands.command(
        name="verificar_cargo",
        description="🔍 Atribui o cargo a TODOS os membros que não têm automaticamente. [ADM]"
    )
    async def verificar_cargo(self, interaction: discord.Interaction):
        # ── Permissão ────────────────────────────────────────────────────────
        if not _tem_permissao(interaction):
            return await checks.sem_permissao(interaction)

        await interaction.response.defer(thinking=True)

        guild      = interaction.guild
        cargo_alvo = guild.get_role(CARGO_ALVO_ID)

        if cargo_alvo is None:
            return await interaction.followup.send(
                embed=utils.embed_erro(
                    "Cargo Não Encontrado",
                    f"O cargo alvo (ID `{CARGO_ALVO_ID}`) não existe neste servidor."
                ),
                ephemeral=True,
            )

        await guild.chunk()

        sem_cargo: list[discord.Member] = []
        erros:     list[str] = []

        for membro in guild.members:
            if membro.bot:
                continue
            if cargo_alvo not in membro.roles:
                sem_cargo.append(membro)

        total_sem = len(sem_cargo)
        atribuidos = 0

        for membro in sem_cargo:
            try:
                await membro.add_roles(
                    cargo_alvo,
                    reason=f"Verificação automática por {interaction.user}"
                )
                atribuidos += 1
            except discord.Forbidden:
                erros.append(f"`{membro.display_name}` — sem permissão")
            except discord.HTTPException as e:
                erros.append(f"`{membro.display_name}` — erro: {e}")

        mencoes = _formatar_lista(sem_cargo)

        cor = COR_SUCESSO if not erros else COR_AVISO
        embed = discord.Embed(
            title="🔍  Verificação de Cargo Concluída",
            color=cor,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="👥 Total de Humanos",  value=f"`{len(guild.members)}`", inline=True)
        embed.add_field(name="⚠️ Sem o Cargo",       value=f"`{total_sem}`",          inline=True)
        embed.add_field(name="✅ Cargo Atribuído",   value=f"`{atribuidos}`",          inline=True)
        embed.add_field(name="🏷️ Cargo Alvo",        value=cargo_alvo.mention,        inline=False)
        embed.add_field(name="📋 Membros atualizados", value=mencoes,                 inline=False)

        if erros:
            embed.add_field(name="❌ Erros", value="\n".join(erros[:10]), inline=False)

        embed.set_footer(
            text=f"Executado por {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_author(
            name=guild.name,
            icon_url=guild.icon.url if guild.icon else None,
        )

        await interaction.followup.send(embed=embed)

        await utils.enviar_log(
            self.bot,
            "Verificação de Cargo",
            (
                f"**Cargo:** {cargo_alvo.mention}\n"
                f"**Total sem cargo:** `{total_sem}`\n"
                f"**Atribuídos:** `{atribuidos}`\n"
                f"**Executado por:** {interaction.user.mention}"
            ),
            cor=cor,
        )

    # ─── /add_adm ────────────────────────────────────────────────────────────
    @app_commands.command(
        name="add_adm",
        description="🛡️ Concede permissão dos comandos de verificação a um cargo. [Apenas Fundador]"
    )
    @app_commands.describe(cargo="Cargo que receberá permissão")
    async def add_adm(self, interaction: discord.Interaction, cargo: discord.Role):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        if cargo.id in CARGOS_FIXOS_PERM:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Cargo Já Privilegiado",
                    f"{cargo.mention} já tem permissão permanente."
                ),
                ephemeral=True,
            )

        sucesso = _add_cargo_adm(cargo.id)

        if not sucesso:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Cargo Já na Lista",
                    f"{cargo.mention} já está na lista de permissões."
                ),
                ephemeral=True,
            )

        embed = discord.Embed(
            title="🛡️  Permissão ADM Concedida",
            description=(
                f"O cargo {cargo.mention} agora pode usar `/verm` e `/verificar_cargo`.\n\n"
                f"Para remover, use `/remove_adm`."
            ),
            color=COR_SUCESSO,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="🏷️ Cargo",        value=cargo.mention,            inline=True)
        embed.add_field(name="👮 Concedido por", value=interaction.user.mention, inline=True)
        embed.set_footer(text="⚔️ Sistema de Permissões de Verificação")

        await interaction.response.send_message(embed=embed)

        await utils.enviar_log(
            self.bot,
            "Permissão ADM Concedida",
            (
                f"**Cargo:** {cargo.mention} (`{cargo.id}`)\n"
                f"**Concedido por:** {interaction.user.mention}"
            ),
            cor=COR_SUCESSO,
        )

    # ─── /remove_adm ─────────────────────────────────────────────────────────
    @app_commands.command(
        name="remove_adm",
        description="🔒 Remove permissão dos comandos de verificação de um cargo. [Apenas Fundador]"
    )
    @app_commands.describe(cargo="Cargo que perderá a permissão")
    async def remove_adm(self, interaction: discord.Interaction, cargo: discord.Role):
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        if cargo.id in CARGOS_FIXOS_PERM:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Cargo Permanente",
                    f"{cargo.mention} tem permissão permanente e **não pode** ser removido."
                ),
                ephemeral=True,
            )

        removido = _remove_cargo_adm(cargo.id)

        if not removido:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Cargo Não Encontrado",
                    f"{cargo.mention} não está na lista. Use `/add_adm` para adicionar."
                ),
                ephemeral=True,
            )

        embed = discord.Embed(
            title="🔒  Permissão ADM Removida",
            description=f"O cargo {cargo.mention} **não pode mais** usar os comandos de verificação.",
            color=COR_ERRO,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="🏷️ Cargo",       value=cargo.mention,            inline=True)
        embed.add_field(name="👮 Removido por", value=interaction.user.mention, inline=True)
        embed.set_footer(text="⚔️ Sistema de Permissões de Verificação")

        await interaction.response.send_message(embed=embed)

        await utils.enviar_log(
            self.bot,
            "Permissão ADM Removida",
            (
                f"**Cargo:** {cargo.mention} (`{cargo.id}`)\n"
                f"**Removido por:** {interaction.user.mention}"
            ),
            cor=COR_ERRO,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Verificacao(bot))
