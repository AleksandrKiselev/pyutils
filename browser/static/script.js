const LIMIT = 50;
const tooltip = document.getElementById("tooltip");

let offset = 0;
let loading = false;
let currentImages = [];
let currentIndex = 0;
let searchQuery = "";
let tooltipTimeout;
let sortBy = "date-asc";
let allTags = [];
let suggestionIndex = -1;


// --- Load Content ---
async function updateUrl(event, path) {
    event.preventDefault();
    if (window.location.pathname === "/" + path) return;
    saveGalleryState();
    window.history.pushState({}, '', '/' + path);
    await loadContent();
    updateActiveFolderHighlight();
}


async function loadContent() {
    document.getElementById('loading').style.display = 'block';
    const path = window.location.pathname;
    restoreGalleryState();
    await (path === "/" ? loadFolders() : loadImages());
    document.getElementById('loading').style.display = 'none';
    fetchAllTags()
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

function findFolderNode(path) {
    const parts = path.split("/").filter(Boolean);
    let fullPath = "";
    let node = FOLDER_TREE;

    for (let i = 0; i < parts.length; i++) {
        fullPath = fullPath ? `${fullPath}/${parts[i]}` : parts[i];

        const parent = node[fullPath];
        if (!parent) return null;

        // Если это последний элемент — вернём его
        if (i === parts.length - 1) {
            return parent;
        }

        // Иначе спускаемся глубже
        node = parent.children;
        if (!node || typeof node !== "object") return null;
    }

    return null;
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
    return images.map((img, index) => {
        const prompt = escapeJS(img.metadata.prompt);
        const tagsJson = JSON.stringify(img.metadata.tags || []).replace(/"/g, '&quot;');

        return `
            <div class="image-container" onclick="openFullscreen(${offset + index})"
                 onmouseenter="showStars(event)" onmouseleave="hideStars(event)">
                <div class="image-buttons">
                    <button class="copy-btn" onclick="copyToClipboard(event, '${prompt}')">📋</button>
                    <button class="copy-favorites-btn" onclick="copyToFavorites(event, '${img.filename}')">⭐</button>
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
                     onmouseenter="showTooltip(event, '${prompt}', ${tagsJson})"
                     onmousemove="updateTooltipPosition(event)"
                     onmouseleave="hideTooltip()">
            </div>`;
        }).join('');
}

function filterImages() {
    searchQuery = document.getElementById("search-box").value.trim();
    loadImages();
}

function saveGalleryState() {
    const state = {
        currentPath: window.location.pathname,
        scrollY: window.scrollY,
        searchQuery: document.getElementById("search-box").value.trim(),
        sortBy: document.getElementById("sort-select").value,
        sidebarVisible: !document.getElementById("sidebar").classList.contains("hidden")
    };

    localStorage.setItem("galleryState", JSON.stringify(state));
}


function restoreGalleryState() {
    const raw = localStorage.getItem("galleryState");
    if (!raw) return;

    try {
        const state = JSON.parse(raw);

        if (state.searchQuery !== undefined) {
            searchQuery = state.searchQuery;
            document.getElementById("search-box").value = searchQuery;
        }

        if (state.sortBy) {
            sortBy = state.sortBy;
            document.getElementById("sort-select").value = sortBy;
        }

        if (typeof state.sidebarVisible === "boolean") {
            const sidebar = document.getElementById("sidebar");
            const container = document.querySelector(".container");
            sidebar.classList.toggle("hidden", !state.sidebarVisible);
            container.classList.toggle("sidebar-visible", state.sidebarVisible);
        }

        setTimeout(() => {
            window.scrollTo(0, state.scrollY || 0);
        }, 0);
    } catch (e) {
        console.warn("Не удалось восстановить галерею:", e);
    }
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function uncheckAllCheckboxes() {
    const checkboxes = document.querySelectorAll(".image-checkbox:checked");
    if (!checkboxes.length) return;

    const filenames = [];
    checkboxes.forEach(cb => {
        cb.checked = false;
        filenames.push(cb.dataset.filename);

        const container = cb.closest(".image-container");
        if (container) container.classList.remove("checked");

        const img = currentImages.find(i => i.filename === cb.dataset.filename);
        if (img) img.metadata.checked = false;
    });

    fetch("/update_metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filenames, checked: false })
    }).catch(console.error);
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

function showTooltip(event, text, tags = []) {
    clearTimeout(tooltipTimeout);

    if (tags.length) {
        const pillsHTML = `<div class="tooltip-tags">${tags.map(tag =>
            `<span class="tag-pill tooltip-pill">${escapeHTML(tag)}</span>`).join("")}</div>`;

        tooltip.innerHTML = `<div class="tooltip-text">${escapeHTML(text)}</div>${pillsHTML}<div class="tooltip-hint">CTRL+C</div>`;
    } else {
        tooltip.innerHTML = `<div class="tooltip-text">${escapeHTML(text)}</div><div class="tooltip-hint">CTRL+C</div>`;
    }


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

    const promptEl = document.getElementById('fullscreen-prompt');
    promptEl.dataset.prompt = data.metadata.prompt;
    promptEl.textContent = data.metadata.prompt || "";

    const checkbox = document.getElementById('fullscreen-checkbox');
    const miniCheckbox = document.querySelector(`.image-checkbox[data-filename="${data.filename}"]`);
    const isChecked = miniCheckbox ? miniCheckbox.checked : !!data.metadata.checked;

    checkbox.dataset.filename = data.filename;
    checkbox.checked = isChecked;

    const wrapper = document.querySelector(".fullscreen-image-wrapper");
    wrapper.classList.toggle("checked", isChecked);

    const tagInput = document.getElementById("fullscreen-tags");
    tagInput.value = (data.metadata.tags || []).join(", ");
    const display = document.getElementById("fullscreen-tags-display");
    display.innerHTML = "";
    renderFullscreenTagPills(data.metadata.tags || []);

    checkbox.onchange = function () {
        const checked = checkbox.checked;
        data.metadata.checked = checked;

        wrapper.classList.toggle("checked", checked);

        // синхронизация с миниатюрой
        if (miniCheckbox) {
            miniCheckbox.checked = checked;
            const container = miniCheckbox.closest(".image-container");
            if (container) {
                container.classList.toggle("checked", checked);
            }
        }

        fetch("/update_metadata", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: data.filename, checked })
        }).catch(console.error);
    };
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

function rebindFullscreenIndices() {
    const containers = document.querySelectorAll("#gallery .image-container");
    containers.forEach((container, i) => {
        container.setAttribute("onclick", `openFullscreen(${i})`);
    });
}

function deleteFullscreen() {
    const data = currentImages[currentIndex];
    if (!data || !confirm("Удалить изображение?")) return;

    fetch("/delete_image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: data.filename })
    })
    .then(res => res.json())
    .then(async result => {
        if (result.success) {
            // Удаляем миниатюру
            const thumb = document.querySelector(`.image-checkbox[data-filename="${data.filename}"]`)?.closest(".image-container");
            if (thumb) thumb.remove();

            // Удаляем из массива
            currentImages.splice(currentIndex, 1);
            rebindFullscreenIndices();

            // Переход к следующему изображению или закрыть, если всё удалено
            if (currentImages.length === 0) {
                closeFullscreen();
            } else if (currentIndex >= currentImages.length) {
                currentIndex = currentImages.length - 1;
                updateFullscreenView();
            } else {
                updateFullscreenView();
            }
        } else {
            alert("Ошибка удаления: " + (result.error || "неизвестная"));
        }
    });
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
        const container = cb.closest(".image-container");
        if (container) {
            container.classList.toggle("checked", cb.checked);
        }
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

// --- Tags ---
function renderFullscreenTagPills(tags) {
    const display = document.getElementById("fullscreen-tags-display");
    display.innerHTML = "";

    tags.forEach(tag => {
        const span = document.createElement("span");
        span.className = "tag-pill";
        span.textContent = tag;
        span.onclick = () => {
            document.getElementById("search-box").value = "t:" + tag;
            filterImages();
            closeFullscreen();
        };
        display.appendChild(span);
    });
}

function saveTags() {
    const input = document.getElementById("fullscreen-tags");
    const tags = input.value.split(",").map(t => t.trim()).filter(Boolean);
    const data = currentImages[currentIndex];
    if (!data) return;

    data.metadata.tags = tags;
    const container = document.querySelector(`.image-container [data-filename="${data.filename}"]`)?.closest(".image-container");
    if (container) {
        const imgEl = container.querySelector("img");
        if (imgEl) {
            const prompt = escapeJS(data.metadata.prompt);
            const tagsJson = JSON.stringify(tags)
                .replace(/\\/g, "\\\\")
                .replace(/'/g, "\\'")
                .replace(/</g, "\\u003c")
                .replace(/>/g, "\\u003e");
            imgEl.setAttribute("onmouseenter", `showTooltip(event, '${prompt}', ${tagsJson})`);
        }
    }

    // Обновим allTags, если были новые
    tags.forEach(tag => {
        if (!allTags.includes(tag)) {
            allTags.push(tag);
        }
    });

    fetch("/update_metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: data.filename, tags })
    }).then(() => {
        console.log("✅ Теги обновлены:", tags);
    }).catch(console.error);

    renderFullscreenTagPills(tags);

    const indicator = document.getElementById("tags-saved-indicator");
    if (indicator) {
        indicator.classList.remove("hidden");
        indicator.classList.add("visible");
        setTimeout(() => {
            indicator.classList.remove("visible");
            indicator.classList.add("hidden");
        }, 1000);
    }

    input.focus();
}

async function fetchAllTags() {
    try {
        const res = await fetch('/all_tags');
        allTags = await res.json();
    } catch (err) {
        console.error("Ошибка загрузки тегов:", err);
    }
}

const tagsInput = document.getElementById("fullscreen-tags");

tagsInput.addEventListener("input", () => {
    const value = tagsInput.value.split(",").pop().trim().toLowerCase();
    closeTagSuggestions();

    if (!value) return;

    const suggestions = allTags.filter(tag => tag.toLowerCase().startsWith(value)).slice(0, 10);

    const container = document.createElement("div");
    container.className = "tag-suggestion-container";

    suggestions.forEach(tag => {
        const div = document.createElement("div");
        div.className = "tag-suggestion";
        div.innerHTML = `<strong>${tag.slice(0, value.length)}</strong>${tag.slice(value.length)}`;
        div.onclick = () => {
            const parts = tagsInput.value.split(",");
            parts[parts.length - 1] = tag;
            tagsInput.value = parts.join(", ") + ", ";
            closeTagSuggestions();
            tagsInput.focus();
        };
        container.appendChild(div);
    });

    suggestionIndex = -1;

    tagsInput.parentNode.appendChild(container);
});

tagsInput.addEventListener("blur", () => {
    setTimeout(closeTagSuggestions, 150); // задержка, чтобы клик по подсказке успел сработать
});

tagsInput.addEventListener("keydown", e => {
    const container = document.querySelector(".tag-suggestion-container");
    if (!container) return;

    const items = container.querySelectorAll(".tag-suggestion");
    if (!items.length) return;

    if (e.key === "ArrowDown") {
        e.preventDefault();
        suggestionIndex = (suggestionIndex + 1) % items.length;
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        suggestionIndex = (suggestionIndex - 1 + items.length) % items.length;
    } else if (e.key === "Enter") {
        if (suggestionIndex >= 0 && suggestionIndex < items.length) {
            e.preventDefault();
            items[suggestionIndex].click();
        }
    } else if (e.key === "Escape") {
        closeTagSuggestions();
    } else if (e.key === "Backspace" && e.ctrlKey) {
        e.preventDefault();
        const pos = tagsInput.selectionStart;
        const before = tagsInput.value.slice(0, pos);
        const after = tagsInput.value.slice(tagsInput.selectionEnd);
        const lastComma = before.lastIndexOf(",");

        let newBefore;
        if (lastComma >= 0) {
            newBefore = before.slice(0, lastComma).replace(/\s+$/, "");
        } else {
            newBefore = ""; // если вообще нет запятой — удаляем всё
        }

        tagsInput.value = newBefore + after;
        const newPos = newBefore.length;
        tagsInput.setSelectionRange(newPos, newPos);
    }

    // подсветка активного
    items.forEach((el, i) => {
        el.classList.toggle("active", i === suggestionIndex);
    });
});


function closeTagSuggestions() {
    const existing = document.querySelector(".tag-suggestion-container");
    if (existing) existing.remove();
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

// --- Copy To Favorites ---
function copyToFavorites(event, filename) {
    event.stopPropagation();
    fetch("/copy_to_favorites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename })
    })
    .then(res => res.json())
    .then(result => {
        if (result.success) {
            console.log(`✅ Скопировано в "favorites": ${filename}`);
        } else {
            alert("Ошибка копирования: " + (result.error || "неизвестная"));
        }
    })
    .catch(err => {
        alert("Ошибка соединения: " + err);
    });
}

function copyToFavoritesFullscreen() {
    const data = currentImages[currentIndex];
    if (!data) return;
    copyToFavorites({ stopPropagation: () => {} }, data.filename);
}


// --- UI Events ---
function changeSort() {
    sortBy = document.getElementById("sort-select").value;
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
    const btn = document.getElementById("menu-toggle");
    const icon = document.getElementById("menu-icon");

    const isVisible = document.body.classList.contains("sidebar-visible");
    btn.style.left = isVisible ? "220px" : "10px";
    icon.textContent = isVisible ? "⯇" : "⯈";
}

// --- Init ---
window.onload = function () {
    const saved = localStorage.getItem("galleryState");
    if (saved) {
        try {
            const state = JSON.parse(saved);
            if (state.currentPath && state.currentPath !== "/") {
                window.history.replaceState({}, '', state.currentPath);
            }
            if (typeof state.sidebarVisible === "boolean") {
                const sidebar = document.getElementById("sidebar");
                const container = document.querySelector(".container");
                sidebar.classList.toggle("hidden", !state.sidebarVisible);
                container.classList.toggle("sidebar-visible", state.sidebarVisible);
            }
        } catch (e) {
            console.warn("Ошибка восстановления пути:", e);
        }
    }

    loadContent();

    document.getElementById("scroll-to-top").classList.add("hidden");

    document.getElementById("menu-toggle").addEventListener("click", () => {
        document.body.classList.toggle("sidebar-visible");
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

    window.addEventListener("beforeunload", saveGalleryState);

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
        const isFullscreen = document.getElementById("fullscreen-container").style.display === "flex";
        const tagInput = document.getElementById("fullscreen-tags");
        const isTagInputFocused = document.activeElement === tagInput;

        if (isFullscreen) {
            if (!isTagInputFocused) {
                if (e.key === "ArrowLeft") prevImage();
                if (e.key === "ArrowRight") nextImage();
                if (e.key === "Delete") deleteFullscreen();
            }
            if (e.key === "Escape") {
                if (isTagInputFocused) {
                    tagInput.blur();
                } else {
                    closeFullscreen();
                }
            }


            if (isTagInputFocused) {
                const suggestionBox = document.querySelector(".tag-suggestion-container");
                const suggestions = suggestionBox?.querySelectorAll(".tag-suggestion") || [];

                if (e.key === "ArrowDown") {
                    e.preventDefault();
                    suggestionIndex = (suggestionIndex + 1) % suggestions.length;
                } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    suggestionIndex = (suggestionIndex - 1 + suggestions.length) % suggestions.length;
                } else if (e.key === "Escape") {
                    closeTagSuggestions();
                    suggestionIndex = -1;
                } else if (e.key === "Enter") {
                    if (suggestionIndex >= 0 && suggestionIndex < suggestions.length) {
                        e.preventDefault();
                        suggestions[suggestionIndex].click(); // вставит тег, но НЕ сохранит
                        return;
                    }
                    e.preventDefault();
                    saveTags(); // обычный Enter, когда подсказок нет
                }

                // Подсветка активного
                suggestions.forEach((el, i) => {
                    el.classList.toggle("active", i === suggestionIndex);
                });
            }
        }

        if (e.ctrlKey && (e.key.toLowerCase() === "c" || e.key.toLowerCase() === "с")) {
            const selection = window.getSelection();
            const isTextSelected = selection && selection.toString().length > 0;

            // Если фокус на поле ввода и есть выделенный текст — ничего не перехватываем
            if (isTagInputFocused && isTextSelected) return;

            // Иначе применяем поведение как раньше
            isFullscreen ? copyPromptFullscreen() : copyTooltipText();
        }
    });

    document.getElementById("fullscreen-container").addEventListener("click", e => {
        const isOutside = !e.target.closest(".fullscreen-image-wrapper")
            && !e.target.closest(".nav-arrow")
            && !e.target.closest(".tag-suggestion-container");
        if (isOutside) closeFullscreen();
    });

    updateToggleButtonPosition();
};

window.onpopstate = () => {
    loadContent();
    loadCheckboxState();
    document.getElementById("scroll-to-top").classList.add("hidden");
};