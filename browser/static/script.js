// ============================================================================
// CONSTANTS
// ============================================================================

const LIMIT = 50;
const TOOLTIP_OFFSET = 15;
const TOOLTIP_HIDE_DELAY = 200;
const TOOLTIP_FADE_DELAY = 100;
const SCROLL_THRESHOLD = 800; // Порог для начала подгрузки изображений (в пикселях от конца страницы)
const SCROLL_TO_TOP_THRESHOLD = 300;
const STARRED_SYMBOL = "★";
const UNSTARRED_SYMBOL = "☆";
const MAX_RATING = 5;
const COPY_CONFIRMATION_DELAY = 700;
const AUTO_REFRESH_INTERVAL = 1000; // 1 секунда

// ============================================================================
// DOM ELEMENTS
// ============================================================================

const DOM = {
    tooltip: document.getElementById("tooltip"),
    gallery: document.getElementById("gallery"),
    sidebar: document.getElementById("sidebar"),
    loading: document.getElementById("loading"),
    searchBox: document.getElementById("search-box"),
    sortSelect: document.getElementById("sort-select"),
    scrollToTop: document.getElementById("scroll-to-top"),
    menuToggle: document.getElementById("menu-toggle"),
    menuIcon: document.getElementById("menu-icon"),
    fullscreenContainer: document.getElementById("fullscreen-container"),
    fullscreenImg: document.getElementById("fullscreen-img"),
    fullscreenPrompt: document.getElementById("fullscreen-prompt"),
    fullscreenCheckbox: document.getElementById("fullscreen-checkbox"),
    fullscreenTagsDisplay: document.getElementById("fullscreen-tags-display"),
    fullscreenRating: document.getElementById("fullscreen-rating")
};

// ============================================================================
// STATE
// ============================================================================

const state = {
    offset: 0,
    loading: false,
    currentImages: [],
    currentIndex: 0,
    searchQuery: "",
    sortBy: "date-asc",
    allTags: [],
    suggestionIndex: -1,
    tooltipTimeout: null,
    autoRefreshInterval: null,
    lastUpdateTime: Date.now()
};

// ============================================================================
// UTILITIES
// ============================================================================

