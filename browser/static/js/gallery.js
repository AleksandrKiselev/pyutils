const gallery = {
    async load() {
        state.loading = false;
        const currentSortBy = DOM.sortSelect.value;
        if (currentSortBy !== state.sortBy) {
            state.sortBy = currentSortBy;
        }
        await folders.load();
        state.offset = 0;
        state.currentImages = [];
        DOM.gallery.innerHTML = "";
        if (DOM.loading.style.display === "block") {
            DOM.loading.style.display = "none";
        }
        
        // Запускаем обработку изображений с прогресс-баром только если он не активен
        if (progressBar && !progressBar.taskId) {
            progressBar.start().catch(err => console.error("Ошибка запуска прогресс-бара:", err));
        }
        
        await gallery.loadMore();
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

            gallery.loadCheckboxState();
            images.forEach(img => rating.updateStars(null, img.filename, img.metadata.rating || 0));
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
            if (!img.metadata) {
                img.metadata = {};
            }
            const prompt = utils.escapeJS(img.metadata.prompt || "");
            const filenameEscaped = utils.escapeJS(img.filename || "");
            const filenameAttrEscaped = img.filename ? img.filename.replace(/"/g, "&quot;").replace(/'/g, "&#39;") : "";
            const ratingValue = img.metadata.rating || 0;

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
                         onmouseenter="gallery.setHoveredPrompt('${prompt}')">
                </div>`;
        }).join("");
    },

    filter() {
        state.searchQuery = DOM.searchBox.value.trim();
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
                    if (img.metadata) {
                        img.metadata.checked = false;
                    }
                });
            }
        } catch (error) {
            console.error("Ошибка сброса чекбоксов:", error);
            const errorMessage = error.message || error.toString();
            alert("Ошибка сброса чекбоксов: " + errorMessage);
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

