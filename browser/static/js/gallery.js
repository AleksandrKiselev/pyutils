const gallery = {
    _filterTimeout: null, // Таймер для debounce фильтрации
    
    async load() {
        state.loading = false;
        const currentSortBy = DOM.sortSelect.value;
        if (currentSortBy !== state.sortBy) {
            state.sortBy = currentSortBy;
        }
        
        const foldersPromise = folders.load();
        
        state.offset = 0;
        state.currentImages = [];
        DOM.gallery.innerHTML = "";
        if (DOM.loading.style.display === "block") {
            DOM.loading.style.display = "none";
        }
        
        await gallery.ensureMetadataGenerated();
        await foldersPromise;
        
        await gallery.loadMore();
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
                const timeoutPromise = new Promise((_, reject) => 
                    setTimeout(() => reject(new Error("Timeout")), 2000)
                );
                
                const checkResponse = await Promise.race([
                    fetch("/check_processing_needed", {
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
                return;
            }

            const response = await fetch("/process_images", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: pathToCheck })
            });

            const { success, task_id, error } = await response.json();
            
            if (!success) {
                throw new Error(error || "Ошибка запуска обработки");
            }

            progressBar.taskId = task_id;
            progressBar.show();
            progressBar.connect();
        } catch (error) {
            console.error("Ошибка запуска обработки:", error);
            if (progressBar.taskId) {
                progressBar.close();
            }
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

            images.forEach(img => {
                if (img.rating === undefined || img.rating === null) {
                    img.rating = 0;
                }
            });

            state.currentImages.push(...images);
            const cardsHTML = gallery.renderCards(images);
            DOM.gallery.insertAdjacentHTML("beforeend", cardsHTML);

            gallery.loadCheckboxState();
            images.forEach(img => {
                const metadataId = img?.id || "";
                rating.updateStars(null, metadataId, img?.rating || 0);
            });
            state.offset += images.length;

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
                                container.classList.add("image-loaded");
                            };
                        }
                    });
                };

                if (window.requestIdleCallback) {
                    requestIdleCallback(preloadImages, { timeout: 1000 });
                } else {
                    setTimeout(preloadImages, 0);
                }
            }
        } catch (error) {
            console.error("Ошибка загрузки изображений:", error);
        } finally {
            state.loading = false;
        }
    },

    renderCards(images) {
        return images.map((img, index) => {
            // Все пути хранятся в метаданных
            const metadataId = img?.id || "";
            const thumbnailPath = img?.thumb_path || "";
            const imagePath = img?.image_path || "";
            
            const prompt = utils.escapeJS(img.prompt || "");
            const metadataIdEscaped = utils.escapeJS(metadataId);
            const metadataIdAttrEscaped = metadataId ? metadataId.replace(/"/g, "&quot;").replace(/'/g, "&#39;") : "";
            const filenameOnly = imagePath ? imagePath.split(/[/\\]/).pop() : "";
            const filenameOnlyEscaped = utils.escapeJS(filenameOnly);
            const fileSize = img.size || 0;
            const fileSizeFormatted = fileSize >= 1024 * 1024 
                ? (fileSize / (1024 * 1024)).toFixed(2) + " MB"
                : fileSize >= 1024
                ? (fileSize / 1024).toFixed(2) + " KB"
                : fileSize + " B";
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
                <div class="image-container" onclick="fullscreen.open(${state.offset + index})"
                     onmouseenter="rating.showStars(event)" onmouseleave="rating.hideStars(event)" ${aspectRatioStyle}>
                    <div class="image-buttons">
                        <button class="copy-btn" onclick="clipboard.copy(event, '${prompt}')" title="Копировать промпт">⧉</button>
                        <button class="copy-favorites-btn" onclick="favorites.copy(event, '${metadataIdEscaped}')" title="В избранное">★</button>
                        <input type="checkbox" class="image-checkbox" data-id="${metadataIdAttrEscaped}"
                               onclick="event.stopPropagation(); gallery.saveCheckboxState(event);" title="Выбрать">
                        <button class="delete-btn" onclick="gallery.deleteThumbnail(event, '${metadataIdEscaped}')" title="Удалить">✕</button>
                    </div>
                    <div class="image-rating" style="opacity: 0;">
                        ${Array.from({ length: MAX_RATING }, (_, i) => i + 1).map(star => `
                            <span class="star" data-id="${metadataIdAttrEscaped}" data-rating="${star}"
                                  onclick="rating.set(event, '${metadataIdEscaped}', ${star})">
                                ${ratingValue >= star ? STARRED_SYMBOL : UNSTARRED_SYMBOL}
                            </span>`).join("")}
                    </div>
                    <img src="/serve_thumbnail/${thumbnailPath}" alt="Image" loading="lazy"
                         onload="this.parentElement.classList.add('image-loaded')"
                         onmouseenter="gallery.setHoveredPrompt('${prompt}')">
                    <div class="image-filename">${filenameOnlyEscaped} <span class="file-size">${fileSizeFormatted}</span></div>
                </div>`;
        }).join("");
    },

    filter() {
        // Блокируем фильтрацию во время генерации метаданных
        if (progressBar.taskId) {
            toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
            return;
        }
        
        // Очищаем предыдущий таймер
        if (this._filterTimeout) {
            clearTimeout(this._filterTimeout);
        }
        
        // Используем debounce для фильтрации (300ms задержка)
        // Это предотвращает множественные вызовы gallery.load() при быстром вводе
        this._filterTimeout = setTimeout(async () => {
            const searchBox = DOM.searchBox;
            
            // Сохраняем фокус и позицию курсора перед загрузкой
            const hadFocus = document.activeElement === searchBox;
            const cursorPosition = hadFocus ? searchBox.selectionStart : null;
            const searchValue = searchBox.value; // Сохраняем значение на случай если оно изменится
            
            state.searchQuery = searchValue.trim();
            state.sortBy = DOM.sortSelect.value;
            
            await gallery.load();
            
            // Восстанавливаем фокус и позицию курсора после загрузки только если поле все еще существует
            if (hadFocus && cursorPosition !== null && DOM.searchBox && document.body.contains(DOM.searchBox)) {
                // Проверяем, что значение не изменилось пользователем во время загрузки
                const currentValue = DOM.searchBox.value;
                if (currentValue === searchValue || currentValue.startsWith(searchValue)) {
                    // Используем один requestAnimationFrame для плавного восстановления
                    requestAnimationFrame(() => {
                        if (DOM.searchBox && document.body.contains(DOM.searchBox)) {
                            // Восстанавливаем значение только если оно было изменено системой
                            if (DOM.searchBox.value !== searchValue && DOM.searchBox.value !== currentValue) {
                                DOM.searchBox.value = searchValue;
                            }
                            // Восстанавливаем позицию курсора только если поле все еще в фокусе
                            if (document.activeElement === DOM.searchBox) {
                                const finalCursorPosition = Math.min(cursorPosition, DOM.searchBox.value.length);
                                DOM.searchBox.setSelectionRange(finalCursorPosition, finalCursorPosition);
                            }
                        }
                    });
                }
            }
        }, 300);
    },

    async deleteThumbnail(event, metadataId) {
        event.stopPropagation();
        if (!confirm("Удалить изображение?")) return;

        try {
            const result = await utils.apiRequest("/delete_image", {
                body: JSON.stringify({ id: metadataId })
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
            body: JSON.stringify({ id: cb.dataset.id, checked: cb.checked })
        }).catch(console.error);
    },

    loadCheckboxState() {
        document.querySelectorAll(".image-checkbox").forEach(cb => {
            const metadataId = cb.dataset.id;
            const img = state.currentImages.find(i => {
                const id = i?.id || "";
                return id === metadataId;
            });
            if (img) cb.checked = !!img?.checked;
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
        
        const currentPath = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
        const searchQuery = state.searchQuery || "";

        try {
            const result = await utils.apiRequest("/uncheck_all", {
                body: JSON.stringify({ path: currentPath, search: searchQuery })
            });

            if (result.success) {
                document.querySelectorAll(".image-checkbox").forEach(cb => {
                    cb.checked = false;
                    const container = cb.closest(".image-container");
                    if (container) container.classList.remove("checked");
                });

                state.currentImages.forEach(img => {
                    if (img) {
                        img.checked = false;
                    }
                });
            }
        } catch (error) {
            console.error("Ошибка сброса чекбоксов:", error);
            const errorMessage = error.message || error.toString();
            alert("Ошибка сброса чекбоксов: " + errorMessage);
        }
    },

    async deleteMetadata() {
        // Блокируем удаление метаданных во время генерации метаданных
        if (progressBar.taskId) {
            toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
            return;
        }
        
        const currentPath = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
        const searchQuery = state.searchQuery || "";

        if (!confirm("Удалить метаданные для всех изображений в текущей папке/фильтрах? Это действие нельзя отменить.")) {
            return;
        }

        try {
            const result = await utils.apiRequest("/delete_metadata", {
                body: JSON.stringify({ path: currentPath, search: searchQuery })
            });

            if (result.success) {
                alert(`Удалено метаданных: ${result.count || 0}`);
                // Перезагружаем галерею для обновления отображения
                // ensureMetadataGenerated() будет вызван внутри gallery.load()
                gallery.load();
            }
        } catch (error) {
            console.error("Ошибка удаления метаданных:", error);
            const errorMessage = error.message || error.toString();
            alert("Ошибка удаления метаданных: " + errorMessage);
        }
    },

    rebindIndices() {
        document.querySelectorAll("#gallery .image-container").forEach((container, i) => {
            container.setAttribute("onclick", `fullscreen.open(${i})`);
        });
    },

    setHoveredPrompt(prompt) {
        state.lastHoveredPrompt = prompt;
    }
};

