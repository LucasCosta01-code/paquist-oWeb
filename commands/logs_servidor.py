"""
commands/logs_servidor.py - Sistema completo de logs do servidor
Registra TUDO que acontece no servidor em tempo real:

  ── MEMBROS ──────────────────────────────────────────────────────
  • Entrou no servidor         • Saiu do servidor
  • Nome/apelido alterado      • Avatar alterado
  • Cargo adicionado           • Cargo removido
  • Banido                     • Desbanido

  ── MENSAGENS ────────────────────────────────────────────────────
  • Mensagem apagada           • Mensagem editada
  • Bulk delete (purge)

  ── CANAIS ───────────────────────────────────────────────────────
  • Canal criado               • Canal apagado
  • Canal renomeado/editado

  ── CARGOS ───────────────────────────────────────────────────────
  • Cargo criado               • Cargo apagado
  • Cargo editado

  ── VOZ ──────────────────────────────────────────────────────────
  • Entrou em canal de voz     • Saiu de canal de voz
  • Movido de canal
  • Mutado/desmutado (servidor)

  ── SERVIDOR ─────────────────────────────────────────────────────
  • Configurações do servidor alteradas
  • Invite criado / deletado
"""

import discord
from discord.ext import commands
from datetime import datetime, timezone

from config import LOG_CANAL_SERVIDOR_ID


# ─── CORES POR CATEGORIA ───────────────────────────────────────────────────────
COR_ENTRADA   = 0x57F287   # Verde  — entrou
COR_SAIDA     = 0xED4245   # Vermelho — saiu / apagado
COR_EDICAO    = 0xFEE75C   # Amarelo — editado
COR_CARGO     = 0x5865F2   # Azul Discord — cargos
COR_CANAL     = 0xEB459E   # Rosa — canais
COR_VOZ       = 0x9B59B6   # Roxo — voz
COR_BAN       = 0xFF0000   # Vermelho forte — ban
COR_SERVIDOR  = 0x95A5A6   # Cinza — servidor geral


def _ts() -> str:
    """Timestamp formatado para o footer."""
    return datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


def _embed(titulo: str, cor: int, descricao: str = "") -> discord.Embed:
    """Cria um embed de log padronizado e estético."""
    # Adiciona uma linha separadora se houver descrição
    corpo = f"{descricao}\n\n{'─' * 42}" if descricao else f"{'─' * 42}"
    
    e = discord.Embed(title=titulo, description=corpo, color=cor)
    e.timestamp = datetime.now(timezone.utc)
    e.set_footer(text="📋 Sistema de Monitoramento • Paquistão Web")
    return e


