"""
commands/clonar.py - Comando /clonar
Copia a estrutura COMPLETA de um servidor para outro:
  • Nome, ícone, banner e descrição do servidor
  • Cargos       — cor, permissões, hoist, mentionable
  • Categorias   — com permission overwrites mapeados
  • Canais       — texto, voz, fórum (+ tags), stage
  • Mensagens    — via webhook (nome + avatar do autor original)
  • Anexos       — re-upload de arquivos das mensagens
  • Emojis       — imagem + nome
  • Stickers     — imagem + nome + descrição
"""

import asyncio
from io import BytesIO

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from config import COR_AVISO, COR_ERRO, COR_SUCESSO


# ─── HELPER: baixar bytes de URL ────────────────────────────────────────────────
async def _baixar(session: aiohttp.ClientSession, url: str) -> bytes | None:
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
    except Exception:
        pass
    return None


# ─── HELPER: converte overwrites antigos → novos ────────────────────────────────
def _mapear_overwrites(overwrites, mapa_cargos, destino):
    novos = {}
    for alvo, perms in overwrites.items():
        if isinstance(alvo, discord.Role):
            if alvo.name == "@everyone":
                novos[destino.default_role] = perms
            elif alvo.id in mapa_cargos:
                novos[mapa_cargos[alvo.id]] = perms
    return novos