const utils = {
    escapeHTML(str) {
        if (!str) return "";
        const map = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        };
        return str.replace(/[&<>"']/g, m => map[m]);
    },

    escapeJS(str) {
        if (!str) return "";
        return str.replace(/'/g, "\\'");
    },

    extractSeed(filename) {
        if (!filename) return "";
        return filename.replace(/^.*[\\/]/, "").replace(/\.[^/.]+$/, "");
    },

    sanitizeTagsJSON(tags) {
        return JSON.stringify(tags || [])
            .replace(/\\/g, "\\\\")
            .replace(/'/g, "\\'")
            .replace(/</g, "\\u003c")
            .replace(/>/g, "\\u003e");
    },

    async apiRequest(endpoint, options = {}) {
        const defaultOptions = {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            ...options
        };
        try {
            console.log(`API request: ${endpoint}`, defaultOptions);
            const response = await fetch(endpoint, defaultOptions);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `HTTP ${response.status}: ${response.statusText}` }));
                console.error(`API request failed: ${endpoint}`, response.status, errorData);
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API request failed: ${endpoint}`, error);
            throw error;
        }
    }
};

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

const stateManager = {
    save() {
        const state = {
            currentPath: window.location.pathname,
            scrollY: window.scrollY,
            searchQuery: DOM.searchBox.value.trim(),
            sortBy: DOM.sortSelect.value,
            sidebarVisible: document.body.classList.contains("sidebar-visible")
        };
        localStorage.setItem("galleryState", JSON.stringify(state));
    },

    restore() {
        const raw = localStorage.getItem("galleryState");
        if (!raw) return;

        try {
            const saved = JSON.parse(raw);

            if (saved.searchQuery !== undefined) {
                state.searchQuery = saved.searchQuery;
                DOM.searchBox.value = saved.searchQuery;
            }

            if (saved.sortBy) {
                state.sortBy = saved.sortBy;
                DOM.sortSelect.value = saved.sortBy;
            } else {
                // Если нет сохраненной сортировки, синхронизируем из DOM
                state.sortBy = DOM.sortSelect.value;
            }

            if (typeof saved.sidebarVisible === "boolean") {
                DOM.sidebar.classList.toggle("hidden", !saved.sidebarVisible);
                document.body.classList.toggle("sidebar-visible", saved.sidebarVisible);
            }

            setTimeout(() => {
                window.scrollTo(0, saved.scrollY || 0);
            }, 0);
        } catch (e) {
            console.warn("Не удалось восстановить галерею:", e);
        }
    }
};

// ============================================================================
// NAVIGATION & FOLDERS
// ============================================================================

const navigation = {
    async updateUrl(event, path) {
        event.preventDefault();
        if (window.location.pathname === `/${path}`) return;

        // Сбрасываем состояние загрузки перед переключением
        state.loading = false;
        // Останавливаем автообновление при смене страницы
        gallery.stopAutoRefresh();
        stateManager.save();
        window.history.pushState({}, '', `/${path}`);
        await contentLoader.load();
        folders.updateActiveHighlight();
    },

    async loadContent() {
        DOM.loading.style.display = "block";
        try {
            const path = window.location.pathname;
            stateManager.restore();
            await (path === "/" ? folders.load() : gallery.load());
        } catch (error) {
            console.error("Failed to load content:", error);
        } finally {
            DOM.loading.style.display = "none";
        }
        tags.fetchAll();
    }
};

const folders = {
    async load() {
        const folderList = DOM.sidebar.querySelector(".sidebar-folders");
        if (!folderList) return;

        try {
            const response = await fetch("/");
            const doc = new DOMParser().parseFromString(await response.text(), "text/html");
            const incomingFolders = doc.querySelector(".sidebar-folders");

            if (incomingFolders) {
                folderList.innerHTML = incomingFolders.innerHTML;
                // Переустанавливаем обработчики событий после обновления HTML
                folders.rebindEventHandlers();
                folders.updateActiveHighlight();
            } else {
                console.error("❌ sidebar-folders not found in response");
            }
        } catch (error) {
            console.error("Failed to load folders:", error);
        }
    },

    rebindEventHandlers() {
        // Переустанавливаем обработчики событий для папок после обновления HTML
        document.querySelectorAll(".folder-row").forEach(row => {
            if (row.dataset.hasChildren === "true") {
                row.addEventListener("click", folders.toggle);
            }
        });
    },

    updateActiveHighlight() {
        const currentPath = window.location.pathname;
        document.querySelectorAll(".folder-tree a.active-folder")
            .forEach(el => el.classList.remove("active-folder"));

        const activeLink = document.querySelector(`.folder-tree a[href="${currentPath}"]`);
        if (activeLink) {
            activeLink.classList.add("active-folder");
            activeLink.scrollIntoView({ block: "center", behavior: "smooth" });
        }
    },

    toggle(event) {
        event.stopPropagation();
        const item = event.currentTarget.closest(".folder-item");
        const children = item.querySelector(".folder-children");
        if (!children) return;

        const expanded = item.classList.toggle("expanded");
        children.classList.toggle("hidden", !expanded);
    }
};

// ============================================================================
// GALLERY
// ============================================================================

const gallery = {
    async load() {
        // Сбрасываем состояние загрузки перед началом
        state.loading = false;
        // Синхронизируем сортировку из DOM в state перед загрузкой (только если изменилась)
        const currentSortBy = DOM.sortSelect.value;
        if (currentSortBy !== state.sortBy) {
            state.sortBy = currentSortBy;
        }
        await folders.load();
        state.offset = 0;
        state.currentImages = [];
        DOM.gallery.innerHTML = "";
        // Скрываем индикатор после очистки галереи
        if (DOM.loading.style.display === "block") {
            DOM.loading.style.display = "none";
        }
        // Загружаем изображения
        await gallery.loadMore();
        // Запускаем автообновление только для сортировки по убыванию даты
        const [sort, order] = state.sortBy.split("-");
        if (sort === "date" && order === "desc") {
            gallery.startAutoRefresh();
        } else {
            gallery.stopAutoRefresh();
        }
    },

    async loadMore(limit = LIMIT) {
        if (state.loading) return;
        state.loading = true;

        try {
            const [sort, order] = state.sortBy.split("-");
            const query = `/images${window.location.pathname}?limit=${limit}&offset=${state.offset}&search=${encodeURIComponent(state.searchQuery)}&sort_by=${sort}&order=${order}`;
            const images = await (await fetch(query)).json();

            if (!images.length) {
                state.loading = false;
                return;
            }

            // Убеждаемся, что у всех изображений есть метаданные с рейтингом
            images.forEach(img => {
                if (!img.metadata) {
                    img.metadata = {};
                }
                if (img.metadata.rating === undefined || img.metadata.rating === null) {
                    img.metadata.rating = 0;
                }
            });

            state.currentImages.push(...images);
            const cardsHTML = gallery.renderCards(images);
            DOM.gallery.insertAdjacentHTML("beforeend", cardsHTML);

            // Сразу обновляем состояние чекбоксов и рейтингов, чтобы контент был виден
            gallery.loadCheckboxState();
            images.forEach(img => rating.updateStars(null, img.filename, img.metadata.rating || 0));
            state.offset += images.length;

            // Предзагрузка изображений асинхронно, не блокируя отображение
            // Используем requestIdleCallback для неблокирующей предзагрузки
            const containers = DOM.gallery.querySelectorAll(".image-container:not(.image-loaded)");
            if (containers.length > 0) {
                const preloadImages = () => {
                    Array.from(containers).forEach(container => {
                        const img = container.querySelector("img");
                        if (!img) return;

                        if (img.complete) {
                            container.classList.add("image-loaded");
                        } else {
                            img.onload = () => {
                                container.classList.add("image-loaded");
                            };
                            img.onerror = () => {
                                // Помечаем как загруженное даже при ошибке, чтобы не ждать бесконечно
                                container.classList.add("image-loaded");
                            };
                        }
                    });
                };

                // Используем requestIdleCallback если доступен, иначе setTimeout
                if (window.requestIdleCallback) {
                    requestIdleCallback(preloadImages, { timeout: 1000 });
                } else {
                    setTimeout(preloadImages, 0);
                }
            }
        } catch (error) {
            console.error("Failed to load images:", error);
        } finally {
            state.loading = false;
        }
    },

    renderCards(images) {
        return images.map((img, index) => {
            // Убеждаемся, что метаданные существуют
            if (!img.metadata) {
                img.metadata = {};
            }
            const prompt = utils.escapeJS(img.metadata.prompt || "");
            const seed = utils.escapeJS(utils.extractSeed(img.filename));
            const filenameEscaped = utils.escapeJS(img.filename || "");
            const filenameAttrEscaped = img.filename ? img.filename.replace(/"/g, "&quot;").replace(/'/g, "&#39;") : "";
            const tagsJson = utils.sanitizeTagsJSON(img.metadata.tags || []);
            const ratingValue = img.metadata.rating || 0;

            // Извлекаем разрешение из тегов для установки aspect-ratio
            const tags = img.metadata.tags || [];
            const resolutionTag = tags.find(tag => /^\d+x\d+$/.test(tag));
            let aspectRatioStyle = "";
            if (resolutionTag) {
                const [width, height] = resolutionTag.split("x").map(Number);
                if (width && height) {
                    const aspectRatio = width / height;
                    aspectRatioStyle = `style="aspect-ratio: ${aspectRatio};"`;
                }
            }

            return `
                <div class="image-container" onclick="fullscreen.open(${state.offset + index})"
                     onmouseenter="rating.showStars(event)" onmouseleave="rating.hideStars(event)" ${aspectRatioStyle}>
                    <div class="image-buttons">
                        <button class="copy-btn" onclick="clipboard.copy(event, '${prompt}')" title="Копировать промпт">⧉</button>
                        <button class="copy-favorites-btn" onclick="favorites.copy(event, '${filenameEscaped}')" title="В избранное">★</button>
                        <input type="checkbox" class="image-checkbox" data-filename="${filenameAttrEscaped}"
                               onclick="event.stopPropagation(); gallery.saveCheckboxState(event);" title="Выбрать">
                        <button class="delete-btn" onclick="gallery.deleteThumbnail(event, '${filenameEscaped}')" title="Удалить">✕</button>
                    </div>
                    <div class="image-rating" style="opacity: 0;">
                        ${Array.from({ length: MAX_RATING }, (_, i) => i + 1).map(star => `
                            <span class="star" data-filename="${filenameAttrEscaped}" data-rating="${star}"
                                  onclick="rating.set(event, '${filenameEscaped}', ${star})">
                                ${ratingValue >= star ? STARRED_SYMBOL : UNSTARRED_SYMBOL}
                            </span>`).join("")}
                    </div>
                    <img src="/serve_thumbnail/${img.thumbnail}" alt="Image" loading="lazy"
                         onload="this.parentElement.classList.add('image-loaded')"
                         onmouseenter="tooltip.show(event, '${prompt}', '${seed}', ${tagsJson})"
                         onmousemove="tooltip.updatePosition(event)"
                         onmouseleave="tooltip.hide()">
                </div>`;
        }).join("");
    },

    filter() {
        state.searchQuery = DOM.searchBox.value.trim();
        // Синхронизируем сортировку перед фильтрацией
        state.sortBy = DOM.sortSelect.value;
        gallery.load();
    },

    async deleteThumbnail(event, filename) {
        event.stopPropagation();
        if (!confirm("Удалить изображение?")) return;

        try {
            const result = await utils.apiRequest("/delete_image", {
                body: JSON.stringify({ filename })
            });

            if (result.success) {
                event.target.closest(".image-container")?.remove();
            } else {
                alert("Ошибка удаления: " + (result.error || "неизвестная"));
            }
        } catch (error) {
            alert("Ошибка удаления: " + error);
        }
    },

    saveCheckboxState(event) {
        const cb = event.target;
        utils.apiRequest("/update_metadata", {
            body: JSON.stringify({ filename: cb.dataset.filename, checked: cb.checked })
        }).catch(console.error);
    },

    loadCheckboxState() {
        document.querySelectorAll(".image-checkbox").forEach(cb => {
            const img = state.currentImages.find(i => i.filename === cb.dataset.filename);
            if (img) cb.checked = !!img.metadata.checked;
        });
        gallery.updateImageOpacity();
    },

    updateImageOpacity() {
        document.querySelectorAll(".image-checkbox").forEach(cb => {
            const container = cb.closest(".image-container");
            if (container) {
                container.classList.toggle("checked", cb.checked);
            }
        });
    },

    async uncheckAll() {
        const currentPath = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
        const searchQuery = state.searchQuery || "";

        console.log("Uncheck all - path:", currentPath, "search:", searchQuery);

        try {
            const result = await utils.apiRequest("/uncheck_all", {
                body: JSON.stringify({ path: currentPath, search: searchQuery })
            });

            if (result.success) {
                console.log(`✅ Сброшено чекбоксов: ${result.count}`);

                // Обновляем визуальное отображение всех видимых чекбоксов
                document.querySelectorAll(".image-checkbox").forEach(cb => {
                    cb.checked = false;
                    const container = cb.closest(".image-container");
                    if (container) container.classList.remove("checked");
                });

                // Обновляем состояние в currentImages
                state.currentImages.forEach(img => {
                    if (img.metadata) {
                        img.metadata.checked = false;
                    }
                });
            }
        } catch (error) {
            console.error("❌ Ошибка сброса чекбоксов:", error);
            const errorMessage = error.message || error.toString();
            alert("Ошибка сброса чекбоксов: " + errorMessage);
        }
    },

    rebindIndices() {
        document.querySelectorAll("#gallery .image-container").forEach((container, i) => {
            container.setAttribute("onclick", `fullscreen.open(${i})`);
        });
    },

    async checkForUpdates() {
        // Не обновляем, если идет загрузка, открыт полноэкранный режим или пользователь не на главной странице
        if (state.loading || DOM.fullscreenContainer.style.display === "flex") {
            return;
        }

        try {
            // Синхронизируем сортировку из DOM в state перед проверкой (только если изменилась)
            const currentSortBy = DOM.sortSelect.value;
            if (currentSortBy !== state.sortBy) {
                state.sortBy = currentSortBy;
            }
            const [sort, order] = state.sortBy.split("-");

            // Автообновление работает только для сортировки по убыванию даты
            if (sort !== "date" || order !== "desc") {
                return;
            }

            // Запрашиваем только первые изображения для поиска новых (не все!)
            const query = `/images${window.location.pathname}?limit=${LIMIT}&offset=0&search=${encodeURIComponent(state.searchQuery)}&sort_by=${sort}&order=${order}`;
            const serverImages = await (await fetch(query)).json();

            // Нормализуем метаданные
            serverImages.forEach(img => {
                if (!img.metadata) {
                    img.metadata = {};
                }
                if (img.metadata.rating === undefined || img.metadata.rating === null) {
                    img.metadata.rating = 0;
                }
            });

            // Создаем Map для быстрого поиска
            const serverImageMap = new Map(serverImages.map(img => [img.filename, img]));
            const currentImageMap = new Map(state.currentImages.map(img => [img.filename, img]));

            // Находим новые изображения
            const newImages = serverImages.filter(img => !currentImageMap.has(img.filename));

            // Находим удаленные изображения
            const removedFilenames = state.currentImages
                .filter(img => !serverImageMap.has(img.filename))
                .map(img => img.filename);

            // Удаляем старые изображения из DOM
            removedFilenames.forEach(filename => {
                const container = document.querySelector(`.image-container [data-filename="${filename.replace(/"/g, "&quot;").replace(/'/g, "&#39;")}"]`)?.closest(".image-container");
                if (container) {
                    container.remove();
                }
            });

            // Удаляем из state
            state.currentImages = state.currentImages.filter(img => !removedFilenames.includes(img.filename));

            // Добавляем новые изображения в начало (для сортировки по убыванию даты новые изображения самые свежие)
            if (newImages.length > 0) {
                // Вставляем новые изображения в начало списка
                const cardsHTML = gallery.renderCards(newImages);
                DOM.gallery.insertAdjacentHTML("afterbegin", cardsHTML);

                // Обновляем state - добавляем в начало
                state.currentImages.unshift(...newImages);

                // Обновляем чекбоксы и рейтинги
                gallery.loadCheckboxState();
                newImages.forEach(img => rating.updateStars(null, img.filename, img.metadata.rating || 0));
                gallery.rebindIndices();
            }

            state.lastUpdateTime = Date.now();
        } catch (error) {
            console.error("Failed to check for updates:", error);
        }
    },

    startAutoRefresh() {
        // Останавливаем предыдущий интервал, если есть
        if (state.autoRefreshInterval) {
            clearInterval(state.autoRefreshInterval);
        }

        // Запускаем автообновление
        state.autoRefreshInterval = setInterval(() => {
            gallery.checkForUpdates();
        }, AUTO_REFRESH_INTERVAL);
    },

    stopAutoRefresh() {
        if (state.autoRefreshInterval) {
            clearInterval(state.autoRefreshInterval);
            state.autoRefreshInterval = null;
        }
    }
};

