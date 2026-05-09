"""
commands/aviso.py - Comando de aviso oficial da facção
/aviso  → Apenas liderança pode usar.
         Envia um anúncio visual SEMPRE no canal de avisos configurado.

Lógica de menção:
  - marcar_todos = True  → menciona apenas @everyone
  - marcar_todos = False → admin escolhe até 3 cargos específicos (cargo1, cargo2, cargo3)
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

import checks
import utils
from config import CANAL_AVISOS_ID


# ─── TEMAS POR NÍVEL DE URGÊNCIA ──────────────────────────────────────────────
TEMAS = {
    "normal": {
        "cor":    0x57F287,          # Verde Discord
        "badge":  "📢",
        "label":  "AVISO OFICIAL",
        "banner": "🟢 COMUNICADO OFICIAL",
        "emoji":  "✅",
    },
    "importante": {
        "cor":    0xFEE75C,          # Amarelo Discord
        "badge":  "⚠️",
        "label":  "AVISO IMPORTANTE",
        "banner": "🟡 ATENÇÃO — LEIA COM CUIDADO",
        "emoji":  "⚠️",
    },
    "urgente": {
        "cor":    0xED4245,          # Vermelho Discord
        "badge":  "🚨",
        "label":  "AVISO URGENTE",
        "banner": "🔴 URGENTE — AÇÃO IMEDIATA NECESSÁRIA",
        "emoji":  "🚨",
    },
}


class Aviso(commands.Cog):
    """Cog responsável pelo comando de aviso oficial da facção."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── /aviso ────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="aviso",
        description="📢 Envia um aviso oficial no canal de avisos. [Apenas Liderança]"
    )
    @app_commands.describe(
        titulo="Título do aviso (ex: Reunião Obrigatória)",
        mensagem="Texto completo do aviso",
        urgencia="Nível de urgência do aviso",
        marcar_todos="Marcar @everyone? Se Não, escolha os cargos abaixo.",
        cargo1="1º cargo específico a ser mencionado (opcional)",
        cargo2="2º cargo específico a ser mencionado (opcional)",
        cargo3="3º cargo específico a ser mencionado (opcional)",
    )
    @app_commands.choices(urgencia=[
        app_commands.Choice(name="🟢 Normal",     value="normal"),
        app_commands.Choice(name="🟡 Importante", value="importante"),
        app_commands.Choice(name="🔴 Urgente",    value="urgente"),
    ])
    async def aviso(
        self,
        interaction: discord.Interaction,
        titulo: str,
        mensagem: str,
        urgencia: app_commands.Choice[str] = None,
        marcar_todos: bool = True,
        cargo1: discord.Role = None,
        cargo2: discord.Role = None,
        cargo3: discord.Role = None,
    ):
        # ── Verificação de permissão ────────────────────────────────────────────
        if not checks.is_lideranca(interaction):
            return await checks.sem_permissao(interaction)

        # ── Validação: se não marcou todos mas também não escolheu nenhum cargo ─
        if not marcar_todos and not any([cargo1, cargo2, cargo3]):
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Nenhum Cargo Selecionado",
                    "Você escolheu **Não** para `marcar_todos`, mas não selecionou nenhum cargo.\n"
                    "Por favor, informe pelo menos um cargo em `cargo1`, `cargo2` ou `cargo3`.\n\n"
                    "Ou ative `marcar_todos` para usar **@everyone**."
                ),
                ephemeral=True,
            )

        # ── Tema com base na urgência ───────────────────────────────────────────
        nivel = urgencia.value if urgencia else "normal"
        tema  = TEMAS[nivel]

        # ── Busca o canal de avisos ─────────────────────────────────────────────
        canal_avisos = interaction.guild.get_channel(CANAL_AVISOS_ID)
        if canal_avisos is None:
            return await interaction.response.send_message(
                embed=utils.embed_erro(
                    "Canal Não Encontrado",
                    f"O canal de avisos (ID `{CANAL_AVISOS_ID}`) não foi encontrado.\n"
                    "Verifique o ID em `config.py`."
                ),
                ephemeral=True,
            )

        # ── Monta menções ───────────────────────────────────────────────────────
        if marcar_todos:
            # Menciona todos com @everyone (mais limpo, sem spam de cargos)
            mencoes = "@everyone"
        else:
            # Menciona apenas os cargos escolhidos pelo admin
            cargos_escolhidos = [c for c in [cargo1, cargo2, cargo3] if c is not None]
            mencoes = " ".join(role.mention for role in cargos_escolhidos)

        # ── Timestamp Unix para formato Discord ─────────────────────────────────
        agora_ts = int(datetime.utcnow().timestamp())

        # ── Descrição dos cargos marcados (para o embed) ─────────────────────────
        if marcar_todos:
            cargos_info = "**@everyone** (todos)"
        else:
            cargos_info = " ".join(role.mention for role in cargos_escolhidos)

        # ── Embed principal (visual premium) ────────────────────────────────────
        embed = discord.Embed(color=tema["cor"], timestamp=datetime.utcnow())

        # Cabeçalho com banner decorativo
        embed.description = (
            f"```\n"
            f"{'═' * 38}\n"
            f"  {tema['banner']}\n"
            f"{'═' * 38}\n"
            f"```\n"
            f"### {tema['badge']}  {titulo.upper()}\n\n"
            f"{mensagem}\n\n"
            f"```\n{'─' * 38}\n```"
        )

        # Campos de metadados em linha
        embed.add_field(
            name="👮 Emitido por",
            value=interaction.user.mention,
            inline=True,
        )
        embed.add_field(
            name="📅 Data & Hora",
            value=f"<t:{agora_ts}:F>",
            inline=True,
        )
        embed.add_field(
            name="⚡ Nível",
            value=f"```{tema['label']}```",
            inline=True,
        )
        embed.add_field(
            name="🎯 Marcados",
            value=cargos_info,
            inline=False,
        )

        # Avatar do autor como thumbnail
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        # Author com ícone do servidor
        if interaction.guild.icon:
            embed.set_author(
                name=f"{interaction.guild.name}  ·  Comunicado Oficial",
                icon_url=interaction.guild.icon.url,
            )
        else:
            embed.set_author(name=f"{interaction.guild.name}  ·  Comunicado Oficial")

        # Footer
        embed.set_footer(
            text="⚔️ Facção Bot  •  Comunicados Oficiais",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None,
        )

        # ── Confirmação efêmera ao admin ────────────────────────────────────────
        await interaction.response.send_message(
            embed=utils.embed_sucesso(
                "Aviso Publicado!",
                f"O aviso **{titulo}** foi enviado em {canal_avisos.mention}.\n"
                f"Marcados: {cargos_info}"
            ),
            ephemeral=True,
        )

        # ── Envia no canal de avisos ────────────────────────────────────────────
        await canal_avisos.send(
            content=mencoes,
            embed=embed,
        )

        # ── Log ─────────────────────────────────────────────────────────────────
        await utils.enviar_log(
            self.bot,
            "Aviso Emitido",
            (
                f"**Titulo:** {titulo}\n"
                f"**Nivel:** {tema['label']}\n"
                f"**Mensagem:** {mensagem}\n"
                f"**Emitido por:** {interaction.user.display_name}\n"
                f"**Canal:** {canal_avisos.mention}\n"
                f"**Marcados:** {cargos_info}"
            ),
            cor=tema["cor"],
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Aviso(bot))
