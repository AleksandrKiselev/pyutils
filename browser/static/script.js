const LIMIT = 50;
const tooltip = document.getElementById("tooltip");

let offset = 0;
let loading = false;
let currentImages = [];
let currentIndex = 0;
let searchQuery = "";
let tooltipTimeout;
let sortBy = "date-asc";


function setCookie(name, value, days) {
    let expires = "";
    if (days) {
        const date = new Date();
        date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + encodeURIComponent(value) + expires + "; path=/";
}

function getCookie(name) {
    const cookies = document.cookie.split("; ");
    for (const cookie of cookies) {
        const [key, value] = cookie.split("=");
        if (key === name) {
            return decodeURIComponent(value);
        }
    }
    return null;
}

async function updateUrl(event, path) {
    event.preventDefault();
    if (window.location.pathname === "/" + path) return;
    window.history.pushState({}, '', '/' + path);
    await loadContent();
}

async function loadContent() {
    document.getElementById('loading').style.display = 'block';

    const path = window.location.pathname;

    if (path === "/") {
        await loadFolders();
    } else {
        await loadImages();
    }

    document.getElementById('loading').style.display = 'none';
}

async function loadFolders() {
    const folderList = document.getElementById('folder-list');
    const response = await fetch('/');
    const parser = new DOMParser();
    const doc = parser.parseFromString(await response.text(), 'text/html');
    folderList.innerHTML = doc.querySelector('.folder-list').innerHTML;
}

function filterImages() {
    searchQuery = document.getElementById("search-box").value.trim();
    setCookie("search_query", searchQuery, 365);  // Сохраняем в куки
    loadImages();
}

function loadSearchFromCookies() {
    const savedSearch = getCookie("search_query");
    if (savedSearch) {
        searchQuery = savedSearch;
        document.getElementById("search-box").value = searchQuery;
    }
}

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
    const response = await fetch(`/images${window.location.pathname}?limit=${limit}&offset=${offset}&search=${encodeURIComponent(searchQuery)}&sort_by=${sort}&order=${order}`);
    const images = await response.json();

    if (images.length === 0) {
        loading = false;
        return;
    }

    currentImages.push(...images);

    document.getElementById('gallery').innerHTML += images.map((img, index) => `
        <div class="image-container" onclick="openFullscreen(${offset + index})"
                onmouseenter="showStars(event)" onmouseleave="hideStars(event)">
            <div class="image-buttons">
                <button class="copy-btn" onclick="copyToClipboard(event, '${escapeHTMLForJS(img.metadata.prompt)}')">📋</button>
                <input type="checkbox" class="image-checkbox" data-filename="${img.filename}"
                    onclick="event.stopPropagation(); saveCheckboxState(event);">
                <button class="delete-btn" onclick="deleteThumbnail(event, '${img.filename}')">❌</button>
            </div>
            <div class="image-rating" style="opacity: 0;">
                ${[1, 2, 3, 4, 5].map(star => `
                    <span class="star" data-filename="${img.filename}" data-rating="${star}"
                        onclick="setRating(event, '${img.filename}', ${star})">
                        ${img.metadata.rating >= star ? "★" : "☆"}
                    </span>
                `).join('')}
            </div>
            <img src="/serve_thumbnail/${img.thumbnail}" alt="Image" loading="lazy"
                onmouseenter="showTooltip(event, '${escapeHTMLForJS(img.metadata.prompt)}')"
                onmousemove="updateTooltipPosition(event)"
                onmouseleave="hideTooltip()">
        </div>

    `).join('');

    loadCheckboxState();
    images.forEach(img => updateStars(null, img.filename, img.metadata.rating || 0));
    offset += images.length;
    loading = false;
}

