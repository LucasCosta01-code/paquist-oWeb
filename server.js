require('dotenv').config();
const { Client, GatewayIntentBits, EmbedBuilder, Partials, ActionRowBuilder, ButtonBuilder, ButtonStyle, AttachmentBuilder } = require('discord.js');
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const bodyParser = require('body-parser');
const axios = require('axios');
const cookieParser = require('cookie-parser');
const sqlite3 = require('sqlite3').verbose();

console.log("-----------------------------------------");
console.log("🚀 TROPA PAQUISTÃO - INICIANDO SISTEMA...");
console.log("-----------------------------------------");

// Database Setup
const volumePath = process.env.RAILWAY_VOLUME_MOUNT_PATH || __dirname;
const DB_PATH = path.join(volumePath, 'database.json');
const dbPath = path.join(volumePath, 'faccao.db');

function getDB() {

    const defaultDB = { gallery: [], videos: [], news: [] };
    if (!fs.existsSync(DB_PATH)) {
        fs.writeFileSync(DB_PATH, JSON.stringify(defaultDB, null, 2));
        return defaultDB;
    }
    const db = JSON.parse(fs.readFileSync(DB_PATH, 'utf8'));
    // Ensure all keys exist to avoid "undefined" errors
    return { ...defaultDB, ...db };
}

function saveDB(data) {
    fs.writeFileSync(DB_PATH, JSON.stringify(data, null, 2));
}


// Express Setup
const app = express();
app.set('trust proxy', 1); // Essencial para Railway/Cloudflare

app.use(cors());
app.use(bodyParser.json());
app.use(cookieParser());

// Segurança, Headers e Força HTTPS (Redirecionamento automático)
app.use((req, res, next) => {
    // Headers de segurança essenciais (Substitui o Helmet para não quebrar o npm ci)
    res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'SAMEORIGIN');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    res.removeHeader('X-Powered-By');
    
    // Checa se o request veio via HTTP original (através do proxy da Railway)
    if (req.headers['x-forwarded-proto'] && req.headers['x-forwarded-proto'] !== 'https') {
        // Usa redirect permanente (301) para SEO e forçar cache HTTPS
        return res.redirect(301, `https://${req.headers.host}${req.url}`);
    }
    next();
});

app.use(express.static(__dirname));

// API Endpoints
app.get('/api/gallery', (req, res) => res.json(getDB().gallery));
app.get('/api/videos', (req, res) => res.json(getDB().videos));
app.get('/api/news', (req, res) => res.json(getDB().news));
app.get('/api/stats', (req, res) => res.json({ members: cachedMemberCount }));

// ── ROTA DO PERFIL (Conecta com faccao.db) ──
app.get('/api/profile', async (req, res) => {
    if (!req.cookies.discordUser) {
        return res.status(401).json({ error: 'Not logged in' });
    }
    const user = JSON.parse(req.cookies.discordUser);
    
    // --- VERIFICAÇÃO DE CARGO NO DISCORD ---
    const MEMBER_ROLE_ID = '1494537507310800928';
    let hasRole = false;
    try {
        const guild = client.guilds.cache.first(); // Pega o primeiro servidor que o bot está
        if (guild) {
            const member = await guild.members.fetch(user.id);
            hasRole = member.roles.cache.has(MEMBER_ROLE_ID);
        }
    } catch (e) {
        console.log("Erro ao buscar cargo do membro:", e.message);
    }

    if (!hasRole) {
        return res.json({ registered: false, discord: user, reason: 'NO_ROLE' });
    }
    // ----------------------------------------

    if (!fs.existsSync(dbPath)) {
        return res.json({ registered: false, discord: user, error: 'DB_NOT_FOUND' });
    }
    
    const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY);
    
    db.get("SELECT * FROM membros WHERE discord_id = ?", [user.id], (err, row) => {
        if (err) {
            db.close();
            return res.status(500).json({ error: 'Database query error' });
        }
        
        if (!row) {
            db.close();
            return res.json({ registered: false, discord: user, reason: 'NOT_IN_DB' });
        }
        
        db.all("SELECT tipo, SUM(quantidade) as total FROM entregas_meta WHERE discord_id = ? GROUP BY tipo", [user.id], (err, metas) => {
            const metaTotals = { c4: 0, plasticos: 0, colete: 0, corda: 0, capuz: 0 };
            if (metas) {
                metas.forEach(m => metaTotals[m.tipo] = m.total);
            }
            
            db.all("SELECT chave, valor FROM bot_config WHERE chave LIKE 'meta_%' OR chave = 'modo_meta'", [], (err, configRows) => {
                db.close();
                const targetMetas = {};
                let modoMeta = 'ou';
                
                if (configRows && configRows.length > 0) {
                    configRows.forEach(row => {
                        if (row.chave === 'modo_meta') {
                            modoMeta = row.valor;
                        } else {
                            const tipo = row.chave.replace('meta_', '');
                            const val = parseInt(row.valor);
                            if (val > 0) targetMetas[tipo] = val;
                        }
                    });
                }
                
                // Fallback to defaults if no targets defined
                if (Object.keys(targetMetas).length === 0) {
                    targetMetas.c4 = 75;
                    targetMetas.plasticos = 300;
                }
                
                res.json({
                    registered: true,
                    discord: user,
                    stats: row,
                    metas: metaTotals,
                    targetMetas: targetMetas,
                    modoMeta: modoMeta
                });
            });
        });
    });
});

