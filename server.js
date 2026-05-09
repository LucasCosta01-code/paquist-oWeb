require('dotenv').config();
const { Client, GatewayIntentBits, EmbedBuilder, Partials } = require('discord.js');
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
app.get('/api/profile', (req, res) => {
    if (!req.cookies.discordUser) {
        return res.status(401).json({ error: 'Not logged in' });
    }
    const user = JSON.parse(req.cookies.discordUser);
    
    const volumePath = process.env.RAILWAY_VOLUME_MOUNT_PATH || __dirname;
    const dbPath = path.join(volumePath, 'faccao.db');
    
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
            return res.json({ registered: false, discord: user });
        }
        
        db.all("SELECT tipo, SUM(quantidade) as total FROM entregas_meta WHERE discord_id = ? GROUP BY tipo", [user.id], (err, metas) => {
            db.close();
            const metaTotals = { c4: 0, plasticos: 0, colete: 0, corda: 0, capuz: 0 };
            if (metas) {
                metas.forEach(m => metaTotals[m.tipo] = m.total);
            }
            
            res.json({
                registered: true,
                discord: user,
                stats: row,
                metas: metaTotals
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

app.get('/api/auth/me', (req, res) => {
    if (req.cookies.discordUser) {
        res.json(JSON.parse(req.cookies.discordUser));
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

        await channel.send({ embeds: [embed] });
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
    console.log(`✅ BOT ONLINE: Logado como ${client.user.tag}`);
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
        
        const db = { gallery: [], videos: [], news: [] };

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