function escapeHTML(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function escapeHTMLForJS(str) {
    return str.replace(/'/g, "\\'");
}

function unescapeHTML(str) {
    return str
        .replace(/&amp;/g, "&")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'");
}


function showTooltip(event, text) {
    clearTimeout(tooltipTimeout);
    tooltip.innerHTML = `<div class="tooltip-text">${escapeHTML(text)}</div><div class="tooltip-hint">CTRL+C</div>`;
    tooltip.style.display = "block";
    tooltip.classList.add("visible");
    updateTooltipPosition(event);
}

function updateTooltipPosition(event) {
    const tooltipWidth = tooltip.offsetWidth;
    const tooltipHeight = tooltip.offsetHeight;

    let x = event.clientX + 15;
    let y = event.clientY + 15;

    // Проверка, чтобы тултип не выходил за правую границу экрана
    if (x + tooltipWidth > window.innerWidth) {
        x = window.innerWidth - tooltipWidth - 10;
    }

    // Проверка, чтобы тултип не выходил за нижнюю границу экрана
    if (y + tooltipHeight > window.innerHeight) {
        y = window.innerHeight - tooltipHeight - 10;
    }

    // Установка новых координат тултипа
    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y + window.scrollY}px`; // Добавляем прокрутку страницы
}

function hideTooltip(event) {
    if (!event.relatedTarget || !event.relatedTarget.closest("#gallery")) {
        clearTimeout(tooltipTimeout);
        tooltipTimeout = setTimeout(() => {
            tooltip.classList.remove("visible");
            setTimeout(() => tooltip.style.display = "none", 100);
        }, 200);
    }
}

function copyTooltipText() {
    const tooltipText = tooltip.querySelector(".tooltip-text");
    const tooltipHint = tooltip.querySelector(".tooltip-hint");
    const originalText = tooltipText.textContent.trim();
    const originalHint = tooltipHint.textContent.trim();

    // Пытаемся скопировать в буфер обмена
    if (originalText) {
        navigator.clipboard.writeText(originalText).then(() => {
            tooltipText.textContent = "Copied!";
            tooltipHint.textContent = "";
            setTimeout(() => {
                tooltipText.textContent = originalText;
                tooltipHint.textContent = originalHint;
            }, 700);
        }).catch(err => {
            console.error("Failed to copy:", err);
        });
    }
}

function copyToClipboard(event, text) {
    event.stopPropagation();
    navigator.clipboard.writeText(text);
}

function openFullscreen(index) {
    currentIndex = index;
    updateFullscreenView();
    document.getElementById('fullscreen-container').style.display = 'flex';
}

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
        const scrollPosition = window.scrollY;
        event.target.closest(".image-container").remove();
        window.scrollTo(0, scrollPosition);
    } else {
        alert("Ошибка: " + (result.error || "не удалось удалить"));
    }
}

function updateFullscreenView() {
    const fullscreenImg = document.getElementById('fullscreen-img');
    const fullscreenPrompt = document.getElementById('fullscreen-prompt');

    if (!currentImages[currentIndex]) return;

    fullscreenImg.src = `/serve_image/${currentImages[currentIndex].filename}`;
    fullscreenPrompt.setAttribute("data-prompt", currentImages[currentIndex].metadata.prompt);
}

function closeFullscreen() {
    document.getElementById('fullscreen-container').style.display = 'none';
}

function prevImage() {
    if (currentIndex > 0) {
        currentIndex--;
        updateFullscreenView();
    }
}

async function nextImage() {
    if (currentIndex < currentImages.length - 1) {
        currentIndex++;
        updateFullscreenView();
    } else {
        await loadMoreImages();

        // Переключаемся на новое изображение только если оно загрузилось
        if (currentIndex < currentImages.length - 1) {
            currentIndex++;
            updateFullscreenView();
        }
    }
}

function copyPromptFullscreen() {
    const promptText = document.getElementById('fullscreen-prompt').dataset.prompt;
    if (promptText) {
        navigator.clipboard.writeText(promptText);
    }
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function saveCheckboxState(event) {
    const checkbox = event.target;
    const filename = checkbox.dataset.filename;
    const checked = checkbox.checked;

    fetch("/update_metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, checked })
    }).catch((error) => console.error("Ошибка обновления метаданных:", error));
}

function updateImageOpacity() {
    document.querySelectorAll(".image-checkbox").forEach((checkbox) => {
        const container = checkbox.closest(".image-container");
        if (checkbox.checked) {
            container.classList.add("checked");
        } else {
            container.classList.remove("checked");
        }
    });
}

function loadCheckboxState() {
    document.querySelectorAll(".image-checkbox").forEach((checkbox) => {
        const filename = checkbox.dataset.filename;
        const imageData = currentImages.find(img => img.filename === filename);

        if (imageData && imageData.metadata.checked !== undefined) {
            checkbox.checked = imageData.metadata.checked;
        }
    });

    updateImageOpacity();
}

function changeSort() {
    sortBy = document.getElementById("sort-select").value;
    setCookie("sort_by", sortBy, 365);
    loadImages();
}

function loadSortFromCookies() {
    const savedSort = getCookie("sort_by");
    if (savedSort) {
        sortBy = savedSort;
        document.getElementById("sort-select").value = sortBy;
    }
}

function setRating(event, filename, rating) {
    event.stopPropagation();

    // Обновляем рейтинг в currentImages
    const image = currentImages.find(img => img.filename === filename);
    if (image) image.metadata.rating = rating;

    updateStars(null, filename, rating);

    fetch("/update_metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, rating })
    }).catch((error) => console.error("Ошибка обновления рейтинга:", error));
}

function updateStars(event, filename, rating) {
    if (event) event.stopPropagation(); // Останавливаем всплытие, если передан event

    const stars = document.querySelectorAll(`.star[data-filename='${filename}']`);
    stars.forEach(star => {
        star.textContent = star.dataset.rating <= rating ? "★" : "☆";
    });
}

function showStars(event) {
    event.stopPropagation();
    const container = event.currentTarget.querySelector(".image-rating");
    if (container) container.style.opacity = "1";
}

function hideStars(event) {
    event.stopPropagation();
    const container = event.currentTarget.querySelector(".image-rating");
    if (container) container.style.opacity = "0";
}

function toggleFolder(event) {
    event.stopPropagation(); // Не даём всплыть на родителя
    const row = event.currentTarget.closest(".folder-row");
    const item = row.closest(".folder-item");
    const children = item.querySelector(".folder-children");

    const isExpanded = item.classList.toggle("expanded");
    if (isExpanded) {
        children.classList.remove("hidden");
    } else {
        children.classList.add("hidden");
    }
}

function updateToggleButtonPosition() {
    const sidebar = document.getElementById("sidebar");
    const toggleBtn = document.getElementById("menu-toggle");
    const icon = document.getElementById("menu-icon");

    if (sidebar.classList.contains("hidden")) {
        toggleBtn.style.left = "10px";
        icon.textContent = "⯈"; // Свернуто
    } else {
        const sidebarWidth = sidebar.offsetWidth;
        toggleBtn.style.left = `${sidebarWidth + 10}px`;
        icon.textContent = "⯇"; // Развернуто
    }
}

window.onpopstate = function () {
    loadContent();
    loadCheckboxState();
    document.getElementById("scroll-to-top").classList.add("hidden");
};

window.onload = function () {
    loadSortFromCookies();
    loadSearchFromCookies();
    loadContent();
    loadCheckboxState();
    document.getElementById("scroll-to-top").classList.add("hidden");
    document.getElementById("menu-toggle").addEventListener("click", () => {
        const sidebar = document.getElementById("sidebar");
        const container = document.querySelector(".container");

        sidebar.classList.toggle("hidden");
        container.classList.toggle("sidebar-visible");
        updateToggleButtonPosition();
    });

    document.querySelectorAll(".folder-row").forEach(row => {
        const hasChildren = row.dataset.hasChildren === "true";
        if (!hasChildren) return;

        row.addEventListener("click", () => {
            const parent = row.closest(".folder-item");
            const children = parent.querySelector(".folder-children");

            const isExpanded = parent.classList.toggle("expanded");
            if (isExpanded) {
                children.classList.remove("hidden");
            } else {
                children.classList.add("hidden");
            }
        });
    });


    window.addEventListener("scroll", () => {
        // 1. Ленивое подгружение изображений при прокрутке вниз
        if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
            loadMoreImages();
        }

        // 2. Показываем/скрываем кнопку "Вверх" при скролле
        const scrollTopButton = document.getElementById("scroll-to-top");
        if (window.scrollY > 300) {
            scrollTopButton.classList.remove("hidden");
        } else {
            scrollTopButton.classList.add("hidden");
        }

        // 3. Корректируем положение тултипа, если он выходит за границы экрана
        if (tooltip.style.display === "block") {
            const tooltipRect = tooltip.getBoundingClientRect();
            if (tooltipRect.bottom > window.innerHeight) {
                tooltip.style.top = `${window.innerHeight - tooltipRect.height - 10}px`;
            }
        }
    });

    document.getElementById("gallery").addEventListener("mouseleave", hideTooltip);
    document.getElementById("gallery").addEventListener("mousemove", (event) => {
        if (tooltip.style.display === "block") {
            updateTooltipPosition(event);
        }
    });

    document.addEventListener("change", (event) => {
        if (event.target.classList.contains("image-checkbox")) {
            saveCheckboxState(event);
            updateImageOpacity();
        }
    });

    document.addEventListener("keydown", (event) => {
        const fullscreenVisible = document.getElementById('fullscreen-container').style.display === "flex";

        if (fullscreenVisible) {
            if (event.key === "ArrowLeft") {
                prevImage();
            } else if (event.key === "ArrowRight") {
                nextImage();
            } else if (event.key === "Escape") {
                closeFullscreen();
            }
        }

        if (event.ctrlKey && (event.key.toLowerCase() === "c" || event.key.toLowerCase() === "с")) {
            if (fullscreenVisible) {
                copyPromptFullscreen();
            } else {
                console.log("CTRL+C pressed");
                copyTooltipText();
            }
        }
    });

    document.getElementById("fullscreen-container").addEventListener("click", (event) => {
        if (!event.target.closest(".fullscreen-image-wrapper") &&
            !event.target.closest(".copy-btn") &&
            !event.target.closest(".close-btn") &&
            !event.target.closest(".nav-arrow")) {
            closeFullscreen();
        }
    });
};

updateToggleButtonPosition();