// ============================================================================
// TOOLTIP
// ============================================================================

const tooltip = {
    show(event, text, seed, tags = []) {
        clearTimeout(state.tooltipTimeout);

        const tagsHTML = tags.length
            ? `<div class="tooltip-tags">${tags.map(tag =>
                `<span class="tag-pill tooltip-pill">${utils.escapeHTML(tag)}</span>`).join("")}</div>`
            : "";

        DOM.tooltip.innerHTML = `
            <div class="tooltip-seed">${utils.escapeHTML(seed)}</div>
            <div class="tooltip-text">${utils.escapeHTML(text)}</div>
            ${tagsHTML}
            <div class="tooltip-hint">CTRL+C</div>`;

        DOM.tooltip.style.display = "block";
        DOM.tooltip.classList.add("visible");
        tooltip.updatePosition(event);
    },

    updatePosition(event) {
        const { clientX: x0, clientY: y0 } = event;
        const { offsetWidth: w, offsetHeight: h } = DOM.tooltip;

        let x = x0 + TOOLTIP_OFFSET;
        let y = y0 + TOOLTIP_OFFSET;

        if (x + w > window.innerWidth) x = window.innerWidth - w - 10;
        if (y + h > window.innerHeight) y = window.innerHeight - h - 10;

        DOM.tooltip.style.left = `${x}px`;
        DOM.tooltip.style.top = `${y + window.scrollY}px`;
    },

    hide(event) {
        if (event?.relatedTarget && event.relatedTarget.closest("#gallery")) return;

        clearTimeout(state.tooltipTimeout);
        state.tooltipTimeout = setTimeout(() => {
            DOM.tooltip.classList.remove("visible");
            setTimeout(() => {
                DOM.tooltip.style.display = "none";
            }, TOOLTIP_FADE_DELAY);
        }, TOOLTIP_HIDE_DELAY);
    },

    async copyText() {
        const textEl = DOM.tooltip.querySelector(".tooltip-text");
        const seedEl = DOM.tooltip.querySelector(".tooltip-seed");

        const prompt = textEl?.textContent?.trim();
        const seed = seedEl?.textContent?.trim();

        if (!prompt || !seed) return;

        try {
            await navigator.clipboard.writeText(prompt);
            textEl.textContent = "Copied!";
            DOM.tooltip.querySelector(".tooltip-hint").textContent = "";

            setTimeout(() => {
                DOM.tooltip.innerHTML = `
                    <div class="tooltip-seed">${utils.escapeHTML(seed)}</div>
                    <div class="tooltip-text">${utils.escapeHTML(prompt)}</div>
                    <div class="tooltip-hint">CTRL+C</div>`;
            }, COPY_CONFIRMATION_DELAY);
        } catch (error) {
            console.error("Failed to copy text:", error);
        }
    }
};

