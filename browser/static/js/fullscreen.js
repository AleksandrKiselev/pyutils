const fullscreen = {
    open(index) {
        state.currentIndex = index;
        fullscreen.updateView();
        DOM.fullscreenContainer.style.display = "flex";
    },

    close() {
        DOM.fullscreenContainer.style.display = "none";
    },

    updateView() {
        const data = state.currentImages[state.currentIndex];
        if (!data) return;

        const imagePath = data?.image_path || "";
        const metadataId = data?.id || "";

        DOM.fullscreenImg.src = `/serve_image/${imagePath}`;

        DOM.fullscreenPrompt.dataset.prompt = data.prompt;
        DOM.fullscreenPrompt.textContent = data.prompt || "";

        const filenameOnly = imagePath ? imagePath.split(/[/\\]/).pop() : "";
        DOM.fullscreenFilename.innerHTML = `${filenameOnly} <span class="file-size">${utils.formatFileSize(data.size || 0)}</span>`;

        const miniCheckbox = document.querySelector(`.image-checkbox[data-id="${metadataId}"]`);
        const isChecked = miniCheckbox ? miniCheckbox.checked : !!data.checked;

        DOM.fullscreenCheckbox.dataset.id = metadataId;
        DOM.fullscreenCheckbox.checked = isChecked;

        const wrapper = document.querySelector(".fullscreen-image-wrapper");
        wrapper?.classList.toggle("checked", isChecked);

        DOM.fullscreenTagsDisplay.innerHTML = "";
        tags.renderPills(data.tags || []);

        fullscreen.setupCheckboxHandler(data, miniCheckbox, wrapper);
        fullscreen.setupRatingHandler(data);
    },

    setupCheckboxHandler(data, miniCheckbox, wrapper) {
        DOM.fullscreenCheckbox.onchange = function () {
            const checked = DOM.fullscreenCheckbox.checked;
            data.checked = checked;
            wrapper?.classList.toggle("checked", checked);

            if (miniCheckbox) {
                miniCheckbox.checked = checked;
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

                const img = utils.findImageById(data?.id || "");
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
        const prompt = DOM.fullscreenPrompt.dataset.prompt;
        if (prompt) {
            navigator.clipboard.writeText(prompt).then(() => {
                toast.show("Промпт скопирован", prompt);
            }).catch(console.error);
        }
    }
};

