const LIMIT = 50;
const tooltip = document.getElementById("tooltip");

let offset = 0;
let loading = false;
let currentImages = [];
let currentIndex = 0;
let searchQuery = "";
let tooltipTimeout;
let sortBy = getCookie("sort_by") || "date-asc";

// --- Cookie Utils ---
function setCookie(name, value, days = 365) {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/`;
}

function getCookie(name) {
    return document.cookie
        .split("; ")
        .map(c => c.split("="))
        .find(([key]) => key === name)?.[1] || null;
}

// --- Load Content ---
async function updateUrl(event, path) {
    event.preventDefault();
    if (window.location.pathname === "/" + path) return;
    window.history.pushState({}, '', '/' + path);
    await loadContent();
    updateActiveFolderHighlight();
}


async function loadContent() {
    document.getElementById('loading').style.display = 'block';
    const path = window.location.pathname;
    await (path === "/" ? loadFolders() : loadImages());
    document.getElementById('loading').style.display = 'none';
}

async function loadFolders() {
    const folderList = document.getElementById('sidebar').querySelector('.sidebar-folders');
    const response = await fetch('/');
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    const incomingFolders = doc.querySelector('.sidebar-folders');
    if (incomingFolders) {
        folderList.innerHTML = incomingFolders.innerHTML;
        updateActiveFolderHighlight();
    } else {
        console.error("❌ sidebar-folders not found in response");
    }
}

function updateActiveFolderHighlight() {
    const currentPath = window.location.pathname;

    // Удаляем старую подсветку
    document.querySelectorAll('.folder-tree a.active-folder')
        .forEach(el => el.classList.remove('active-folder'));

    // Добавляем новую подсветку
    const selector = `.folder-tree a[href="${currentPath}"]`;
    const activeLink = document.querySelector(selector);

    if (activeLink) {
        activeLink.classList.add('active-folder');
        // Если элемент вне видимой области — скроллим его
        activeLink.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
}

// --- Image Gallery ---
async function loadImages() {
    loadFolders();
    offset = 0;
    currentImages = [];
    const gallery = document.getElementById('gallery');
    gallery.innerHTML = "";
    gallery.style.gridTemplateColumns = `repeat(${IMAGES_PER_ROW}, minmax(120px, 1fr))`;
    await loadMoreImages();
}

async function loadMoreImages(limit = LIMIT) {
    if (loading) return;
    loading = true;

    const [sort, order] = sortBy.split("-");
    const query = `/images${window.location.pathname}?limit=${limit}&offset=${offset}&search=${encodeURIComponent(searchQuery)}&sort_by=${sort}&order=${order}`;
    const images = await (await fetch(query)).json();
    if (!images.length) return loading = false;

    currentImages.push(...images);
    document.getElementById('gallery').insertAdjacentHTML("beforeend", renderImageCards(images));
    loadCheckboxState();
    images.forEach(img => updateStars(null, img.filename, img.metadata.rating || 0));
    offset += images.length;
    loading = false;
}

function renderImageCards(images) {
    return images.map((img, index) => `
        <div class="image-container" onclick="openFullscreen(${offset + index})"
             onmouseenter="showStars(event)" onmouseleave="hideStars(event)">
            <div class="image-buttons">
                <button class="copy-btn" onclick="copyToClipboard(event, '${escapeJS(img.metadata.prompt)}')">📋</button>
                <input type="checkbox" class="image-checkbox" data-filename="${img.filename}"
                       onclick="event.stopPropagation(); saveCheckboxState(event);">
                <button class="delete-btn" onclick="deleteThumbnail(event, '${img.filename}')">❌</button>
            </div>
            <div class="image-rating" style="opacity: 0;">
                ${[1,2,3,4,5].map(star => `
                    <span class="star" data-filename="${img.filename}" data-rating="${star}"
                          onclick="setRating(event, '${img.filename}', ${star})">
                        ${img.metadata.rating >= star ? "★" : "☆"}
                    </span>`).join('')}
            </div>
            <img src="/serve_thumbnail/${img.thumbnail}" alt="Image" loading="lazy"
                 onmouseenter="showTooltip(event, '${escapeJS(img.metadata.prompt)}')"
                 onmousemove="updateTooltipPosition(event)"
                 onmouseleave="hideTooltip()">
        </div>
    `).join('');
}

function filterImages() {
    searchQuery = document.getElementById("search-box").value.trim();
    setCookie("search_query", searchQuery);
    loadImages();
}

function loadSearchFromCookies() {
    const saved = getCookie("search_query");
    if (saved) {
        searchQuery = decodeURIComponent(saved);
        document.getElementById("search-box").value = searchQuery;
    }
}

// --- Tooltip ---
function escapeHTML(str) {
    return str.replace(/[&<>"']/g, m => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[m]));
}

function escapeJS(str) {
    return str.replace(/'/g, "\\'");
}

function showTooltip(event, text) {
    clearTimeout(tooltipTimeout);
    tooltip.innerHTML = `<div class="tooltip-text">${escapeHTML(text)}</div><div class="tooltip-hint">CTRL+C</div>`;
    tooltip.style.display = "block";
    tooltip.classList.add("visible");
    updateTooltipPosition(event);
}

function updateTooltipPosition(event) {
    const { clientX: x0, clientY: y0 } = event;
    const { offsetWidth: w, offsetHeight: h } = tooltip;

    let x = x0 + 15;
    let y = y0 + 15;

    if (x + w > window.innerWidth) x = window.innerWidth - w - 10;
    if (y + h > window.innerHeight) y = window.innerHeight - h - 10;

    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y + window.scrollY}px`;
}

