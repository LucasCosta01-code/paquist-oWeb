const { Client, GatewayIntentBits } = require('discord.js');
require('dotenv').config();

const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages] });

client.once('ready', async () => {
    try {
        const channel = await client.channels.fetch('1502504591097335828');
        const message = await channel.messages.fetch('1502540891674513518');
        if (message.attachments.size > 0) {
            console.log("URL_DA_IMAGEM:", message.attachments.first().url);
        } else {
            console.log("Nenhum anexo encontrado nessa mensagem.");
        }
    } catch (e) {
        console.error("Erro ao buscar:", e);
    }
    client.destroy();
});

client.login(process.env.DISCORD_TOKEN);
