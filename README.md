<div align="center">

# ⚔️ Paquistão Web

### Plataforma de gestão para comunidades no Discord

Bot modular, painel web e automações integradas para gerenciar membros, metas, tickets, moderação e atividades de uma comunidade.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-20+-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)

</div>

> [!NOTE]
> Este repositório é um projeto de demonstração e portfólio. Os dados, IDs e configurações presentes no código são fictícios e devem ser substituídos antes de qualquer implantação real.

## Sobre o projeto

O **Paquistão Web** reúne um bot para Discord e uma aplicação web em uma única solução. O sistema automatiza rotinas administrativas, registra atividades em SQLite e oferece uma interface para consulta de informações da comunidade.

O projeto foi desenvolvido pela **MSCODEX** com foco em modularidade, automação e facilidade de implantação.

## Principais recursos

- Cadastro, edição e acompanhamento de membros
- Sistema de farm e metas semanais
- Registro de entregas, C4 e outros itens
- Bate-ponto com histórico e ranking de atividade
- Advertências, punições e relatórios
- Reuniões, presenças e solicitações de ausência
- Painel configurável de tickets
- Moderação e proteção contra links
- Boas-vindas e atribuição automática de cargos
- Logs de atividades do servidor
- Autenticação web com Discord OAuth2
- Perfil do membro integrado ao banco SQLite
- Galeria, vídeos e notícias via API
- Execução conjunta do bot Python e servidor Node.js
- Deploy preparado para Docker e Railway

## Tecnologias

| Camada | Tecnologias |
|---|---|
| Bot | Python, discord.py |
| Servidor web | Node.js, Express |
| Integração Discord | discord.js, Discord OAuth2 |
| Banco de dados | SQLite |
| Front-end | HTML, CSS e JavaScript |
| Infraestrutura | Docker e Railway |

## Arquitetura

```text
paquist-oWeb/
├── commands/          # Módulos e comandos do bot
├── main.py            # Inicialização do bot Python
├── config.py          # Configurações centrais
├── database.py        # Tabelas e operações SQLite
├── server.js          # API, site e integração Discord
├── index.html         # Interface web
├── requirements.txt   # Dependências Python
├── package.json       # Dependências e scripts Node.js
└── Dockerfile         # Imagem para implantação
```

Os comandos ficam separados por responsabilidade dentro de `commands/`, facilitando manutenção e expansão sem concentrar toda a lógica em um único arquivo.

## Pré-requisitos

- Python 3.10 ou superior
- Node.js 20 ou superior
- npm
- Aplicação e bot configurados no Discord Developer Portal

## Instalação local

### 1. Clone o projeto

```bash
git clone https://github.com/LucasCosta01-code/paquist-oWeb.git
cd paquist-oWeb
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
npm install
```

### 3. Configure o ambiente

Crie um arquivo `.env` na raiz:

```env
DISCORD_TOKEN=seu_token_do_bot
DISCORD_CLIENT_ID=id_da_aplicacao
DISCORD_CLIENT_SECRET=segredo_da_aplicacao
REDIRECT_URI=http://localhost:3000/api/auth/callback

LOG_CHANNEL_ID=0
CHANNEL_ALISTAMENTO=0
CHANNEL_ORDERS=0
CHANNEL_VIDEOS=0
CHANNEL_GALLERY=0

META_FARM_SEMANAL=50
PORT=3000
```

Os demais IDs de canais e cargos utilizados pelo bot podem ser configurados em `config.py`.

### 4. Inicie o sistema

```bash
npm start
```

O comando inicia o servidor Node.js e o bot Python em conjunto. Por padrão, a interface web fica disponível em:

```text
http://localhost:3000
```

## Executando com Docker

```bash
docker build -t paquistao-web .
docker run --env-file .env -p 3000:3000 paquistao-web
```

Para preservar o SQLite em produção, configure um volume persistente e a variável `RAILWAY_VOLUME_MOUNT_PATH`.

## Módulos do bot

Entre os módulos disponíveis estão:

- `membros`, `registro` e `entrada`
- `farm`, `c4` e `metas`
- `bate_ponto`, `reunioes` e `relatorios`
- `punicoes`, `moderacao` e `anti_link`
- `tickets`, `aviso` e `boas_vindas`
- `logs_servidor`, `status` e `verificacao`

## Cuidados antes de usar em produção

- Substitua todos os IDs e dados demonstrativos
- Nunca publique tokens ou segredos reais
- Use variáveis de ambiente para credenciais
- Restrinja CORS aos domínios autorizados
- Utilize HTTPS e cookies seguros
- Mantenha o banco SQLite fora do repositório
- Revise permissões e intents do bot
- Configure backup do volume persistente

## Próximas melhorias

- [ ] Painel administrativo completo
- [ ] Testes automatizados
- [ ] Controle de acesso por cargo
- [ ] Migrações versionadas do banco
- [ ] Logs estruturados
- [ ] CI com GitHub Actions
- [ ] Documentação da API

## Autor

Desenvolvido por **Lucas Costa — MSCODEX**.

- [GitHub](https://github.com/LucasCosta01-code)
- [LinkedIn](https://www.linkedin.com/in/lucas-costa-b675762a7/)

---

<div align="center">
  <strong>MSCODEX — tecnologia, automação e soluções digitais.</strong>
</div>