function hideTooltip(event) {
    if (!event?.relatedTarget || !event.relatedTarget.closest("#gallery")) {
        clearTimeout(tooltipTimeout);
        tooltipTimeout = setTimeout(() => {
            tooltip.classList.remove("visible");
            setTimeout(() => tooltip.style.display = "none", 100);
        }, 200);
    }
}

function copyTooltipText() {
    const text = tooltip.querySelector(".tooltip-text")?.textContent?.trim();
    if (!text) return;

    navigator.clipboard.writeText(text).then(() => {
        tooltip.querySelector(".tooltip-text").textContent = "Copied!";
        tooltip.querySelector(".tooltip-hint").textContent = "";
        setTimeout(() => tooltip.innerHTML = `<div class="tooltip-text">${escapeHTML(text)}</div><div class="tooltip-hint">CTRL+C</div>`, 700);
    });
}

// --- Fullscreen View ---
function openFullscreen(index) {
    currentIndex = index;
    updateFullscreenView();
    document.getElementById('fullscreen-container').style.display = 'flex';
}

function closeFullscreen() {
    document.getElementById('fullscreen-container').style.display = 'none';
}

function updateFullscreenView() {
    const data = currentImages[currentIndex];
    if (!data) return;

    document.getElementById('fullscreen-img').src = `/serve_image/${data.filename}`;
    document.getElementById('fullscreen-prompt').dataset.prompt = data.metadata.prompt;
}

function prevImage() {
    if (currentIndex > 0) {
        currentIndex--;
        updateFullscreenView();
    }
}

async function nextImage() {
    if (++currentIndex >= currentImages.length) {
        await loadMoreImages();
    }
    if (currentIndex < currentImages.length) {
        updateFullscreenView();
    }
}

function copyToClipboard(event, text) {
    event.stopPropagation();
    navigator.clipboard.writeText(text);
}

function copyPromptFullscreen() {
    const prompt = document.getElementById('fullscreen-prompt').dataset.prompt;
    if (prompt) navigator.clipboard.writeText(prompt);
}

// --- Checkbox and Rating ---
function saveCheckboxState(event) {
    const cb = event.target;
    fetch("/update_metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: cb.dataset.filename, checked: cb.checked })
    }).catch(console.error);
}

function loadCheckboxState() {
    document.querySelectorAll(".image-checkbox").forEach(cb => {
        const img = currentImages.find(i => i.filename === cb.dataset.filename);
        if (img) cb.checked = !!img.metadata.checked;
    });
    updateImageOpacity();
}

function updateImageOpacity() {
    document.querySelectorAll(".image-checkbox").forEach(cb => {
        cb.closest(".image-container").classList.toggle("checked", cb.checked);
    });
}

