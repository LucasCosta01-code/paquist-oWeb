require('dotenv').config();
const { Client, GatewayIntentBits, EmbedBuilder, Partials } = require('discord.js');
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const bodyParser = require('body-parser');

console.log("-----------------------------------------");
console.log("🚀 TROPA PAQUISTÃO - INICIANDO SISTEMA...");
console.log("-----------------------------------------");

// Database Setup
const DB_PATH = path.join(__dirname, 'database.json');

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
app.use(cors());
app.use(bodyParser.json());
app.use(express.static(__dirname)); 

// API Endpoints
app.get('/api/gallery', (req, res) => res.json(getDB().gallery));
app.get('/api/videos', (req, res) => res.json(getDB().videos));
app.get('/api/news', (req, res) => res.json(getDB().news));

app.post('/api/submit', async (req, res) => {
    const { type, data } = req.body;
    const channelId = type === 'order' ? process.env.CHANNEL_ORDERS : 
                    type === 'video' ? process.env.CHANNEL_VIDEOS : 
                    type === 'gallery' ? process.env.CHANNEL_GALLERY : 
                    process.env.CHANNEL_ALISTAMENTO;

    const colors = { alistamento: 0x00ff88, order: 0xf39c12, gallery: 0x00ff88, video: 0x00ff88 };

    try {
        const channel = await client.channels.fetch(channelId);
        const fields = Object.keys(data).map(key => ({ name: key, value: String(data[key]), inline: true }));
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
        GatewayIntentBits.MessageContent
    ] 
});

const TARGET_CHANNEL_ID = '1502504591097335828';

client.on('ready', async () => {
    console.log(`✅ BOT ONLINE: Logado como ${client.user.tag}`);
    console.log(`📡 Sincronizando o histórico completo do canal ${TARGET_CHANNEL_ID}...`);

    try {
        const channel = await client.channels.fetch(TARGET_CHANNEL_ID);
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



const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🌐 SITE ONLINE: Acesse em http://localhost:${PORT}`);
    console.log("-----------------------------------------");
});

client.login(process.env.DISCORD_TOKEN).catch(err => {
    console.error("❌ ERRO AO LOGAR NO BOT: Verifique seu Token no .env");
    console.error(err);
});
