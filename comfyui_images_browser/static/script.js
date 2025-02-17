let offset = 0;
const LIMIT = 50;
let loading = false;
let currentImages = [];
let currentIndex = 0;

async function updateUrl(event, path) {
    event.preventDefault(); // Отменяем стандартный переход

    if (window.location.pathname === "/" + path) return; // Если уже в этой папке, ничего не делаем

    lastImageCount = 0; // Сбрасываем счетчик изображений
    window.history.pushState({}, '', '/' + path); // Обновляем URL без перезагрузки
    await loadContent(); // Динамически загружаем новую папку
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

let searchQuery = "";

function filterImages() {
    searchQuery = document.getElementById("search-box").value.trim();
    loadImages(); // Перезагружаем галерею с новым фильтром
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

async function loadMoreImages() {
    if (loading) return;
    loading = true;

    const response = await fetch(`/images${window.location.pathname}?limit=${LIMIT}&offset=${offset}&search=${encodeURIComponent(searchQuery)}`);
    const images = await response.json();

    if (images.length === 0 && offset === 0) {
        loading = false;
        document.getElementById('gallery').innerHTML = "<p>Нет изображений.</p>";
        return;
    }

    currentImages.push(...images);

    document.getElementById('gallery').innerHTML += images.map((img, index) => `
        <div class="image-container" onclick="openFullscreen(${offset + index})">
            <button class="delete-btn" onclick="deleteThumbnail(event, '${img.filename}')">❌</button>
            <button class="copy-btn" onclick="copyToClipboard(event, '${img.prompt}')">📋</button>
            <img src="/serve_thumbnail/${img.thumbnail}" alt="Image" loading="lazy">
        </div>
    `).join('');

    offset += LIMIT;
    loading = false;
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

    fullscreenImg.src = `/serve_image/${currentImages[currentIndex].filename}?t=${Date.now()}`;
    fullscreenPrompt.setAttribute("data-prompt", currentImages[currentIndex].prompt);
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

// Обработчик клавиш
document.addEventListener("keydown", (event) => {
    if (document.getElementById('fullscreen-container').style.display === "flex") {
        if (event.key === "ArrowLeft") {
            prevImage();
        } else if (event.key === "ArrowRight") {
            nextImage();
        } else if (event.ctrlKey && event.key === "c") {
            copyPromptFullscreen();
        } else if (event.key === "Escape") {
            closeFullscreen();
        }
    }
});

window.onpopstate = function () {
    loadContent();
};

window.onload = function () {
    loadContent();
};

window.addEventListener("scroll", () => {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
        loadMoreImages();
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


let lastImageCount = 0;
let isLoading = false;

async function checkForUpdates() {
    if (isLoading) return; // Если уже идет загрузка, не загружаем снова

    const folder = window.location.pathname.replace("/", "");
    if (!folder) return;

    const response = await fetch(`/check_updates/${folder}`);
    const data = await response.json();

    if (data.count !== lastImageCount) {
        console.log(`Обнаружены изменения в папке "${folder}", обновляем...`);
        lastImageCount = data.count;

        isLoading = true;
        const scrollPosition = window.scrollY;
        await loadContent();
        window.scrollTo(0, scrollPosition);
        isLoading = false;
    }
}

setInterval(checkForUpdates, 5000);

window.addEventListener("scroll", () => {
    const scrollButton = document.getElementById("scroll-to-top");

    if (window.scrollY > 300) {
        scrollButton.classList.remove("hidden");
    } else {
        scrollButton.classList.add("hidden");
    }
});

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: "smooth" });
}
