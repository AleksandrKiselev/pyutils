const fullscreen = {
    open(index) {
        state.currentIndex = index;
        fullscreen.updateView();
        if (DOM.fullscreenContainer) DOM.fullscreenContainer.style.display = "flex";
        fullscreen.setupImageClickHandler();
    },

    setupImageClickHandler() {
        if (!DOM.fullscreenImg) return;
        
        // Удаляем старый обработчик, если есть
        DOM.fullscreenImg.onclick = null;
        
        // Добавляем новый обработчик
        DOM.fullscreenImg.onclick = function(e) {
            // Проверяем, что клик был именно на изображении, а не на элементах управления
            const target = e.target;
            const isControlElement = target.closest('.fullscreen-buttons') || 
                                   target.closest('.fullscreen-rating') ||
                                   target.closest('.nav-arrow') ||
                                   target.closest('.fullscreen-prompt') ||
                                   target.closest('.fullscreen-tags-overlay') ||
                                   target.closest('.fullscreen-filename');
            
            if (!isControlElement && target === DOM.fullscreenImg) {
                fullscreen.close();
            }
        };
    },

    close() {
        if (DOM.fullscreenContainer) DOM.fullscreenContainer.style.display = "none";
    },

    updateView() {
        const data = state.currentImages[state.currentIndex];
        if (!data) return;

        const metadataId = data?.id || "";

        if (DOM.fullscreenImg) DOM.fullscreenImg.src = `/serve_image/${metadataId}`;

        if (DOM.fullscreenPrompt) {
            const promptText = data.prompt || "";
            DOM.fullscreenPrompt.dataset.prompt = promptText;
            DOM.fullscreenPrompt.textContent = promptText || "промпт не найден";
        }

        const filenameOnly = data?.filename || "";
        if (DOM.fullscreenFilename) {
            DOM.fullscreenFilename.innerHTML = `<span class="filename-text">${filenameOnly}</span> <span class="file-size">${utils.formatFileSize(data.size || 0)}</span>`;
        }

        const miniCheckbox = document.querySelector(`.image-checkbox[data-id="${metadataId}"]`);
        const isChecked = miniCheckbox ? miniCheckbox.checked : !!data.checked;

        if (DOM.fullscreenCheckbox) {
            DOM.fullscreenCheckbox.dataset.id = metadataId;
            DOM.fullscreenCheckbox.checked = isChecked;
        }

        const wrapper = document.querySelector(".fullscreen-image-wrapper");
        wrapper?.classList.toggle("checked", isChecked);

        tags.renderPills(data.tags || []);

        fullscreen.setupCheckboxHandler(data, miniCheckbox, wrapper);
        fullscreen.setupRatingHandler(data);
        
        if (typeof bookmarks !== "undefined") {
            bookmarks.updateFullscreenButton(metadataId);
        }
    },

    setupCheckboxHandler(data, miniCheckbox, wrapper) {
        if (!DOM.fullscreenCheckbox) return;
        
        DOM.fullscreenCheckbox.onchange = function () {
            const checked = DOM.fullscreenCheckbox.checked;
            data.checked = checked;
            wrapper?.classList.toggle("checked", checked);

            if (miniCheckbox) {
                // Временно отключаем обработчик, чтобы избежать двойного обновления счетчика
                const wasHandled = miniCheckbox.dataset.handling;
                miniCheckbox.dataset.handling = "true";
                miniCheckbox.checked = checked;
                delete miniCheckbox.dataset.handling;
                
                const container = miniCheckbox.closest(".image-container");
                if (container) {
                    container.classList.toggle("checked", checked);
                }
            }

            const metadataId = data?.id || "";
            
            utils.apiRequest("/update_metadata", {
                body: JSON.stringify({ id: metadataId, checked })
            }).catch(console.error);
        };
    },

    setupRatingHandler(data) {
        if (!DOM.fullscreenRating) return;

        const metadataId = data?.id || "";
        const stars = DOM.fullscreenRating.querySelectorAll(".star");
        const currentRating = data.rating || 0;

        stars.forEach(star => {
            const starRating = parseInt(star.dataset.rating);
            star.textContent = starRating <= currentRating ? STARRED_SYMBOL : UNSTARRED_SYMBOL;
            star.classList.toggle("selected", starRating <= currentRating);

            star.onclick = function (e) {
                e.stopPropagation();

                const currentRating = data.rating || 0;
                const newRating = currentRating === starRating ? 0 : starRating;

                data.rating = newRating;

                const img = utils.findImageById(metadataId);
                if (img) img.rating = newRating;

                stars.forEach(s => {
                    const r = parseInt(s.dataset.rating);
                    s.textContent = r <= newRating ? STARRED_SYMBOL : UNSTARRED_SYMBOL;
                    s.classList.toggle("selected", r <= newRating);
                });

                rating.updateStars(null, metadataId, newRating);

                utils.apiRequest("/update_metadata", {
                    body: JSON.stringify({ id: metadataId, rating: newRating })
                }).catch(error => {
                    console.error("Ошибка сохранения рейтинга:", error);
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

        const metadataId = data?.id || "";

        try {
            const result = await utils.apiRequest("/delete_image", {
                body: JSON.stringify({ id: metadataId })
            });

            if (result.success) {
                document.querySelector(`.image-checkbox[data-id="${metadataId}"]`)?.closest(".image-container")?.remove();
                state.currentImages.splice(state.currentIndex, 1);
                gallery.rebindIndices();

                if (state.currentImages.length === 0) {
                    fullscreen.close();
                } else {
                    if (state.currentIndex >= state.currentImages.length) {
                        state.currentIndex = state.currentImages.length - 1;
                    }
                    fullscreen.updateView();
                }
            } else {
                toast.show("Ошибка удаления: " + (result.error || "неизвестная"), null, 5000);
            }
        } catch (error) {
            utils.showError("Ошибка удаления", error);
        }
    },

    copyPrompt() {
        if (!DOM.fullscreenPrompt) return;
        const prompt = DOM.fullscreenPrompt.dataset.prompt;
        if (prompt) {
            navigator.clipboard.writeText(prompt).then(() => {
                toast.show("Промпт скопирован", prompt);
            }).catch(console.error);
        }
    }
};