// Discord OAuth2 Routes
const DISCORD_CLIENT_ID = process.env.DISCORD_CLIENT_ID;
const DISCORD_CLIENT_SECRET = process.env.DISCORD_CLIENT_SECRET;
const REDIRECT_URI = process.env.REDIRECT_URI || 'http://localhost:3000/api/auth/callback';

app.get('/api/auth/discord', (req, res) => {
    if (!DISCORD_CLIENT_ID) return res.send("ERRO: Configure o DISCORD_CLIENT_ID no .env");
    const url = `https://discord.com/api/oauth2/authorize?client_id=${DISCORD_CLIENT_ID}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&response_type=code&scope=identify%20guilds`;
    res.redirect(url);
});

app.get('/api/auth/callback', async (req, res) => {
    if (!req.query.code) return res.redirect('/');
    try {
        const params = new URLSearchParams({
            client_id: DISCORD_CLIENT_ID,
            client_secret: DISCORD_CLIENT_SECRET,
            grant_type: 'authorization_code',
            code: req.query.code,
            redirect_uri: REDIRECT_URI
        });
        const tokenResponse = await axios.post('https://discord.com/api/oauth2/token', params.toString(), {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
        
        const accessToken = tokenResponse.data.access_token;

        const userResponse = await axios.get('https://discord.com/api/users/@me', {
            headers: { Authorization: `Bearer ${accessToken}` }
        });
        
        // --- VERIFICAÇÃO SE ESTÁ NO DISCORD DA FACÇÃO ---
        const guildsResponse = await axios.get('https://discord.com/api/users/@me/guilds', {
            headers: { Authorization: `Bearer ${accessToken}` }
        });
        
        // Pega o ID do servidor baseado no canal configurado no .env
        const factionChannel = client.channels.cache.get(process.env.CHANNEL_ALISTAMENTO);
        if (!factionChannel) {
            console.error("ERRO: O bot não encontrou o canal configurado. Verifique os IDs no .env");
            return res.redirect('/?error=bot_not_ready');
        }
        const factionGuildId = factionChannel.guild.id;
        
        const isInFaction = guildsResponse.data.some(guild => guild.id === factionGuildId);
        
        if (!isInFaction) {
            // O usuário não está no grupo da facção
            return res.redirect('/?error=not_in_faction');
        }
        // --------------------------------------------------

        // Salva dados no cookie
        res.cookie('discordUser', JSON.stringify({
            id: userResponse.data.id,
            username: userResponse.data.username,
            avatar: userResponse.data.avatar
        }), { maxAge: 1000 * 60 * 60 * 24 * 7, httpOnly: false }); // 7 dias
        res.redirect('/');
    } catch (err) {
        console.error("Erro OAuth:", err.message);
        res.redirect('/?error=oauth_failed');
    }
});

app.get('/api/auth/me', async (req, res) => {
    if (req.cookies.discordUser) {
        const user = JSON.parse(req.cookies.discordUser);
        
        // --- CATEGORIZAÇÃO DINÂMICA POR CARGO ---
        let status = "CONVIDADO";
        try {
            const guild = client.guilds.cache.first();
            if (guild) {
                const member = await guild.members.fetch(user.id);
                
                // IDs dos cargos baseados no config.py e registro.py
                const ROLES = {
                    MEMBRO: ['1494537507310800928', '1494537726916169799', '1494537855739887758', '1492571692638277795', '1492527673531171019'],
                    RECRUTA: ['1501834943657939097'],
                    VISITANTE: ['1497655589365350522']
                };

                if (member.roles.cache.some(r => ROLES.MEMBRO.includes(r.id))) {
                    status = "MEMBRO";
                } else if (member.roles.cache.some(r => ROLES.RECRUTA.includes(r.id))) {
                    status = "RECRUTA";
                } else if (member.roles.cache.some(r => ROLES.VISITANTE.includes(r.id))) {
                    status = "VISITANTE";
                }
            }
        } catch (e) {
            console.log("Erro ao categorizar usuário:", e.message);
        }
        
        user.status = status;
        res.json(user);
    } else {
        res.status(401).json({ error: 'Not logged in' });
    }
});

app.get('/api/auth/logout', (req, res) => {
    res.clearCookie('discordUser');
    res.redirect('/');
});

app.post('/api/submit', async (req, res) => {
    const { type, data } = req.body;
    
    // Verificacao
    let verifiedUser = data._discordUser ? `✅ Verificado: ${data._discordUser} (${data._discordId})` : `⚠️ Não Verificado`;
    const channelId = type === 'order' ? process.env.CHANNEL_ORDERS : 
                    type === 'video' ? process.env.CHANNEL_VIDEOS : 
                    type === 'gallery' ? process.env.CHANNEL_GALLERY : 
                    process.env.CHANNEL_ALISTAMENTO;

    const colors = { alistamento: 0x00ff88, order: 0xf39c12, gallery: 0x00ff88, video: 0x00ff88 };

    try {
        const channel = await client.channels.fetch(channelId);
        const guild = channel.guild;
        
        const filteredData = { ...data };
        delete filteredData._discordUser;
        delete filteredData._discordId;
        
        const fields = Object.keys(filteredData).map(key => ({ name: key.toUpperCase(), value: String(filteredData[key]) || "Não informado", inline: true }));
        fields.push({ name: 'STATUS LOGIN', value: verifiedUser, inline: false });
        
        const embed = new EmbedBuilder()
            .setTitle(`NOVA ENTRADA: ${type.toUpperCase()}`)
            .setColor(colors[type] || 0x00ff88)
            .addFields(fields)
            .setTimestamp();

        const mainMsg = await channel.send({ embeds: [embed] });

        // --- SISTEMA DE TICKET PARA ENCOMENDAS E RECRUTAMENTO ---
        if ((type === 'order' || type === 'alistamento') && data._discordId) {
            const CATEGORY_ID = '1492506092633194616';
            
            // Busca cargos configurados no banco de dados
            const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY);
            db.get("SELECT valor FROM bot_config WHERE chave = ?", [type === 'order' ? 'role_ticket_encomenda' : 'role_ticket_recrutamento'], async (err, configRow) => {
                db.close();
                
                let supportRoles = [];
                if (configRow && configRow.valor) {
                    supportRoles = configRow.valor.split(',').map(id => id.trim());
                } else {
                    // Defaults caso não esteja configurado
                    supportRoles = type === 'order' ? ['1494537855739887758'] : ['1494537507310800928', '1494537726916169799'];
                }

                const prefix = type === 'order' ? '📦-encomenda' : '⚔️-recrutamento';
                const embedTitle = type === 'order' ? '🛒 NOVO CHAT DE ENCOMENDA' : '⚔️ NOVO CHAT DE RECRUTAMENTO';
                const embedColor = type === 'order' ? 0xf39c12 : 0x00ff88;
                const welcomeText = type === 'order' ? 
                    `Olá <@${data._discordId}>! Este é o seu canal exclusivo para tratar da sua encomenda.` :
                    `Olá <@${data._discordId}>! Bem-vindo ao seu processo de recrutamento. Um responsável irá te atender em breve.`;

                try {
                    const ticketChannel = await guild.channels.create({
                        name: `${prefix}-${data._discordUser}`,
                        type: 0, // GuildText
                        parent: CATEGORY_ID,
                        permissionOverwrites: [
                            {
                                id: guild.id, // @everyone
                                deny: [8n], // No View
                            },
                            {
                                id: data._discordId,
                                allow: [1024n, 2048n, 32768n, 65536n], // View, Send, AttachFiles, ReadHistory
                            },
                            ...supportRoles.map(roleId => ({
                                id: roleId,
                                allow: [1024n, 2048n, 32768n, 65536n],
                            }))
                        ],
                    });

                    const ticketEmbed = new EmbedBuilder()
                        .setTitle(embedTitle)
                        .setDescription(`${welcomeText}\n\n**Dados Enviados:**\n` + 
                            Object.keys(filteredData).map(k => `**${k.toUpperCase()}:** ${filteredData[k]}`).join('\n'))
                        .setColor(embedColor)
                        .setTimestamp()
                        .setFooter({ text: 'Tropa Paquistão - Sistema de Atendimento' });

                    const tags = supportRoles.map(id => `<@&${id}>`).join(' | ');
                
                    const row = new ActionRowBuilder()
                        .addComponents(
                            new ButtonBuilder()
                                .setCustomId('btn_finalize_ticket')
                                .setLabel('Finalizar Atendimento')
                                .setStyle(ButtonStyle.Danger)
                                .setEmoji('🔒')
                        );

                    await ticketChannel.send({ content: `<@${data._discordId}> | ${tags}`, embeds: [ticketEmbed], components: [row] });
                    console.log(`✅ Canal de ticket criado (${type}): ${ticketChannel.name}`);
                } catch (err) {
                    console.error(`❌ Erro ao criar canal de ticket para ${type}:`, err);
                }
            });
        }
        // ------------------------------------------

        res.json({ success: true });
    } catch (error) {
        console.error("❌ Erro ao enviar formulário para o Discord:", error);
        res.status(500).json({ error: error.message });
    }
});

// Discord Bot
const client = new Client({ 
    intents: [
        GatewayIntentBits.Guilds, 
        GatewayIntentBits.GuildMessages, 
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ] 
});

const TARGET_CHANNEL_ID = '1502504591097335828';
const TARGET_ROLE_ID = '1492527673531171019';
let cachedMemberCount = 0;

client.on('ready', async () => {
    console.log(`✅ BOT DISCORD LOGADO COMO: ${client.user.tag}`);
    
    // Registra o comando /c_cargo como comando de GUILDA para ser instantâneo
    try {
        for (const [guildId, guild] of client.guilds.cache) {
            await guild.commands.set([
                {
                    name: 'c_cargo',
                    description: 'Configura o cargo de suporte para tickets',
                    options: [
                        {
                            name: 'tipo',
                            description: 'Qual sistema configurar?',
                            type: 3, // STRING
                            required: true,
                            choices: [
                                { name: 'Encomenda', value: 'encomenda' },
                                { name: 'Recrutamento', value: 'recrutamento' }
                            ]
                        },
                        {
                            name: 'cargo',
                            description: 'Arraste o cargo que poderá ver os tickets',
                            type: 8, // ROLE
                            required: true
                        }
                    ]
                }
            ]);
            console.log(`✅ Comando /c_cargo registrado instantaneamente na guilda: ${guild.name}`);
        }
    } catch (e) {
        console.error("❌ Erro ao registrar comando na guilda:", e);
    }

    console.log(`📡 Sincronizando o histórico completo do canal ${TARGET_CHANNEL_ID}...`);

    try {
        const channel = await client.channels.fetch(TARGET_CHANNEL_ID);
        const guild = channel.guild;
        
        try {
            await guild.members.fetch(); // Puxa todos os membros para cache
            const role = guild.roles.cache.get(TARGET_ROLE_ID);
            if (role) {
                cachedMemberCount = role.members.size;
                console.log(`👥 Contador de Membros: ${cachedMemberCount} encontrados no cargo.`);
            }
        } catch(e) {
            console.error("⚠️ Aviso: SERVER MEMBERS INTENT não está ativada no Discord Developer Portal.");
        }
        
        const messages = await channel.messages.fetch({ limit: 100 });
        
        const db = getDB();

        messages.forEach(message => {
            if (message.author.bot) return;

            const hasAttachment = message.attachments.size > 0;
            const attachmentUrl = hasAttachment ? message.attachments.first().url : null;
            let content = message.content;
            let customAuthor = null;
            
            // Extract "Autor: name" or "autor: name"
            const authorMatch = content.match(/autor:\s*(.+)/i);
            if (authorMatch) {
                customAuthor = authorMatch[1].trim();
                // Remove the author line from content so it doesn't show twice
                content = content.replace(/autor:\s*(.+)/i, '').trim();
            }

            const isVideoLink = content.includes('youtube.com') || content.includes('youtu.be') || content.includes('tiktok.com');
            const isImageLink = content.match(/\.(jpeg|jpg|gif|png|webp)$/i) != null;

            let ytThumb = null;
            if (isVideoLink) {
                const ytRegex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i;
                const match = content.match(ytRegex);
                if (match && match[1]) {
                    ytThumb = `https://img.youtube.com/vi/${match[1]}/maxresdefault.jpg`;
                }
            }

            const post = {
                id: message.id,
                author: customAuthor || message.author.username,
                authorAvatar: message.author.displayAvatarURL(),
                date: new Date(message.createdTimestamp).toISOString(),
                content: content
            };

            if (isVideoLink) {
                const linkMatches = content.match(/https?:\/\/[^\s]+/);
                db.videos.push({ 
                    ...post, 
                    title: "Vídeo do Discord", 
                    link: linkMatches ? linkMatches[0] : content,
                    thumb: ytThumb 
                });
            } else if (hasAttachment || isImageLink) {
                db.gallery.push({ ...post, type: "image", content: attachmentUrl || content.match(/https?:\/\/[^\s]+/)[0] });
            } else if (content.trim().length > 0 && !hasAttachment && !isImageLink) {
                db.news.push(post);
            }
        });

        saveDB(db);
        console.log(`✅ Sincronização 100% Completa! ${messages.size} mensagens analisadas do Discord.`);

    } catch (error) {
        console.error("❌ Erro ao sincronizar o canal no startup:", error);
    }
});

client.on('messageCreate', async (message) => {
    if (message.author.bot || message.channelId !== TARGET_CHANNEL_ID) return;
    const db = getDB();
    let updated = false;

    const hasAttachment = message.attachments.size > 0;
    const attachmentUrl = hasAttachment ? message.attachments.first().url : null;
    let content = message.content;
    let customAuthor = null;
    
    const authorMatch = content.match(/autor:\s*(.+)/i);
    if (authorMatch) {
        customAuthor = authorMatch[1].trim();
        content = content.replace(/autor:\s*(.+)/i, '').trim();
    }

    const isVideoLink = content.includes('youtube.com') || content.includes('youtu.be') || content.includes('tiktok.com');
    const isImageLink = content.match(/\.(jpeg|jpg|gif|png|webp)$/i) != null;

    let ytThumb = null;
    if (isVideoLink) {
        const ytRegex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i;
        const match = content.match(ytRegex);
        if (match && match[1]) {
            ytThumb = `https://img.youtube.com/vi/${match[1]}/maxresdefault.jpg`;
        }
    }

    const post = {
        id: message.id,
        author: customAuthor || message.author.username,
        authorAvatar: message.author.displayAvatarURL(),
        date: new Date().toISOString(),
        content: content
    };

    if (isVideoLink) {
        const linkMatches = content.match(/https?:\/\/[^\s]+/);
        db.videos.push({ 
            ...post, 
            title: "Vídeo do Discord", 
            link: linkMatches ? linkMatches[0] : content,
            thumb: ytThumb 
        });
        updated = true;
        console.log(`🎬 Novo vídeo de ${message.author.username} adicionado.`);
    } else if (hasAttachment || isImageLink) {
        db.gallery.push({ ...post, type: "image", content: attachmentUrl || content.match(/https?:\/\/[^\s]+/)[0] });
        updated = true;
        console.log(`📸 Nova foto de ${message.author.username} adicionada.`);
    } else if (content.trim().length > 0 && !hasAttachment && !isImageLink) {
        db.news.push(post);
        updated = true;
        console.log(`📰 Nova notícia de ${message.author.username} publicada.`);
    }

    if (updated) {
        saveDB(db);
        message.reply(`✅ **REGISTRADO!** Esse conteúdo já está disponível no site da Tropa! 🚀`);
    }
});

client.on('messageDelete', async (message) => {
    if (message.channelId !== TARGET_CHANNEL_ID) return;
    const db = getDB();
    const idToRemove = message.id;

    const initialGalleryLength = db.gallery.length;
    const initialVideosLength = db.videos.length;
    const initialNewsLength = db.news.length;

    db.gallery = db.gallery.filter(item => item.id !== idToRemove);
    db.videos = db.videos.filter(item => item.id !== idToRemove);
    db.news = db.news.filter(item => item.id !== idToRemove);

    if (db.gallery.length !== initialGalleryLength || db.videos.length !== initialVideosLength || db.news.length !== initialNewsLength) {
        saveDB(db);
        console.log(`🗑️ Conteúdo removido pelo Discord (ID: ${idToRemove})`);
    }
});

client.on('messageDeleteBulk', async (messages) => {
    const firstMsg = messages.first();
    if (!firstMsg || firstMsg.channelId !== TARGET_CHANNEL_ID) return;

    const db = getDB();
    const deletedIds = new Set(messages.map(m => m.id));

    db.gallery = db.gallery.filter(item => !deletedIds.has(item.id));
    db.videos = db.videos.filter(item => !deletedIds.has(item.id));
    db.news = db.news.filter(item => !deletedIds.has(item.id));

    saveDB(db);
    console.log(`🧹 Chat limpo no Discord! Removendo ${messages.size} itens do site.`);
});



client.on('guildMemberAdd', async (member) => {
    try {
        const role = member.guild.roles.cache.get(TARGET_ROLE_ID);
        if (role) cachedMemberCount = role.members.size;
    } catch(e) {}
});

client.on('guildMemberRemove', async (member) => {
    try {
        const role = member.guild.roles.cache.get(TARGET_ROLE_ID);
        if (role) cachedMemberCount = role.members.size;
    } catch(e) {}
});

client.on('guildMemberUpdate', async (oldMember, newMember) => {
    try {
        const role = newMember.guild.roles.cache.get(TARGET_ROLE_ID);
        if (role) cachedMemberCount = role.members.size;
    } catch(e) {}
});

client.on('interactionCreate', async (interaction) => {
    if (interaction.isChatInputCommand()) {
        if (interaction.commandName === 'c_cargo') {
            const ADMIN_ROLES = ['1494537507310800928', '1494537726916169799'];
            if (!interaction.member.roles.cache.some(r => ADMIN_ROLES.includes(r.id))) {
                return interaction.reply({ content: "❌ Você não tem permissão (Admin) para configurar cargos.", ephemeral: true });
            }

            const tipo = interaction.options.getString('tipo');
            const role = interaction.options.getRole('cargo');
            const chave = tipo === 'encomenda' ? 'role_ticket_encomenda' : 'role_ticket_recrutamento';

            const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READWRITE);
            db.run("INSERT OR REPLACE INTO bot_config (chave, valor) VALUES (?, ?)", [chave, role.id], function(err) {
                db.close();
                if (err) {
                    console.error("Erro ao salvar config:", err);
                    return interaction.reply({ content: "❌ Erro ao salvar configuração no banco de dados.", ephemeral: true });
                }
                interaction.reply({ content: `✅ Cargo para **${tipo}** configurado com sucesso: <@&${role.id}>`, ephemeral: true });
            });
        }
    } else if (interaction.isButton()) {
        if (interaction.customId === 'btn_finalize_ticket') {
            const channel = interaction.channel;
            const isRecrutamento = channel.name.includes('recrutamento');
            const isEncomenda = channel.name.includes('encomenda');
            const type = isRecrutamento ? 'recrutamento' : (isEncomenda ? 'encomenda' : null);

            if (!type) return interaction.reply({ content: "❌ Este canal não é um ticket válido.", ephemeral: true });

            // Busca cargo configurado no banco
            const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY);
            db.get("SELECT valor FROM bot_config WHERE chave = ?", [type === 'encomenda' ? 'role_ticket_encomenda' : 'role_ticket_recrutamento'], async (err, row) => {
                db.close();
                
                const ADMIN_ROLES = ['1494537507310800928', '1494537726916169799'];
                const allowedRoles = row ? [row.valor, ...ADMIN_ROLES] : [...ADMIN_ROLES];

                if (!interaction.member.roles.cache.some(r => allowedRoles.includes(r.id))) {
                    return interaction.reply({ content: "❌ Você não tem permissão para finalizar este atendimento.", ephemeral: true });
                }

                // --- LOG DE FINALIZAÇÃO ---
                const LOG_CHANNEL_ID = '1502421274507612280';
                try {
                    const logChannel = await client.channels.fetch(LOG_CHANNEL_ID);
                    
                    // --- GERAÇÃO DE HISTÓRICO (TRANSCRIPT) ---
                    const messages = await channel.messages.fetch({ limit: 100 });
                    let transcript = `HISTÓRICO DO TICKET: ${channel.name}\n`;
                    transcript += `FINALIZADO POR: ${interaction.user.tag}\n`;
                    transcript += `DATA: ${new Date().toLocaleString('pt-BR')}\n`;
                    transcript += `------------------------------------------\n\n`;

                    const sortedMessages = messages.sort((a, b) => a.createdTimestamp - b.createdTimestamp);
                    sortedMessages.forEach(msg => {
                        const time = new Date(msg.createdTimestamp).toLocaleString('pt-BR');
                        transcript += `[${time}] ${msg.author.tag}: ${msg.content}\n`;
                        if (msg.attachments.size > 0) {
                            msg.attachments.forEach(att => transcript += `[ANEXO]: ${att.url}\n`);
                        }
                    });

                    const buffer = Buffer.from(transcript, 'utf-8');
                    const attachment = new AttachmentBuilder(buffer, { name: `transcript-${channel.name}.txt` });
                    // ------------------------------------------

                    const logEmbed = new EmbedBuilder()
                        .setTitle('🔒 ATENDIMENTO FINALIZADO')
                        .setColor(0xff3333)
                        .addFields([
                            { name: 'Tipo', value: type.toUpperCase(), inline: true },
                            { name: 'Canal', value: `#${channel.name}`, inline: true },
                            { name: 'Finalizado por', value: `<@${interaction.user.id}>`, inline: false }
                        ])
                        .setTimestamp()
                        .setFooter({ text: 'Tropa Paquistão - Logs de Suporte' });

                    await logChannel.send({ embeds: [logEmbed], files: [attachment] });
                } catch (e) {
                    console.error("Erro ao enviar log:", e.message);
                }

                await interaction.reply({ content: "🔒 Finalizando atendimento e deletando canal em 5 segundos..." });
                setTimeout(() => channel.delete().catch(e => console.log("Erro ao deletar canal:", e)), 5000);
            });
        }
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🌐 SITE ONLINE: Acesse em http://localhost:${PORT}`);
    console.log("-----------------------------------------");
});

const discordToken = (process.env.DISCORD_TOKEN || "").trim();
client.login(discordToken).catch(err => {
    console.error("❌ ERRO AO LOGAR NO BOT: Verifique seu Token no .env");
    console.error(err);
});