// ============================================================================
// FULLSCREEN VIEWER
// ============================================================================

const fullscreen = {
    open(index) {
        state.currentIndex = index;
        fullscreen.updateView();
        DOM.fullscreenContainer.style.display = "flex";
        // Останавливаем автообновление при открытии полноэкранного режима
        gallery.stopAutoRefresh();
    },

    close() {
        DOM.fullscreenContainer.style.display = "none";
        // Возобновляем автообновление при закрытии полноэкранного режима
        gallery.startAutoRefresh();
    },

    updateView() {
        const data = state.currentImages[state.currentIndex];
        if (!data) return;

        DOM.fullscreenImg.src = `/serve_image/${data.filename}`;

        DOM.fullscreenPrompt.dataset.prompt = data.metadata.prompt;
        DOM.fullscreenPrompt.textContent = data.metadata.prompt || "";

        const miniCheckbox = document.querySelector(`.image-checkbox[data-filename="${data.filename}"]`);
        const isChecked = miniCheckbox ? miniCheckbox.checked : !!data.metadata.checked;

        DOM.fullscreenCheckbox.dataset.filename = data.filename;
        DOM.fullscreenCheckbox.checked = isChecked;

        const wrapper = document.querySelector(".fullscreen-image-wrapper");
        wrapper?.classList.toggle("checked", isChecked);

        DOM.fullscreenTagsDisplay.innerHTML = "";
        tags.renderPills(data.metadata.tags || []);

        fullscreen.setupCheckboxHandler(data, miniCheckbox, wrapper);
        fullscreen.setupRatingHandler(data);
    },

    setupCheckboxHandler(data, miniCheckbox, wrapper) {
        DOM.fullscreenCheckbox.onchange = function () {
            const checked = DOM.fullscreenCheckbox.checked;
            data.metadata.checked = checked;
            wrapper?.classList.toggle("checked", checked);

            if (miniCheckbox) {
                miniCheckbox.checked = checked;
                const container = miniCheckbox.closest(".image-container");
                if (container) {
                    container.classList.toggle("checked", checked);
                }
            }

            utils.apiRequest("/update_metadata", {
                body: JSON.stringify({ filename: data.filename, checked })
            }).catch(console.error);
        };
    },

    setupRatingHandler(data) {
        if (!DOM.fullscreenRating) return;

        const stars = DOM.fullscreenRating.querySelectorAll(".star");
        const currentRating = data.metadata.rating || 0;

        stars.forEach(star => {
            const starRating = parseInt(star.dataset.rating);
            star.textContent = starRating <= currentRating ? STARRED_SYMBOL : UNSTARRED_SYMBOL;
            star.classList.toggle("selected", starRating <= currentRating);

            star.onclick = function (e) {
                e.stopPropagation();

                const currentRating = data.metadata.rating || 0;
                // Если кликнули на уже выбранную звездочку - сбрасываем рейтинг
                const newRating = currentRating === starRating ? 0 : starRating;

                // Обновляем метаданные в состоянии
                data.metadata.rating = newRating;

                // Обновляем метаданные в массиве currentImages
                const img = state.currentImages.find(i => i.filename === data.filename);
                if (img) {
                    img.metadata.rating = newRating;
                }

                // Обновляем визуальное отображение в fullscreen
                stars.forEach(s => {
                    const r = parseInt(s.dataset.rating);
                    s.textContent = r <= newRating ? STARRED_SYMBOL : UNSTARRED_SYMBOL;
                    s.classList.toggle("selected", r <= newRating);
                });

                // Обновляем визуальное отображение в галерее
                rating.updateStars(null, data.filename, newRating);

                // Сохраняем на сервере
                utils.apiRequest("/update_metadata", {
                    body: JSON.stringify({ filename: data.filename, rating: newRating })
                }).then(() => {
                    console.log("✅ Рейтинг сохранен:", newRating);
                }).catch(error => {
                    console.error("❌ Ошибка сохранения рейтинга:", error);
                });
            };
        });
    },

    prev() {
        if (state.currentIndex > 0) {
            state.currentIndex--;
            fullscreen.updateView();
        }
    },

    async next() {
        if (++state.currentIndex >= state.currentImages.length) {
            await gallery.loadMore();
        }
        if (state.currentIndex < state.currentImages.length) {
            fullscreen.updateView();
        }
    },

    async delete() {
        const data = state.currentImages[state.currentIndex];
        if (!data || !confirm("Удалить изображение?")) return;

        try {
            const result = await utils.apiRequest("/delete_image", {
                body: JSON.stringify({ filename: data.filename })
            });

            if (result.success) {
                const thumb = document.querySelector(`.image-checkbox[data-filename="${data.filename}"]`)?.closest(".image-container");
                thumb?.remove();

                state.currentImages.splice(state.currentIndex, 1);
                gallery.rebindIndices();

                if (state.currentImages.length === 0) {
                    fullscreen.close();
                } else if (state.currentIndex >= state.currentImages.length) {
                    state.currentIndex = state.currentImages.length - 1;
                    fullscreen.updateView();
                } else {
                    fullscreen.updateView();
                }
            } else {
                alert("Ошибка удаления: " + (result.error || "неизвестная"));
            }
        } catch (error) {
            alert("Ошибка удаления: " + error);
        }
    },

    copyPrompt() {
        const prompt = DOM.fullscreenPrompt.dataset.prompt;
        if (prompt) {
            navigator.clipboard.writeText(prompt).catch(console.error);
        }
    }
};

