const gallery = {
    async load() {
        state.loading = false;
        if (DOM.sortSelect) {
            const currentSortBy = DOM.sortSelect.value;
            if (currentSortBy !== state.sortBy) {
                state.sortBy = currentSortBy;
            }
        }
        
        const foldersPromise = folders.load();
        
        state.offset = 0;
        state.currentImages = [];
        if (DOM.gallery) DOM.gallery.innerHTML = "";
        if (DOM.loading && DOM.loading.style.display === "block") {
            DOM.loading.style.display = "none";
        }
        
        await gallery.ensureMetadataGenerated();
        await foldersPromise;
        
        // Загружаем галерею только если обработка не запущена
        // Если обработка запущена, галерея загрузится автоматически после завершения
        if (!progressBar.taskId) {
            await gallery.loadMore();
        }
    },

    async ensureMetadataGenerated() {
        if (!progressBar) return;

        const currentPath = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
        const isGlobalSearch = state.searchQuery && state.searchQuery.trim().toLowerCase().startsWith("g:");
        const pathToCheck = isGlobalSearch ? "" : currentPath;
        
        try {
            if (progressBar.taskId) {
                progressBar.close();
            }

            let needs_processing = false;
            
            try {
                progressBar.showChecking("Проверка папки...");
                
                const timeoutPromise = new Promise((_, reject) => 
                    setTimeout(() => reject(new Error("Timeout")), 2000)
                );
                
                const checkResponse = await Promise.race([
                    fetch("/processing/check", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ path: pathToCheck })
                    }),
                    timeoutPromise
                ]);
                
                const { needs_processing: needs } = await checkResponse.json();
                needs_processing = needs;
            } catch (error) {
                needs_processing = true;
            }
            
            if (!needs_processing) {
                progressBar.close();
                return;
            }

            progressBar.showChecking("Запуск обработки...");

            const response = await fetch("/processing/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: pathToCheck })
            });

            const { success, task_id, error } = await response.json();
            
            if (!success) {
                throw new Error(error || "Ошибка запуска обработки");
            }

            progressBar.taskId = task_id;
            progressBar.connect();
        } catch (error) {
            console.error("Ошибка запуска обработки:", error);
            progressBar.close();
        }
    },

    async loadMore(limit = LIMIT) {
        if (state.loading) return;
        state.loading = true;

        try {
            const [sort, order] = state.sortBy.split("-");
            const isRandom = sort === "random";
            
            // Для случайной сортировки offset не важен, но передаем его для совместимости
            const hideCheckedParam = state.hideChecked ? "&hide_checked=true" : "";
            const path = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
            const query = `/metadata?path=${encodeURIComponent(path)}&limit=${limit}&offset=${state.offset}&search=${encodeURIComponent(state.searchQuery)}&sort_by=${sort}&order=${order}${hideCheckedParam}`;
            const images = await (await fetch(query)).json();

            // Для обычной сортировки останавливаемся при пустом массиве (конец пагинации)
            if (!isRandom && !images.length) {
                state.loading = false;
                return;
            }

            // Для случайной сортировки: если получили пустой массив, значит коллекция пуста
            if (isRandom && !images.length) {
                state.loading = false;
                return;
            }

            images.forEach(img => {
                if (img.rating === undefined || img.rating === null) {
                    img.rating = 0;
                }
            });

            const startIndex = state.currentImages.length;
            state.currentImages.push(...images);
            const cardsHTML = gallery.renderCards(images, startIndex);
            if (DOM.gallery) DOM.gallery.insertAdjacentHTML("beforeend", cardsHTML);

            gallery.loadCheckboxState();
            images.forEach(img => {
                const metadataId = img?.id || "";
                rating.updateStars(null, metadataId, img?.rating || 0);
            });
            
            await gallery.loadThumbnails(images.map(img => img?.id).filter(Boolean));
            
            // Для случайной сортировки не увеличиваем offset, чтобы загрузка продолжалась бесконечно
            // Для обычной сортировки увеличиваем offset как обычно
            if (!isRandom) {
                state.offset += images.length;
            }
        } catch (error) {
            console.error("Ошибка загрузки изображений:", error);
        } finally {
            state.loading = false;
        }
    },

    async loadThumbnails(metadataIds) {
        if (!metadataIds || metadataIds.length === 0) return;
        
        try {
            const response = await fetch("/thumbnails", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids: metadataIds })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const thumbnails = await response.json();
            
            metadataIds.forEach(metadataId => {
                const thumbnailBase64 = thumbnails[metadataId];
                if (thumbnailBase64) {
                    const imgElements = document.querySelectorAll(`img[data-thumbnail-id="${metadataId}"]`);
                    imgElements.forEach(img => {
                        img.src = `data:image/avif;base64,${thumbnailBase64}`;
                    });
                }
            });
        } catch (error) {
            console.error("Ошибка загрузки миниатюр:", error);
        }
    },

    renderCards(images, startIndex = null) {
        // Если startIndex не передан, используем state.offset для обратной совместимости
        const baseIndex = startIndex !== null ? startIndex : state.offset;
        
        return images.map((img, index) => {
            const metadataId = img?.id || "";
            
            const promptText = img.prompt || "";
            const prompt = utils.escapeJS(promptText || "промпт не найден");
            const metadataIdEscaped = utils.escapeJS(metadataId);
            const metadataIdAttrEscaped = metadataId ? metadataId.replace(/"/g, "&quot;").replace(/'/g, "&#39;") : "";
            const filenameOnly = img?.filename || "";
            const filenameOnlyEscaped = utils.escapeJS(filenameOnly);
            const fileSizeFormatted = utils.formatFileSize(img.size || 0);
            const ratingValue = img.rating || 0;

            const tags = img.tags || [];
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
                <div class="image-container" onclick="fullscreen.open(${baseIndex + index})"
                     onmouseenter="rating.showStars(event)" onmouseleave="rating.hideStars(event)" ${aspectRatioStyle}>
                    <div class="image-buttons">
                        <button class="copy-btn" onclick="clipboard.copy(event, '${utils.escapeJS(promptText)}')" title="Копировать промпт">⧉</button>
                        <button class="copy-favorites-btn" onclick="favorites.copy(event, '${metadataIdEscaped}')" title="В избранное">★</button>
                        <input type="checkbox" class="image-checkbox" data-id="${metadataIdAttrEscaped}"
                               onclick="event.stopPropagation();" title="Выбрать">
                        <button class="delete-btn" onclick="gallery.deleteThumbnail(event, '${metadataIdEscaped}')" title="Удалить">✕</button>
                    </div>
                    <div class="image-rating" style="opacity: 0;">
                        ${Array.from({ length: MAX_RATING }, (_, i) => i + 1).map(star => `
                            <span class="star" data-id="${metadataIdAttrEscaped}" data-rating="${star}"
                                  onclick="rating.set(event, '${metadataIdEscaped}', ${star})">
                                ${ratingValue >= star ? STARRED_SYMBOL : UNSTARRED_SYMBOL}
                            </span>`).join("")}
                    </div>
                    <img data-thumbnail-id="${metadataIdEscaped}" alt="Image" loading="lazy"
                         onload="this.parentElement.classList.add('image-loaded')"
                         onmouseenter="gallery.setHoveredPrompt('${prompt}')">
                    <div class="image-filename"><span class="filename-text">${filenameOnlyEscaped}</span> <span class="file-size">${fileSizeFormatted}</span></div>
                </div>`;
        }).join("");
    },

    async filter() {
        // Блокируем фильтрацию во время генерации метаданных
        if (progressBar.taskId) {
            toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
            return;
        }
        
        const searchBox = DOM.searchBox;
        if (!searchBox) return;
        
        const searchValue = searchBox.value;
        state.searchQuery = searchValue.trim();
        if (DOM.sortSelect) {
            state.sortBy = DOM.sortSelect.value;
        }
        // Сохраняем состояние после изменения поиска
        if (typeof stateManager !== "undefined" && stateManager.save) {
            stateManager.save();
        }
        await gallery.load();
    },

    async deleteThumbnail(event, metadataId) {
        event.stopPropagation();
        if (!confirm("Удалить изображение?")) return;

        try {
            const result = await utils.apiRequest(`/images/${metadataId}`, {
                method: "DELETE"
            });

            if (result.success) {
                event.target.closest(".image-container")?.remove();
            } else {
                toast.show("Ошибка удаления: " + (result.error || "неизвестная"), null, 5000);
            }
        } catch (error) {
            utils.showError("Ошибка удаления", error);
        }
    },

    saveCheckboxState(event) {
        const cb = event.target;
        
        utils.apiRequest("/metadata", {
            method: "POST",
            body: JSON.stringify({ id: cb.dataset.id, checked: cb.checked })
        }).catch(console.error);
    },

    loadCheckboxState() {
        document.querySelectorAll(".image-checkbox").forEach(cb => {
            const img = utils.findImageById(cb.dataset.id);
            if (img) cb.checked = !!img.checked;
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
        // Блокируем сброс чекбоксов во время генерации метаданных
        if (progressBar.taskId) {
            toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
            return;
        }
        
        // Проверяем, есть ли отмеченные изображения
        const hasChecked = Array.from(document.querySelectorAll(".image-checkbox:checked")).length > 0 ||
            state.currentImages.some(img => img && img.checked);
        
        if (!hasChecked) {
            toast.show("Нет отмеченных изображений", null, 3000);
            return;
        }
        
        if (!confirm("Снять выделение со всех отмеченных изображений?")) {
            return;
        }
        
        const currentPath = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
        const searchQuery = state.searchQuery || "";

        try {
            const result = await utils.apiRequest("/metadata/uncheck", {
                method: "POST",
                body: JSON.stringify({ path: currentPath, search: searchQuery })
            });

            if (result.success) {
                // Подсчитываем, сколько изображений было отмечено (до снятия чекбоксов)
                let checkedCount = 0;
                const checkedImages = new Set();
                
                state.currentImages.forEach(img => {
                    if (img && img.checked) {
                        checkedCount++;
                        checkedImages.add(img.id);
                        img.checked = false;
                    }
                });

                document.querySelectorAll(".image-checkbox").forEach(cb => {
                    if (cb.checked && !checkedImages.has(cb.dataset.id)) {
                        checkedCount++;
                    }
                    cb.checked = false;
                    const container = cb.closest(".image-container");
                    if (container) container.classList.remove("checked");
                });
            }
        } catch (error) {
            utils.showError("Ошибка сброса чекбоксов", error);
        }
    },

    async deleteCheckedImages() {
        // Блокируем удаление во время генерации метаданных
        if (progressBar.taskId) {
            toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
            return;
        }
        
        const currentPath = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
        const searchQuery = state.searchQuery || "";

        // Проверяем, есть ли отмеченные изображения
        const hasChecked = Array.from(document.querySelectorAll(".image-checkbox:checked")).length > 0 ||
            state.currentImages.some(img => img && img.checked);
        
        if (!hasChecked) {
            toast.show("Нет отмеченных изображений", null, 3000);
            return;
        }

        if (!confirm("Удалить все отмеченные изображения? Это действие нельзя отменить.")) {
            return;
        }

        try {
            const result = await utils.apiRequest("/images/checked", {
                method: "DELETE",
                body: JSON.stringify({ path: currentPath, search: searchQuery })
            });

            if (result.success) {             
                toast.show(`Удалено изображений: ${result.count || 0}`, null, 3000);
                gallery.load();
            }
        } catch (error) {
            utils.showError("Ошибка удаления изображений", error);
        }
    },

    rebindIndices() {
        document.querySelectorAll("#gallery .image-container").forEach((container, i) => {
            container.setAttribute("onclick", `fullscreen.open(${i})`);
        });
    },

    setHoveredPrompt(prompt) {
        state.lastHoveredPrompt = prompt;
    },

    async downloadUncheckedPrompts() {
        // Блокируем скачивание во время генерации метаданных
        if (progressBar.taskId) {
            toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
            return;
        }

        try {
            const path = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
            const isGlobalSearch = state.searchQuery && state.searchQuery.trim().toLowerCase().startsWith("g:");
            const searchPath = isGlobalSearch ? "" : path;
            const query = `/prompts/unchecked?path=${encodeURIComponent(searchPath)}&search=${encodeURIComponent(state.searchQuery)}&sort_by=${state.sortBy.split("-")[0]}&order=${state.sortBy.split("-")[1] || "desc"}`;
            const result = await (await fetch(query)).json();

            if (!result.prompts) {
                toast.show("Ошибка получения промптов", null, 3000);
                return;
            }

            const prompts = result.prompts.filter(p => p && p.trim()); // Фильтруем пустые промпты

            if (prompts.length === 0) {
                toast.show("Нет неотмеченных изображений", null, 3000);
                return;
            }

            // Создаем содержимое файла (каждый промпт с новой строки)
            const content = prompts.join("\n");
            
            // Создаем blob и скачиваем файл
            const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `prompts_${new Date().toISOString().slice(0, 10)}.txt`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);

            toast.show(`Скачано промптов: ${prompts.length}`, null, 3000);
        } catch (error) {
            utils.showError("Ошибка скачивания промптов", error);
        }
    }
};

