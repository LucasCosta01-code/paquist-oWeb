const API_BASE = '/api';
const MEMBER_ID_TARGET = '1492527673531171019';

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
};

// Content Sync
async function syncAll() {
    try {
        const [gallery, videos, news] = await Promise.all([
            fetch(`${API_BASE}/gallery`).then(r => r.json()).catch(() => []),
            fetch(`${API_BASE}/videos`).then(r => r.json()).catch(() => []),
            fetch(`${API_BASE}/news`).then(r => r.json()).catch(() => [])
        ]);

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
            <div class="gallery-item-card">
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
                <div class="video-thumb">
                    <img src="${thumbUrl}" alt="Thumbnail">
                    <a href="${item.link}" target="_blank" class="play-btn"><i class="fas fa-play-circle"></i></a>
                </div>
                <div class="video-info">
                    <h3 style="font-size: 1.1rem; margin-bottom: 5px;">${item.title || "Vídeo da Tropa"}</h3>
                    <p style="font-size: 0.8rem; opacity: 0.7;">Enviado por: ${item.author}</p>
                    <a href="${item.link}" target="_blank" style="color: var(--primary-color); text-decoration: none; font-size: 0.8rem; margin-top: 10px; display: inline-block;">VER NO YOUTUBE <i class="fas fa-external-link-alt"></i></a>
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