# ─── HELPER: copiar mensagens de um canal via webhook ───────────────────────────
async def _copiar_mensagens(
    canal_origem: discord.TextChannel,
    canal_destino: discord.TextChannel,
    session: aiohttp.ClientSession,
    limite: int,
    log,
):
    try:
        webhook = await canal_destino.create_webhook(name="Clonar Bot")
    except Exception as ex:
        await log(f"Webhook falhou em #{canal_origem.name}: {ex}", ok=False)
        return

    try:
        mensagens = [m async for m in canal_origem.history(limit=limite, oldest_first=True)]
    except Exception as ex:
        await log(f"Histórico falhou em #{canal_origem.name}: {ex}", ok=False)
        await webhook.delete()
        return

    for msg in mensagens:
        try:
            # Re-upload de anexos
            files = []
            for anexo in msg.attachments:
                data = await _baixar(session, anexo.url)
                if data and len(data) < 8_000_000:  # limite 8MB
                    files.append(discord.File(BytesIO(data), filename=anexo.filename))

            conteudo = msg.content or ""

            # Embeds (apenas os que não são gerados pelo Discord automaticamente)
            embeds = [e for e in msg.embeds if e.type == "rich"]

            if not conteudo and not files and not embeds:
                continue  # mensagem vazia (ex: só sticker) — pula

            await webhook.send(
                content=conteudo[:2000] if conteudo else None,
                username=msg.author.display_name[:80],
                avatar_url=msg.author.display_avatar.url,
                files=files if files else discord.utils.MISSING,
                embeds=embeds[:10] if embeds else discord.utils.MISSING,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            await asyncio.sleep(0.6)

        except Exception as ex:
            await log(f"Msg falhou em #{canal_origem.name}: {ex}", ok=False)

    try:
        await webhook.delete()
    except Exception:
        pass

    await log(f"Mensagens: **#{canal_origem.name}** ({len(mensagens)} msg)")


# ─── COG ────────────────────────────────────────────────────────────────────────
class Clonar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="clonar",
        description="📋 Copia TUDO de um servidor para outro (cargos, canais, mensagens, emojis…).",
    )
    @app_commands.describe(
        origem_id="ID do servidor a ser copiado (o bot deve estar lá)",
        destino_id="ID do servidor de destino (o bot deve ser admin lá)",
        limite_mensagens="Quantas mensagens copiar por canal (padrão: 100, máximo: 500)",
    )
    async def clonar(
        self,
        interaction: discord.Interaction,
        origem_id: str,
        destino_id: str,
        limite_mensagens: app_commands.Range[int, 1, 500] = 100,
    ):
        # ── Apenas o dono pode usar ─────────────────────────────────────────────
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "❌ Apenas o **dono do servidor** pode usar este comando.", ephemeral=True
            )
            return

        # ── Valida origem ───────────────────────────────────────────────────────
        try:
            origem_id_int = int(origem_id)
        except ValueError:
            await interaction.response.send_message("❌ ID de origem inválido.", ephemeral=True)
            return

        origem: discord.Guild | None = self.bot.get_guild(origem_id_int)
        if not origem:
            await interaction.response.send_message(
                "❌ Bot não está no servidor de **origem** ou ID incorreto.", ephemeral=True
            )
            return

        # ── Valida destino ──────────────────────────────────────────────────────
        try:
            destino_id_int = int(destino_id)
        except ValueError:
            await interaction.response.send_message("❌ ID de destino inválido.", ephemeral=True)
            return

        destino: discord.Guild | None = self.bot.get_guild(destino_id_int)
        if not destino:
            await interaction.response.send_message(
                "❌ Bot não está no servidor de **destino** ou ID incorreto.", ephemeral=True
            )
            return
        if destino.id == origem.id:
            await interaction.response.send_message(
                "❌ Origem e destino não podem ser o mesmo servidor.", ephemeral=True
            )
            return
        if not destino.me.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ O bot precisa de **Administrador** no servidor de destino.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        linhas: list[str] = []
        embed = discord.Embed(
            title="📋 Clonando Servidor…",
            description="Iniciando…",
            color=COR_AVISO,
        )
        embed.set_footer(text=f"Destino: {destino.name} ({destino.id})")
        msg = await interaction.followup.send(embed=embed, wait=True)

        async def log(texto: str, ok: bool = True):
            linhas.append(("✅" if ok else "⚠️") + " " + texto)
            embed.description = "\n".join(linhas[-18:])
            try:
                await msg.edit(embed=embed)
            except Exception:
                pass

        async with aiohttp.ClientSession() as session:

            # ══════════════════════════════════════════════════════════════════
            #  ETAPA 0 — LIMPEZA DO SERVIDOR DE DESTINO
            # ══════════════════════════════════════════════════════════════════
            embed.title = "🗑️ Limpando servidor de destino…"

            # Apaga todos os canais
            for canal in list(destino.channels):
                try:
                    await canal.delete(reason="Limpeza antes da clonagem")
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            await log("Canais apagados")

            # Apaga todos os cargos (exceto @everyone e cargos gerenciados pelo Discord)
            for cargo in list(destino.roles):
                if cargo.name == "@everyone" or cargo.managed:
                    continue
                try:
                    await cargo.delete(reason="Limpeza antes da clonagem")
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            await log("Cargos apagados")

            # Apaga todos os emojis
            for emoji in list(destino.emojis):
                try:
                    await emoji.delete(reason="Limpeza antes da clonagem")
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            await log("Emojis apagados")

            # Apaga todos os stickers
            for sticker in list(destino.stickers):
                try:
                    await sticker.delete(reason="Limpeza antes da clonagem")
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            await log("Stickers apagados")

            # ══════════════════════════════════════════════════════════════════
            #  ETAPA 1 — CARGOS
            # ══════════════════════════════════════════════════════════════════
            embed.title = "📋 Clonando… [1/4] Cargos"
            mapa_cargos: dict[int, discord.Role] = {}

            for cargo in sorted(origem.roles[1:], key=lambda r: r.position):
                try:
                    novo = await destino.create_role(
                        name=cargo.name,
                        color=cargo.color,
                        permissions=cargo.permissions,
                        hoist=cargo.hoist,
                        mentionable=cargo.mentionable,
                        reason="Clonagem de servidor",
                    )
                    mapa_cargos[cargo.id] = novo
                    await log(f"Cargo: **{cargo.name}**")
                except Exception as ex:
                    await log(f"Cargo falhou — {cargo.name}: {ex}", ok=False)
                await asyncio.sleep(0.4)

            # ══════════════════════════════════════════════════════════════════
            #  ETAPA 3 — CATEGORIAS + CANAIS + MENSAGENS
            # ══════════════════════════════════════════════════════════════════
            embed.title = "📋 Clonando… [2/4] Canais + Mensagens"
            mapa_categorias: dict[int, discord.CategoryChannel] = {}
            # mapa canal origem → canal destino (para copiar mensagens depois)
            mapa_canais_texto: list[tuple[discord.TextChannel, discord.TextChannel]] = []

            # Cria categorias
            for cat in sorted(origem.categories, key=lambda c: c.position):
                try:
                    ow = _mapear_overwrites(cat.overwrites, mapa_cargos, destino)
                    nova_cat = await destino.create_category(
                        name=cat.name, overwrites=ow, reason="Clonagem de servidor"
                    )
                    mapa_categorias[cat.id] = nova_cat
                    await log(f"Categoria: **{cat.name}**")
                except Exception as ex:
                    await log(f"Categoria falhou — {cat.name}: {ex}", ok=False)
                await asyncio.sleep(0.4)

            # Função criar canal
            async def criar_canal(canal, cat_dest):
                ow = _mapear_overwrites(canal.overwrites, mapa_cargos, destino)
                try:
                    if isinstance(canal, discord.TextChannel):
                        novo = await destino.create_text_channel(
                            name=canal.name,
                            category=cat_dest,
                            topic=canal.topic,
                            slowmode_delay=canal.slowmode_delay,
                            nsfw=canal.is_nsfw(),
                            overwrites=ow,
                            reason="Clonagem de servidor",
                        )
                        mapa_canais_texto.append((canal, novo))
                        await log(f"Texto: **#{canal.name}**")

                    elif isinstance(canal, discord.VoiceChannel):
                        await destino.create_voice_channel(
                            name=canal.name,
                            category=cat_dest,
                            bitrate=min(canal.bitrate, destino.bitrate_limit),
                            user_limit=canal.user_limit,
                            overwrites=ow,
                            reason="Clonagem de servidor",
                        )
                        await log(f"Voz: **🔊 {canal.name}**")

                    elif isinstance(canal, discord.ForumChannel):
                        tags = [
                            discord.ForumTag(
                                name=t.name, emoji=t.emoji, moderated=t.moderated
                            )
                            for t in canal.available_tags
                        ]
                        await destino.create_forum(
                            name=canal.name,
                            category=cat_dest,
                            topic=canal.topic or "",
                            slowmode_delay=canal.slowmode_delay,
                            nsfw=canal.is_nsfw(),
                            available_tags=tags,
                            overwrites=ow,
                            reason="Clonagem de servidor",
                        )
                        await log(f"Fórum: **#{canal.name}** ({len(tags)} tag(s))")

                    elif isinstance(canal, discord.StageChannel):
                        await destino.create_stage_channel(
                            name=canal.name,
                            category=cat_dest,
                            overwrites=ow,
                            reason="Clonagem de servidor",
                        )
                        await log(f"Stage: **{canal.name}**")

                except Exception as ex:
                    await log(f"Canal falhou — {canal.name}: {ex}", ok=False)
                await asyncio.sleep(0.4)

            # Canais sem categoria
            sem_cat = [
                c for c in origem.channels
                if c.category is None and not isinstance(c, discord.CategoryChannel)
            ]
            for canal in sorted(sem_cat, key=lambda c: c.position):
                await criar_canal(canal, None)

            # Canais dentro de categorias
            for cat in sorted(origem.categories, key=lambda c: c.position):
                nova_cat = mapa_categorias.get(cat.id)
                for canal in sorted(cat.channels, key=lambda c: c.position):
                    await criar_canal(canal, nova_cat)

            # Copia mensagens de cada canal de texto
            embed.title = "📋 Clonando… [2/4] Mensagens"
            for canal_orig, canal_dest in mapa_canais_texto:
                await _copiar_mensagens(
                    canal_orig, canal_dest, session, limite_mensagens, log
                )

            # ══════════════════════════════════════════════════════════════════
            #  ETAPA 4 — EMOJIS
            # ══════════════════════════════════════════════════════════════════
            embed.title = "📋 Clonando… [3/4] Emojis"

            for emoji in origem.emojis:
                try:
                    data = await _baixar(session, str(emoji.url))
                    if data:
                        await destino.create_custom_emoji(
                            name=emoji.name, image=data, reason="Clonagem de servidor"
                        )
                        await log(f"Emoji: **:{emoji.name}:**")
                except Exception as ex:
                    await log(f"Emoji falhou — :{emoji.name}:: {ex}", ok=False)
                await asyncio.sleep(0.8)

            # ══════════════════════════════════════════════════════════════════
            #  ETAPA 5 — STICKERS
            # ══════════════════════════════════════════════════════════════════
            embed.title = "📋 Clonando… [4/4] Stickers"

            for sticker_ref in origem.stickers:
                try:
                    sticker = await sticker_ref.fetch()
                    data = await _baixar(session, sticker.url)
                    if data:
                        arquivo = discord.File(
                            BytesIO(data), filename=f"{sticker.name}.png"
                        )
                        await destino.create_sticker(
                            name=sticker.name,
                            description=sticker.description or sticker.name,
                            emoji=sticker.emoji,
                            file=arquivo,
                            reason="Clonagem de servidor",
                        )
                        await log(f"Sticker: **{sticker.name}**")
                except Exception as ex:
                    await log(f"Sticker falhou — {sticker_ref.name}: {ex}", ok=False)
                await asyncio.sleep(1.0)

        # ── Finalizado ──────────────────────────────────────────────────────────
        total_ok    = sum(1 for l in linhas if "✅" in l)
        total_falha = sum(1 for l in linhas if "⚠️" in l)

        embed.title = "✅ Clonagem Concluída!"
        embed.color = COR_SUCESSO
        embed.description = "\n".join(linhas[-18:])
        embed.add_field(
            name="📊 Resumo",
            value=(
                f"**✅ Itens copiados:** {total_ok}\n"
                f"**⚠️ Falhas:** {total_falha}\n"
                f"**💬 Msgs por canal:** até {limite_mensagens}"
            ),
            inline=False,
        )
        await msg.edit(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Clonar(bot))
