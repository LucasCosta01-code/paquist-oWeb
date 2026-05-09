const API_BASE = '/api';
const MEMBER_ID_TARGET = '1492527673531171019';

// Tratar erros de Login
window.onload = () => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('error') === 'not_in_faction') {
        alert("⚠️ ACESSO NEGADO: Você precisa estar no Servidor do Discord da Tropa Paquistão para fazer login no site!");
        window.history.replaceState({}, document.title, "/");
    } else if (params.get('error') === 'bot_not_ready') {
        alert("⚠️ ERRO: O sistema do bot ainda está conectando. Tente novamente em alguns segundos.");
        window.history.replaceState({}, document.title, "/");
    }
};
let currentUser = null;

// Auth Check
async function checkAuth() {
    try {
        const res = await fetch(`${API_BASE}/auth/me`);
        if (res.ok) {
            const user = await res.json();
            if (user && user.id) {
                currentUser = user;
                document.getElementById('btnDiscordLogin').style.display = 'none';
                const widget = document.getElementById('userWidget');
                widget.classList.add('active');
                document.getElementById('userName').textContent = user.username;
                document.getElementById('userAvatar').src = `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png`;
                
                // Pre-fill forms
                const dIds = document.querySelectorAll('input[name="discordId"], input[name="discord"]');
                dIds.forEach(el => { el.value = user.username; el.readOnly = true; });
                
                const dNames = document.querySelectorAll('input[name="author"], input[name="nickname"]');
                dNames.forEach(el => { el.value = user.username; });
            }
        }
    } catch (e) { console.log('Not logged in'); }
}
checkAuth();

function logout() {
    window.location.href = `${API_BASE}/auth/logout`;
}

// Side-Panel Modal Functions
const openModal = (id) => document.getElementById(id).classList.add('active');
const closeModal = (id) => document.getElementById(id).classList.remove('active');

// Event Listeners for Modals
document.getElementById("openModal").onclick = () => openModal("registerModal");
document.getElementById("openOrderModal").onclick = () => openModal("orderModal");
document.getElementById("openVideoModal").onclick = () => openModal("videoModal");
document.getElementById("openGalleryPostModal").onclick = () => openModal("galleryPostModal");

// Close panel when clicking outside
window.onclick = (e) => { 
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
    if (e.target.id === 'mediaLightbox') {
        closeLightbox();
    }
};

// Lightbox Functions
function openLightbox(type, url) {
    const lightbox = document.getElementById('mediaLightbox');
    const contentBox = document.getElementById('lightboxContent');
    
    if (type === 'image') {
        contentBox.innerHTML = `<img src="${url}" alt="Visualização">`;
    } else if (type === 'video') {
        // Convert YouTube URL to embed format if needed
        let embedUrl = url;
        const ytRegex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i;
        const match = url.match(ytRegex);
        if (match && match[1]) {
            // Remove o vermelho usando color=white e melhora UX com modestbranding e rel=0
            embedUrl = `https://www.youtube.com/embed/${match[1]}?autoplay=1&color=white&modestbranding=1&rel=0`;
            contentBox.innerHTML = `<iframe width="100%" height="100%" src="${embedUrl}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>`;
        } else {
            // Se for outro tipo de vídeo (MP4), usar tag de vídeo
            if (url.match(/\.(mp4|webm|ogg)$/i)) {
                 contentBox.innerHTML = `<video width="100%" height="100%" controls autoplay><source src="${url}" type="video/mp4"></video>`;
            } else {
                 // Fallback genérico iframe
                 contentBox.innerHTML = `<iframe width="100%" height="100%" src="${url}" frameborder="0" allowfullscreen></iframe>`;
            }
        }
    }
    
    lightbox.classList.add('active');
}

function closeLightbox() {
    const lightbox = document.getElementById('mediaLightbox');
    const contentBox = document.getElementById('lightboxContent');
    lightbox.classList.remove('active');
    setTimeout(() => contentBox.innerHTML = '', 300); // Clear content to stop video playing
}

// 3D Parallax Effect & UX Dynamic Blur
window.addEventListener('scroll', () => {
    const bg = document.querySelector('.background-container');
    const scrollPos = window.scrollY;
    if (bg) {
        // Efeito 3D: A imagem dá um zoom e desce levemente conforme rola a página
        // Efeito UX: A imagem vai ficando borrada (blur) conforme desce, focando a atenção na leitura!
        const blurValue = Math.min(scrollPos * 0.015, 10); // Borra até no máximo 10px
        bg.style.transform = `translateY(${scrollPos * 0.15}px) scale(${1 + scrollPos * 0.0003})`;
        bg.style.filter = `blur(${blurValue}px) brightness(${1 - scrollPos * 0.0005})`; // Escurece levemente também
    }
});

// Content Sync
async function syncAll() {
    try {
        const [gallery, videos, news, stats] = await Promise.all([
            fetch(`${API_BASE}/gallery`).then(r => r.json()).catch(() => []),
            fetch(`${API_BASE}/videos`).then(r => r.json()).catch(() => []),
            fetch(`${API_BASE}/news`).then(r => r.json()).catch(() => []),
            fetch(`${API_BASE}/stats`).then(r => r.json()).catch(() => ({ members: 20 }))
        ]);

        const memberEl = document.getElementById("memberCount");
        if (memberEl && stats.members > 0) {
            memberEl.textContent = `+${stats.members}`;
        }

        renderNews(news);
        renderGallery(gallery);
        renderVideos(videos);
    } catch (err) {
        console.error("Erro ao sincronizar dados:", err);
    }
}