// ============================================================================
// RATING
// ============================================================================

const rating = {
    set(event, filename, ratingValue) {
        event.stopPropagation();
        const img = state.currentImages.find(i => i.filename === filename);
        if (!img) return;

        const currentRating = img.metadata.rating || 0;
        // Если кликнули на уже выбранную звездочку - сбрасываем рейтинг
        const newRating = currentRating === ratingValue ? 0 : ratingValue;

        img.metadata.rating = newRating;

        rating.updateStars(null, filename, newRating);

        utils.apiRequest("/update_metadata", {
            body: JSON.stringify({ filename, rating: newRating })
        }).then(() => {
            console.log("✅ Рейтинг сохранен:", newRating, "для", filename);
        }).catch(error => {
            console.error("❌ Ошибка сохранения рейтинга:", error);
        });
    },

    updateStars(event, filename, ratingValue) {
        if (event) event.stopPropagation();
        document.querySelectorAll(`.star[data-filename='${filename}']`).forEach(star => {
            star.textContent = star.dataset.rating <= ratingValue ? STARRED_SYMBOL : UNSTARRED_SYMBOL;
        });
    },

    showStars(event) {
        event.currentTarget.querySelector(".image-rating").style.opacity = "1";
    },

    hideStars(event) {
        event.currentTarget.querySelector(".image-rating").style.opacity = "0";
    }
};