class LogsServidor(commands.Cog):
    """Cog que escuta todos os eventos do servidor e os loga."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _enviar(self, embed: discord.Embed):
        """Envia o embed no canal de log do servidor."""
        if not LOG_CANAL_SERVIDOR_ID:
            return
        canal = self.bot.get_channel(LOG_CANAL_SERVIDOR_ID)
        if canal:
            try:
                await canal.send(embed=embed)
            except discord.Forbidden:
                pass  # Bot sem permissão para enviar no canal de log

    # ══════════════════════════════════════════════════════════════════════════════
    #   MEMBROS
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Membro entrou no servidor."""
        conta_criada = f"<t:{int(member.created_at.timestamp())}:R>"
        e = _embed("📥  Membro Entrou", COR_ENTRADA)
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="👤 Usuário",        value=f"{member.mention} (`{member.id}`)", inline=False)
        e.add_field(name="🏷️ Nome completo",  value=str(member),                         inline=True)
        e.add_field(name="📅 Conta criada",   value=conta_criada,                        inline=True)
        e.add_field(name="👥 Total membros",  value=str(member.guild.member_count),       inline=True)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Membro saiu ou foi kickado do servidor."""
        responsavel = None
        motivo = None
        try:
            # Verifica se foi um kick recente
            async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    # Verifica se o kick aconteceu nos últimos 10 segundos
                    if (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
                        responsavel = entry.user
                        motivo = entry.reason
                        break
        except Exception:
            pass

        if responsavel:
            e = _embed("👢  Membro Expulso (Kick)", COR_SAIDA)
            e.add_field(name="👮 Responsável", value=f"{responsavel.mention} (`{responsavel.id}`)", inline=True)
            e.add_field(name="📝 Motivo",      value=motivo or "Não especificado",                inline=False)
        else:
            e = _embed("📤  Membro Saiu", COR_SAIDA)
        
        cargos = [r.mention for r in member.roles if r.name != "@everyone"]
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="👤 Usuário",      value=f"{member.mention} (`{member.id}`)",               inline=False)
        e.add_field(name="🏷️ Nome",         value=str(member),                                        inline=True)
        e.add_field(name="👥 Total agora",  value=str(member.guild.member_count),                     inline=True)
        e.add_field(name="🎭 Cargos",       value=" ".join(cargos) if cargos else "Nenhum",           inline=False)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Nickname, cargos ou outros dados do membro mudaram."""

        # ── Cargo adicionado/removido ───────────────────────────────────────────
        cargos_add = [r for r in after.roles  if r not in before.roles]
        cargos_rem = [r for r in before.roles if r not in after.roles]

        if cargos_add or cargos_rem:
            responsavel = "Desconhecido"
            try:
                # Busca quem alterou os cargos
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                    if entry.target.id == after.id:
                        responsavel = f"{entry.user.mention} (`{entry.user.id}`)"
                        break
            except Exception:
                pass

            for cargo in cargos_add:
                e = _embed("🟢  Cargo Adicionado", COR_CARGO)
                e.set_thumbnail(url=after.display_avatar.url)
                e.add_field(name="👤 Usuário",     value=f"{after.mention} (`{after.id}`)", inline=True)
                e.add_field(name="➕ Cargo",       value=cargo.mention,                     inline=True)
                e.add_field(name="👮 Responsável", value=responsavel,                       inline=False)
                await self._enviar(e)

            for cargo in cargos_rem:
                e = _embed("🔴  Cargo Removido", COR_CARGO)
                e.set_thumbnail(url=after.display_avatar.url)
                e.add_field(name="👤 Usuário",     value=f"{after.mention} (`{after.id}`)", inline=True)
                e.add_field(name="➖ Cargo",       value=cargo.mention,                     inline=True)
                e.add_field(name="👮 Responsável", value=responsavel,                       inline=False)
                await self._enviar(e)

        # ── Nickname alterado ───────────────────────────────────────────────────
        if before.nick != after.nick:
            e = _embed("✏️  Apelido Alterado", COR_EDICAO)
            e.set_thumbnail(url=after.display_avatar.url)
            e.add_field(name="👤 Usuário",   value=f"{after.mention} (`{after.id}`)", inline=False)
            e.add_field(name="📝 Antes",     value=before.nick or "*sem apelido*",    inline=True)
            e.add_field(name="📝 Depois",    value=after.nick  or "*sem apelido*",    inline=True)
            await self._enviar(e)

        # ── Timeout aplicado / removido ─────────────────────────────────────────
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                ts = f"<t:{int(after.timed_out_until.timestamp())}:R>"
                e = _embed("⏱️  Timeout Aplicado", COR_BAN)
                e.set_thumbnail(url=after.display_avatar.url)
                e.add_field(name="👤 Usuário", value=f"{after.mention} (`{after.id}`)", inline=True)
                e.add_field(name="⏰ Expira",  value=ts,                                inline=True)
            else:
                e = _embed("✅  Timeout Removido", COR_ENTRADA)
                e.set_thumbnail(url=after.display_avatar.url)
                e.add_field(name="👤 Usuário", value=f"{after.mention} (`{after.id}`)", inline=True)
            await self._enviar(e)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Nome global ou avatar de um usuário mudou."""
        if before.name != after.name or before.global_name != after.global_name:
            e = _embed("✏️  Nome de Usuário Alterado", COR_EDICAO)
            e.set_thumbnail(url=after.display_avatar.url)
            e.add_field(name="🆔 ID",       value=str(after.id),  inline=False)
            e.add_field(name="📝 Antes",    value=str(before),     inline=True)
            e.add_field(name="📝 Depois",   value=str(after),      inline=True)
            await self._enviar(e)

        if before.avatar != after.avatar:
            e = _embed("🖼️  Avatar Alterado", COR_EDICAO)
            e.set_thumbnail(url=after.display_avatar.url)
            e.add_field(name="👤 Usuário",  value=f"{after.mention} (`{after.id}`)", inline=False)
            if before.avatar:
                e.set_image(url=before.display_avatar.url)
            await self._enviar(e)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Usuário foi banido."""
        responsavel = "Desconhecido"
        motivo = "Não especificado"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    responsavel = f"{entry.user.mention} (`{entry.user.id}`)"
                    motivo = entry.reason or "Não especificado"
                    break
        except Exception:
            pass

        e = _embed("🔨  Usuário Banido", COR_BAN)
        e.set_thumbnail(url=user.display_avatar.url)
        e.add_field(name="👤 Usuário",     value=f"{user.mention} (`{user.id}`)", inline=True)
        e.add_field(name="👮 Responsável", value=responsavel,                     inline=True)
        e.add_field(name="📝 Motivo",      value=motivo,                          inline=False)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Usuário foi desbanido."""
        responsavel = "Desconhecido"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.unban):
                if entry.target.id == user.id:
                    responsavel = f"{entry.user.mention} (`{entry.user.id}`)"
                    break
        except Exception:
            pass

        e = _embed("✅  Usuário Desbanido", COR_ENTRADA)
        e.set_thumbnail(url=user.display_avatar.url)
        e.add_field(name="👤 Usuário",     value=f"{user.mention} (`{user.id}`)", inline=True)
        e.add_field(name="👮 Responsável", value=responsavel,                     inline=True)
        await self._enviar(e)

    # ══════════════════════════════════════════════════════════════════════════════
    #   MENSAGENS
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Mensagem foi apagada."""
        if message.author.bot:
            return  # Ignora bots
        if not message.guild:
            return  # Ignora DMs

        e = _embed("🗑️  Mensagem Apagada", COR_SAIDA)
        e.set_thumbnail(url=message.author.display_avatar.url)
        e.add_field(name="👤 Autor",   value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        e.add_field(name="📌 Canal",   value=message.channel.mention,                             inline=True)

        # Conteúdo (pode ser vazio se for embed/arquivo)
        conteudo = message.content or "*[Mensagem sem texto — pode ser apenas arquivo, imagem ou embed]*"
        if len(conteudo) > 1020:
            conteudo = conteudo[:1020] + "..."
        e.add_field(name="💬 Conteúdo Apagado", value=f"```\n{conteudo}\n```", inline=False)

        # Anexos
        if message.attachments:
            nomes = "\n".join(a.filename for a in message.attachments)
            e.add_field(name="📎 Anexos", value=nomes, inline=False)

        await self._enviar(e)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        """Múltiplas mensagens foram apagadas de uma vez (ex: /limpar)."""
        if not messages:
            return
        canal = messages[0].channel
        e = _embed("🗑️  Purge — Mensagens em Massa Apagadas", COR_SAIDA)
        e.add_field(name="📌 Canal",      value=canal.mention,        inline=True)
        e.add_field(name="🔢 Quantidade", value=str(len(messages)),   inline=True)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Mensagem foi editada."""
        if before.author.bot:
            return
        if not before.guild:
            return
        if before.content == after.content:
            return  # Edição sem mudança de texto (ex: embed gerado)

        e = _embed("✏️  Mensagem Editada", COR_EDICAO)
        e.set_thumbnail(url=before.author.display_avatar.url)
        e.add_field(name="👤 Autor",   value=f"{before.author.mention} (`{before.author.id}`)", inline=True)
        e.add_field(name="📌 Canal",   value=before.channel.mention,                            inline=True)
        e.add_field(name="🔗 Link",    value=f"[Ir para mensagem]({after.jump_url})",           inline=True)

        antes = before.content or "*[Vazio ou apenas mídia]*"
        depois = after.content or "*[Vazio ou apenas mídia]*"
        
        if len(antes) > 1020:
            antes = antes[:1020] + "..."
        if len(depois) > 1020:
            depois = depois[:1020] + "..."

        e.add_field(name="📝 Antes",  value=f"```\n{antes}\n```",  inline=False)
        e.add_field(name="📝 Depois", value=f"```\n{depois}\n```", inline=False)
        await self._enviar(e)

    # ══════════════════════════════════════════════════════════════════════════════
    #   CANAIS
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Canal criado."""
        responsavel = "Desconhecido"
        try:
            async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    responsavel = f"{entry.user.mention} (`{entry.user.id}`)"
                    break
        except Exception:
            pass

        tipo = type(channel).__name__.replace("Channel", "").replace("Thread", "Thread")
        e = _embed("📁  Canal Criado", COR_CANAL)
        e.add_field(name="📌 Canal",       value=f"{channel.mention} (`{channel.id}`)", inline=True)
        e.add_field(name="🔎 Tipo",        value=tipo,                                  inline=True)
        e.add_field(name="👮 Responsável", value=responsavel,                         inline=False)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Canal apagado."""
        responsavel = "Desconhecido"
        try:
            # Busca nos logs de auditoria quem apagou
            async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    responsavel = f"{entry.user.mention} (`{entry.user.id}`)"
                    break
        except Exception:
            pass

        e = _embed("🗑️  Canal Apagado", COR_SAIDA)
        e.add_field(name="📌 Nome", value=f"`#{channel.name}` (`{channel.id}`)", inline=True)
        e.add_field(name="👮 Responsável", value=responsavel, inline=True)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        """Canal foi editado (nome, tópico, permissões etc.)."""
        mudancas = []
        if before.name != after.name:
            mudancas.append(f"**Nome:** `{before.name}` → `{after.name}`")

        # Tópico (apenas TextChannel)
        if hasattr(before, "topic") and before.topic != after.topic:
            mudancas.append(
                f"**Tópico:** `{before.topic or '—'}` → `{after.topic or '—'}`"
            )
        # NSFW
        if hasattr(before, "nsfw") and before.nsfw != after.nsfw:
            mudancas.append(f"**NSFW:** `{before.nsfw}` → `{after.nsfw}`")

        if not mudancas:
            return

        responsavel = "Desconhecido"
        try:
            async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_update):
                if entry.target.id == after.id:
                    responsavel = f"{entry.user.mention} (`{entry.user.id}`)"
                    break
        except Exception:
            pass

        e = _embed("🔧  Canal Editado", COR_CANAL)
        e.add_field(name="📌 Canal",       value=after.mention,          inline=True)
        e.add_field(name="👮 Responsável", value=responsavel,            inline=True)
        e.add_field(name="📋 Mudanças",    value="\n".join(mudancas),    inline=False)
        await self._enviar(e)

    # ══════════════════════════════════════════════════════════════════════════════
    #   CARGOS
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Cargo criado."""
        responsavel = "Desconhecido"
        try:
            async for entry in role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    responsavel = f"{entry.user.mention} (`{entry.user.id}`)"
                    break
        except Exception:
            pass

        e = _embed("🎭  Cargo Criado", COR_CARGO)
        e.add_field(name="🏷️ Cargo",       value=f"{role.mention} (`{role.id}`)", inline=True)
        e.add_field(name="🎨 Cor",         value=str(role.color),                 inline=True)
        e.add_field(name="👮 Responsável", value=responsavel,                     inline=False)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Cargo apagado."""
        responsavel = "Desconhecido"
        try:
            async for entry in role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    responsavel = f"{entry.user.mention} (`{entry.user.id}`)"
                    break
        except Exception:
            pass

        e = _embed("🗑️  Cargo Apagado", COR_SAIDA)
        e.add_field(name="🏷️ Nome", value=f"`{role.name}` (`{role.id}`)", inline=True)
        e.add_field(name="🎨 Cor",  value=str(role.color),                 inline=True)
        e.add_field(name="👮 Responsável", value=responsavel,            inline=False)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Cargo editado."""
        mudancas = []
        if before.name != after.name:
            mudancas.append(f"**Nome:** `{before.name}` → `{after.name}`")
        if before.color != after.color:
            mudancas.append(f"**Cor:** `{before.color}` → `{after.color}`")
        if before.permissions != after.permissions:
            mudancas.append("**Permissões alteradas**")
        if before.hoist != after.hoist:
            mudancas.append(f"**Exibir separado:** `{before.hoist}` → `{after.hoist}`")
        if before.mentionable != after.mentionable:
            mudancas.append(f"**Mencionável:** `{before.mentionable}` → `{after.mentionable}`")

        if not mudancas:
            return

        responsavel = "Desconhecido"
        try:
            async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_update):
                if entry.target.id == after.id:
                    responsavel = f"{entry.user.mention} (`{entry.user.id}`)"
                    break
        except Exception:
            pass

        e = _embed("✏️  Cargo Editado", COR_CARGO)
        e.add_field(name="🏷️ Cargo",       value=after.mention,         inline=True)
        e.add_field(name="👮 Responsável", value=responsavel,           inline=True)
        e.add_field(name="📋 Mudanças",    value="\n".join(mudancas),   inline=False)
        await self._enviar(e)

    # ══════════════════════════════════════════════════════════════════════════════
    #   VOZ
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Qualquer mudança de estado de voz."""

        # ── Entrou em canal de voz ──────────────────────────────────────────────
        if before.channel is None and after.channel is not None:
            e = _embed("🔊  Entrou no Canal de Voz", COR_VOZ)
            e.set_thumbnail(url=member.display_avatar.url)
            e.add_field(name="👤 Usuário", value=f"{member.mention} (`{member.id}`)", inline=True)
            e.add_field(name="🔊 Canal",   value=after.channel.mention,               inline=True)
            await self._enviar(e)

        # ── Saiu de canal de voz ────────────────────────────────────────────────
        elif before.channel is not None and after.channel is None:
            e = _embed("🔇  Saiu do Canal de Voz", COR_VOZ)
            e.set_thumbnail(url=member.display_avatar.url)
            e.add_field(name="👤 Usuário", value=f"{member.mention} (`{member.id}`)", inline=True)
            e.add_field(name="🔊 Canal",   value=before.channel.mention,              inline=True)
            await self._enviar(e)

        # ── Movido de canal ─────────────────────────────────────────────────────
        elif before.channel != after.channel and before.channel and after.channel:
            e = _embed("🔄  Movido de Canal de Voz", COR_VOZ)
            e.set_thumbnail(url=member.display_avatar.url)
            e.add_field(name="👤 Usuário",  value=f"{member.mention} (`{member.id}`)", inline=False)
            e.add_field(name="🔊 De",       value=before.channel.mention,              inline=True)
            e.add_field(name="🔊 Para",     value=after.channel.mention,               inline=True)
            await self._enviar(e)

        # ── Mute/Unmute por servidor ────────────────────────────────────────────
        if before.mute != after.mute:
            acao = "🔇 Mutado" if after.mute else "🔊 Desmutado"
            e = _embed(f"{acao} (Servidor)", COR_VOZ)
            e.set_thumbnail(url=member.display_avatar.url)
            e.add_field(name="👤 Usuário", value=f"{member.mention} (`{member.id}`)", inline=True)
            await self._enviar(e)

        # ── Deaf/Undeaf por servidor ────────────────────────────────────────────
        if before.deaf != after.deaf:
            acao = "🙉 Ensurdecido" if after.deaf else "👂 Desensurdecido"
            e = _embed(f"{acao} (Servidor)", COR_VOZ)
            e.set_thumbnail(url=member.display_avatar.url)
            e.add_field(name="👤 Usuário", value=f"{member.mention} (`{member.id}`)", inline=True)
            await self._enviar(e)

    # ══════════════════════════════════════════════════════════════════════════════
    #   SERVIDOR
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """Configurações do servidor foram alteradas."""
        mudancas = []
        if before.name != after.name:
            mudancas.append(f"**Nome:** `{before.name}` → `{after.name}`")
        if before.icon != after.icon:
            mudancas.append("**Ícone do servidor alterado**")
        if before.afk_channel != after.afk_channel:
            mudancas.append(
                f"**Canal AFK:** `{getattr(before.afk_channel, 'name', '—')}` → "
                f"`{getattr(after.afk_channel, 'name', '—')}`"
            )
        if before.verification_level != after.verification_level:
            mudancas.append(
                f"**Nível de verificação:** `{before.verification_level}` → `{after.verification_level}`"
            )

        if not mudancas:
            return

        e = _embed("⚙️  Servidor Atualizado", COR_SERVIDOR)
        e.add_field(name="📋 Mudanças", value="\n".join(mudancas), inline=False)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Convite criado."""
        e = _embed("🔗  Invite Criado", COR_SERVIDOR)
        criador = invite.inviter.mention if invite.inviter else "Desconhecido"
        usos    = invite.max_uses if invite.max_uses else "Ilimitado"
        e.add_field(name="🔗 Link",     value=invite.url,        inline=True)
        e.add_field(name="👤 Criado por", value=criador,         inline=True)
        e.add_field(name="🔢 Usos máx", value=str(usos),         inline=True)
        e.add_field(name="📌 Canal",    value=invite.channel.mention if invite.channel else "—", inline=True)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Convite apagado/expirado."""
        e = _embed("🗑️  Invite Deletado", COR_SERVIDOR)
        e.add_field(name="🔗 Código", value=invite.code, inline=True)
        e.add_field(name="📌 Canal",  value=invite.channel.mention if invite.channel else "—", inline=True)
        await self._enviar(e)


    # ══════════════════════════════════════════════════════════════════════════════
    #   THREADS
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        e = _embed("🧵  Thread Criada", COR_CANAL)
        e.add_field(name="🧵 Thread", value=f"{thread.mention} (`{thread.id}`)", inline=True)
        e.add_field(name="📌 Canal pai", value=thread.parent.mention if thread.parent else "—", inline=True)
        dono = thread.owner
        e.add_field(name="👤 Criada por", value=dono.mention if dono else "Desconhecido", inline=True)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        e = _embed("🗑️  Thread Apagada", COR_SAIDA)
        e.add_field(name="🧵 Nome", value=f"`{thread.name}` (`{thread.id}`)", inline=True)
        e.add_field(name="📌 Canal pai", value=thread.parent.mention if thread.parent else "—", inline=True)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        mudancas = []
        if before.name != after.name:
            mudancas.append(f"**Nome:** `{before.name}` → `{after.name}`")
        if before.archived != after.archived:
            estado = "Arquivada" if after.archived else "Desarquivada"
            mudancas.append(f"**Estado:** {estado}")
        if before.locked != after.locked:
            mudancas.append(f"**Bloqueada:** `{before.locked}` → `{after.locked}`")
        if not mudancas:
            return
        e = _embed("✏️  Thread Editada", COR_CANAL)
        e.add_field(name="🧵 Thread", value=after.mention, inline=True)
        e.add_field(name="📋 Mudanças", value="\n".join(mudancas), inline=False)
        await self._enviar(e)

    # ══════════════════════════════════════════════════════════════════════════════
    #   TIMEOUT DE MEMBROS
    # ══════════════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════════════
    #   EMOJIS
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: list[discord.Emoji],
        after: list[discord.Emoji],
    ):
        antes_ids = {e.id for e in before}
        depois_ids = {e.id for e in after}

        for emoji in after:
            if emoji.id not in antes_ids:
                e = _embed("😀  Emoji Adicionado", COR_ENTRADA)
                e.add_field(name="Emoji", value=f"{emoji} `:{emoji.name}:`", inline=True)
                await self._enviar(e)

        for emoji in before:
            if emoji.id not in depois_ids:
                e = _embed("🗑️  Emoji Removido", COR_SAIDA)
                e.add_field(name="Nome", value=f"`:{emoji.name}:`", inline=True)
                await self._enviar(e)

    # ══════════════════════════════════════════════════════════════════════════════
    #   STICKERS
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self,
        guild: discord.Guild,
        before: list[discord.GuildSticker],
        after: list[discord.GuildSticker],
    ):
        antes_ids = {s.id for s in before}
        depois_ids = {s.id for s in after}

        for sticker in after:
            if sticker.id not in antes_ids:
                e = _embed("🖼️  Sticker Adicionado", COR_ENTRADA)
                e.add_field(name="Nome", value=sticker.name, inline=True)
                await self._enviar(e)

        for sticker in before:
            if sticker.id not in depois_ids:
                e = _embed("🗑️  Sticker Removido", COR_SAIDA)
                e.add_field(name="Nome", value=sticker.name, inline=True)
                await self._enviar(e)

    # ══════════════════════════════════════════════════════════════════════════════
    #   WEBHOOKS
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel):
        e = _embed("🔗  Webhook Atualizado", COR_SERVIDOR)
        e.add_field(name="📌 Canal", value=channel.mention, inline=True)
        e.add_field(name="ℹ️ Detalhe", value="Um webhook foi criado, editado ou removido neste canal.", inline=False)
        await self._enviar(e)

    # ══════════════════════════════════════════════════════════════════════════════
    #   EVENTOS AGENDADOS
    # ══════════════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event: discord.ScheduledEvent):
        e = _embed("📅  Evento Agendado Criado", COR_ENTRADA)
        e.add_field(name="📌 Nome", value=event.name, inline=True)
        criador = event.creator
        e.add_field(name="👤 Criado por", value=criador.mention if criador else "Desconhecido", inline=True)
        if event.start_time:
            e.add_field(name="🕐 Início", value=f"<t:{int(event.start_time.timestamp())}:F>", inline=True)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        e = _embed("🗑️  Evento Agendado Removido", COR_SAIDA)
        e.add_field(name="📌 Nome", value=event.name, inline=True)
        await self._enviar(e)

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent):
        mudancas = []
        if before.name != after.name:
            mudancas.append(f"**Nome:** `{before.name}` → `{after.name}`")
        if before.status != after.status:
            mudancas.append(f"**Status:** `{before.status}` → `{after.status}`")
        if not mudancas:
            return
        e = _embed("✏️  Evento Agendado Editado", COR_SERVIDOR)
        e.add_field(name="📌 Evento", value=after.name, inline=True)
        e.add_field(name="📋 Mudanças", value="\n".join(mudancas), inline=False)
        await self._enviar(e)


async def setup(bot: commands.Bot):
    await bot.add_cog(LogsServidor(bot))