function setRating(event, filename, rating) {
    event.stopPropagation();
    const img = currentImages.find(i => i.filename === filename);
    if (img) img.metadata.rating = rating;
    updateStars(null, filename, rating);

    fetch("/update_metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, rating })
    }).catch(console.error);
}

function updateStars(event, filename, rating) {
    if (event) event.stopPropagation();
    document.querySelectorAll(`.star[data-filename='${filename}']`).forEach(star => {
        star.textContent = star.dataset.rating <= rating ? "★" : "☆";
    });
}

function showStars(event) {
    event.currentTarget.querySelector(".image-rating").style.opacity = "1";
}

function hideStars(event) {
    event.currentTarget.querySelector(".image-rating").style.opacity = "0";
}

// --- Deletion ---
async function deleteThumbnail(event, filename) {
    event.stopPropagation();
    if (!confirm("Удалить изображение?")) return;

    const response = await fetch("/delete_image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename })
    });
    const result = await response.json();
    if (result.success) {
        event.target.closest(".image-container").remove();
    } else {
        alert("Ошибка удаления: " + (result.error || "неизвестная"));
    }
}

// --- UI Events ---
function changeSort() {
    sortBy = document.getElementById("sort-select").value;
    setCookie("sort_by", sortBy);
    loadImages();
}

function toggleFolder(event) {
    event.stopPropagation();
    const item = event.currentTarget.closest(".folder-item");
    const children = item.querySelector(".folder-children");
    const expanded = item.classList.toggle("expanded");
    children.classList.toggle("hidden", !expanded);
}

function updateToggleButtonPosition() {
    const sidebar = document.getElementById("sidebar");
    const toggleBtn = document.getElementById("menu-toggle");
    const icon = document.getElementById("menu-icon");

    toggleBtn.style.left = sidebar.classList.contains("hidden") ? "10px" : `${sidebar.offsetWidth + 10}px`;
    icon.textContent = sidebar.classList.contains("hidden") ? "⯈" : "⯇";
}

// --- Init ---
window.onload = function () {
    loadSearchFromCookies();
    loadContent();

    document.getElementById("scroll-to-top").classList.add("hidden");
    document.getElementById("menu-toggle").addEventListener("click", () => {
        document.getElementById("sidebar").classList.toggle("hidden");
        document.querySelector(".container").classList.toggle("sidebar-visible");
        updateToggleButtonPosition();
    });

    document.querySelectorAll(".folder-row").forEach(row => {
        if (row.dataset.hasChildren === "true") {
            row.addEventListener("click", toggleFolder);
        }
    });

    window.addEventListener("scroll", () => {
        if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) loadMoreImages();
        document.getElementById("scroll-to-top").classList.toggle("hidden", window.scrollY <= 300);
    });

    document.getElementById("gallery").addEventListener("mouseleave", hideTooltip);
    document.getElementById("gallery").addEventListener("mousemove", e => {
        if (tooltip.style.display === "block") updateTooltipPosition(e);
    });

    document.addEventListener("change", e => {
        if (e.target.classList.contains("image-checkbox")) {
            saveCheckboxState(e);
            updateImageOpacity();
        }
    });

    document.addEventListener("keydown", e => {
        if (document.getElementById("fullscreen-container").style.display === "flex") {
            if (e.key === "ArrowLeft") prevImage();
            if (e.key === "ArrowRight") nextImage();
            if (e.key === "Escape") closeFullscreen();
        }
        if (e.ctrlKey && (e.key.toLowerCase() === "c" || e.key.toLowerCase() === "с")) {
            document.getElementById("fullscreen-container").style.display === "flex"
                ? copyPromptFullscreen()
                : copyTooltipText();
        }
    });

    document.getElementById("fullscreen-container").addEventListener("click", e => {
        if (!e.target.closest(".fullscreen-image-wrapper") && !e.target.closest(".copy-btn") &&
            !e.target.closest(".close-btn") && !e.target.closest(".nav-arrow")) {
            closeFullscreen();
        }
    });

    updateToggleButtonPosition();
};

window.onpopstate = () => {
    loadContent();
    loadCheckboxState();
    document.getElementById("scroll-to-top").classList.add("hidden");
};