// ============================================================================
// TAGS
// ============================================================================

const tags = {
    async fetchAll() {
        try {
            const res = await fetch("/all_tags");
            state.allTags = await res.json();
        } catch (err) {
            console.error("Ошибка загрузки тегов:", err);
        }
    },

    renderPills(tags) {
        DOM.fullscreenTagsDisplay.innerHTML = "";

        tags.forEach(tag => {
            const span = document.createElement("span");
            span.className = "tag-pill";
            span.textContent = tag;
            span.onclick = () => {
                DOM.searchBox.value = `t:${tag}`;
                gallery.filter();
                fullscreen.close();
            };
            DOM.fullscreenTagsDisplay.appendChild(span);
        });
    }
};

// ============================================================================
// CLIPBOARD
// ============================================================================

const clipboard = {
    copy(event, text) {
        event.stopPropagation();
        navigator.clipboard.writeText(text).catch(console.error);
    }
};

// ============================================================================
// FAVORITES
// ============================================================================

const favorites = {
    async copy(event, filename) {
        event.stopPropagation();

        try {
            const result = await utils.apiRequest("/copy_to_favorites", {
                body: JSON.stringify({ filename })
            });

            if (result.success) {
                console.log(`✅ Скопировано в "favorites": ${filename}`);
            } else {
                alert("Ошибка копирования: " + (result.error || "неизвестная"));
            }
        } catch (err) {
            alert("Ошибка соединения: " + err);
        }
    },

    copyFromFullscreen() {
        const data = state.currentImages[state.currentIndex];
        if (!data) return;
        favorites.copy({ stopPropagation: () => { } }, data.filename);
    }
};