function renderNews(items) {
    const feed = document.getElementById("newsFeed");
    const section = document.getElementById("noticias");
    if (!feed || !items || !section) return;

    if (items.length === 0) {
        section.style.display = 'none';
        feed.innerHTML = '';
    } else {
        section.style.display = 'block';
        feed.innerHTML = items.reverse().map(item => `
            <div class="news-card">
                <div class="news-header">
                    <img src="${item.authorAvatar || ''}" class="author-avatar" onerror="this.src='https://via.placeholder.com/50'">
                    <div>
                        <h4 style="color:var(--primary-color)">${item.author}</h4>
                        <span style="font-size:0.7rem; opacity:0.5">${new Date(item.date).toLocaleString()}</span>
                    </div>
                </div>
                <div class="news-body">${item.content}</div>
            </div>
        `).join('');
    }
}

function renderGallery(items) {
    const feed = document.getElementById("galleryFeed");
    const section = document.getElementById("galeria");
    if (!feed || !items || !section) return;

    if (items.length === 0) {
        section.style.display = 'none';
        feed.innerHTML = '';
    } else {
        section.style.display = 'block';
        feed.innerHTML = items.reverse().map(item => `
            <div class="gallery-item-card" style="cursor:pointer;" onclick="openLightbox('image', '${item.content}')">
                <div class="gallery-item-media">
                    <img src="${item.content}" alt="Galeria" onerror="this.src='https://via.placeholder.com/400'">
                </div>
                <div class="gallery-item-info" style="padding: 15px; background: rgba(0,0,0,0.5)">
                    <p style="font-size: 0.8rem; font-weight: 700;">Autor: <span class="logo-green">${item.author}</span></p>
                </div>
            </div>
        `).join('');
    }
}

function renderVideos(items) {
    const grid = document.querySelector(".video-grid");
    const section = document.getElementById("videos");
    if (!grid || !items || !section) return;

    if (items.length === 0) {
        section.style.display = 'none';
        grid.innerHTML = '';
    } else {
        section.style.display = 'block';
        grid.innerHTML = items.reverse().map(item => {
            const thumbUrl = item.thumb || "https://images.unsplash.com/photo-1614028674026-a65e31bfd27c?auto=format&fit=crop&q=80&w=800";
            return `
            <div class="video-card">
                <div class="video-thumb" style="cursor:pointer;" onclick="openLightbox('video', '${item.link}')">
                    <img src="${thumbUrl}" alt="Thumbnail">
                    <div class="play-btn"><i class="fas fa-play-circle"></i></div>
                </div>
                <div class="video-info">
                    <h3 style="font-size: 1.1rem; margin-bottom: 5px;">${item.title || "Vídeo da Tropa"}</h3>
                    <p style="font-size: 0.8rem; opacity: 0.7;">Enviado por: ${item.author}</p>
                    <a href="javascript:void(0)" onclick="openLightbox('video', '${item.link}')" style="color: var(--primary-color); text-decoration: none; font-size: 0.8rem; margin-top: 10px; display: inline-block;">VER VÍDEO <i class="fas fa-play"></i></a>
                </div>
            </div>
            `;
        }).join('');
    }
}



// Submissions
async function submitData(type, payload, statusId) {
    const statusEl = document.getElementById(statusId);
    statusEl.textContent = "🚀 Enviando...";
    statusEl.style.color = "var(--primary-color)";
    
    // Inject auth data if available
    if (currentUser) {
        payload._discordUser = currentUser.username;
        payload._discordId = currentUser.id;
    }

    try {
        const res = await fetch(`${API_BASE}/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type, data: payload })
        });
        if (res.ok) {
            statusEl.textContent = "✅ Sucesso! O bot processou seu pedido.";
            syncAll();
            return true;
        } else {
            const err = await res.json();
            statusEl.textContent = `❌ Erro: ${err.error || 'Falha ao processar'}`;
            return false;
        }
    } catch (e) {
        statusEl.textContent = "❌ Erro ao conectar com o servidor.";
    }
    return false;
}

// Form Handlers
document.getElementById("registrationForm").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    if (await submitData('alistamento', data, "statusMessage")) {
        e.target.reset();
        setTimeout(() => closeModal("registerModal"), 2000);
    }
};

document.getElementById("orderForm").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    if (await submitData('order', data, "orderStatusMessage")) {
        e.target.reset();
        setTimeout(() => closeModal("orderModal"), 2000);
    }
};

document.getElementById("videoForm").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    if (await submitData('video', data, "videoStatusMessage")) {
        e.target.reset();
        setTimeout(() => closeModal("videoModal"), 2000);
    }
};

document.getElementById("galleryPostForm").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    if (await submitData('gallery', data, "galleryStatusMessage")) {
        e.target.reset();
        setTimeout(() => closeModal("galleryPostModal"), 2000);
    }
};

// Auto-sync every 5s (Quase tempo real)
syncAll();
setInterval(syncAll, 5000);


// Smooth Scroll
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.onclick = (e) => {
        e.preventDefault();
        const target = document.querySelector(anchor.getAttribute('href'));
        if (target) target.scrollIntoView({ behavior: 'smooth' });
    }
});
