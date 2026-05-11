"""
main.py - Ponto de entrada principal do bot
Inicializa o bot, carrega os Cogs e sincroniza os slash commands.
"""

import sys
import discord
from discord.ext import commands
import asyncio
import os

# Garante que o terminal aceita UTF-8 no Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import database as db
from config import TOKEN


# ─── CONFIGURAÇÃO DOS INTENTS ──────────────────────────────────────────────────
# Intents controlam quais eventos o bot recebe do Discord
intents = discord.Intents.default()
intents.members = True       # Necessário para acessar dados de membros
intents.message_content = True


# ─── CLASSE DO BOT ─────────────────────────────────────────────────────────────
class FaccaoBot(commands.Bot):
    """Classe principal do bot com carregamento automático de Cogs."""

    def __init__(self):
        super().__init__(
            command_prefix="!",  # Prefixo de fallback (não usado – apenas slash)
            intents=intents,
            help_command=None    # Remove o !help padrão
        )

    async def setup_hook(self):
        """Chamado durante a inicialização do bot antes do login."""
        # Cria as tabelas do banco de dados
        db.criar_tabelas()

        # Lista de todos os módulos de comandos para carregar
        cogs = [
            "commands.membros",
            "commands.farm",
            "commands.c4",
            "commands.reunioes",
            "commands.punicoes",
            "commands.relatorios",
            "commands.aviso",
            "commands.moderacao",
            "commands.verificacao",
            "commands.logs_servidor",   # ← Logs completos do servidor
            # "commands.verificacao_meta", # ← DESATIVADO: substituído por commands.metas
            "commands.status",           # ← Status e segurança do servidor
            "commands.clonar",           # ← Clonagem completa de servidor
            "commands.metas",            # ← Sistema de Metas (C4 / Plásticos)
            "commands.boas_vindas",      # ← Boas-Vindas para novos membros
            "commands.bate_ponto",       # ← Sistema de Bate-Ponto
            "commands.registro",         # ← Sistema de Registro (Recrutado/Visitante)
            "commands.tickets",          # ← Sistema de Tickets
            "commands.anti_link",        # ← Proteção contra links
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"[COG] OK  {cog} carregado com sucesso.")
            except Exception as e:
                print(f"[COG] ERRO ao carregar {cog}: {e}")

    async def on_ready(self):
        """Chamado quando o bot está pronto e conectado ao Discord."""
        # Sincroniza slash commands por guild (instantâneo, sem duplicação)
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"[SYNC] {len(synced)} comando(s) sincronizados em {guild.name}")

        print("=" * 50)
        print(f"[BOT] {self.user} esta online!")
        print(f"[BOT] Conectado em {len(self.guilds)} servidor(es).")
        print("=" * 50)

        # Define a atividade do bot (status)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="⚔️ Gerenciando a Facção"
            ),
            status=discord.Status.online
        )

    async def on_command_error(self, ctx, error):
        """Tratamento global de erros de comandos."""
        print(f"[ERRO] Erro no comando: {error}")


# ─── INICIALIZAÇÃO ─────────────────────────────────────────────────────────────
def main():
    """Função principal que inicia o bot."""
    if not TOKEN:
        print("[ERRO] DISCORD_TOKEN não encontrado no arquivo .env!")
        print("[ERRO] Por favor, configure o arquivo .env antes de iniciar.")
        return

    bot = FaccaoBot()
    bot.run(TOKEN, log_handler=None)  # log_handler=None usa o logger padrão do Python


if __name__ == "__main__":
    main()