// ============================================================================
// UI CONTROLS
// ============================================================================

const ui = {
    changeSort() {
        const newSortBy = DOM.sortSelect.value;
        // Останавливаем автообновление перед сменой сортировки
        gallery.stopAutoRefresh();
        state.sortBy = newSortBy;
        // Сохраняем в localStorage
        stateManager.save();
        gallery.load();
    },

    scrollToTop() {
        window.scrollTo({ top: 0, behavior: "smooth" });
    },

    updateToggleButtonPosition() {
        const isVisible = document.body.classList.contains("sidebar-visible");
        DOM.menuToggle.style.left = isVisible ? "220px" : "10px";
        DOM.menuIcon.textContent = isVisible ? "⯇" : "⯈";
    },

    toggleSidebar() {
        document.body.classList.toggle("sidebar-visible");
        ui.updateToggleButtonPosition();
    }
};

// ============================================================================
// KEYBOARD HANDLERS
// ============================================================================

const keyboard = {
    handleKeydown(e) {
        const isFullscreen = DOM.fullscreenContainer.style.display === "flex";

        if (isFullscreen) {
            keyboard.handleFullscreenKeys(e);
        }

        keyboard.handleCopyShortcut(e, isFullscreen);
    },

    handleFullscreenKeys(e) {
        if (e.key === "ArrowLeft") fullscreen.prev();
        if (e.key === "ArrowRight") fullscreen.next();
        if (e.key === "Delete") fullscreen.delete();
        if (e.key === "Escape") fullscreen.close();
    },

    handleCopyShortcut(e, isFullscreen) {
        if (!e.ctrlKey || (e.key.toLowerCase() !== "c" && e.key.toLowerCase() !== "с")) return;

        const selection = window.getSelection();
        const isTextSelected = selection && selection.toString().length > 0;

        if (isTextSelected) return;

        if (isFullscreen) {
            fullscreen.copyPrompt();
        } else {
            tooltip.copyText();
        }
    }
};

// ============================================================================
// INITIALIZATION
// ============================================================================

const contentLoader = {
    async load() {
        await navigation.loadContent();
    }
};

// Global functions for HTML onclick handlers
window.updateUrl = navigation.updateUrl;
window.loadContent = contentLoader.load;
window.filterImages = gallery.filter;
window.changeSort = ui.changeSort;
window.toggleFolder = folders.toggle;
window.scrollToTop = ui.scrollToTop;
window.uncheckAllCheckboxes = gallery.uncheckAll;
window.openFullscreen = fullscreen.open;
window.closeFullscreen = fullscreen.close;
window.prevImage = fullscreen.prev;
window.nextImage = fullscreen.next;
window.deleteFullscreen = fullscreen.delete;
window.copyPromptFullscreen = fullscreen.copyPrompt;
window.copyToClipboard = clipboard.copy;
window.copyToFavorites = favorites.copy;
window.copyToFavoritesFullscreen = favorites.copyFromFullscreen;
window.deleteThumbnail = gallery.deleteThumbnail;
window.setRating = rating.set;
window.showStars = rating.showStars;
window.hideStars = rating.hideStars;
window.showTooltip = tooltip.show;
window.updateTooltipPosition = tooltip.updatePosition;
window.hideTooltip = tooltip.hide;

window.onload = function () {
    const saved = localStorage.getItem("galleryState");
    if (saved) {
        try {
            const state = JSON.parse(saved);
            if (state.currentPath && state.currentPath !== "/") {
                window.history.replaceState({}, "", state.currentPath);
            }
            if (typeof state.sidebarVisible === "boolean") {
                DOM.sidebar.classList.toggle("hidden", !state.sidebarVisible);
                document.body.classList.toggle("sidebar-visible", state.sidebarVisible);
            }
        } catch (e) {
            console.warn("Ошибка восстановления пути:", e);
        }
    }

    contentLoader.load();
    DOM.scrollToTop.classList.add("hidden");

    DOM.menuToggle.addEventListener("click", ui.toggleSidebar);

    document.querySelectorAll(".folder-row").forEach(row => {
        if (row.dataset.hasChildren === "true") {
            row.addEventListener("click", folders.toggle);
        }
    });

    window.addEventListener("scroll", () => {
        if (window.innerHeight + window.scrollY >= document.body.offsetHeight - SCROLL_THRESHOLD) {
            gallery.loadMore();
        }
        DOM.scrollToTop.classList.toggle("hidden", window.scrollY <= SCROLL_TO_TOP_THRESHOLD);
    });

    window.addEventListener("beforeunload", stateManager.save);

    DOM.gallery.addEventListener("mouseleave", tooltip.hide);
    DOM.gallery.addEventListener("mousemove", e => {
        if (DOM.tooltip.style.display === "block") {
            tooltip.updatePosition(e);
        }
    });

    document.addEventListener("change", e => {
        if (e.target.classList.contains("image-checkbox")) {
            gallery.saveCheckboxState(e);
            gallery.updateImageOpacity();
        }
    });

    document.addEventListener("keydown", keyboard.handleKeydown);

    DOM.fullscreenContainer.addEventListener("click", e => {
        const isOutside = !e.target.closest(".fullscreen-image-wrapper")
            && !e.target.closest(".nav-arrow");
        if (isOutside) fullscreen.close();
    });

    ui.updateToggleButtonPosition();
};

window.onpopstate = () => {
    gallery.stopAutoRefresh();
    contentLoader.load();
    gallery.loadCheckboxState();
    DOM.scrollToTop.classList.add("hidden");
};
