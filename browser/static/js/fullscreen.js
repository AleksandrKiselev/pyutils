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

        DOM.fullscreenImg.src = `/serve_image/${data.filename}`;

        DOM.fullscreenPrompt.dataset.prompt = data.metadata.prompt;
        DOM.fullscreenPrompt.textContent = data.metadata.prompt || "";

        const filenameOnly = data.filename ? data.filename.split(/[/\\]/).pop() : "";
        const fileSize = data.size || 0;
        const fileSizeFormatted = fileSize >= 1024 * 1024 
            ? (fileSize / (1024 * 1024)).toFixed(2) + " MB"
            : fileSize >= 1024
            ? (fileSize / 1024).toFixed(2) + " KB"
            : fileSize + " B";
        DOM.fullscreenFilename.innerHTML = `${filenameOnly} <span class="file-size">${fileSizeFormatted}</span>`;

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
                const newRating = currentRating === starRating ? 0 : starRating;

                data.metadata.rating = newRating;

                const img = state.currentImages.find(i => i.filename === data.filename);
                if (img) {
                    img.metadata.rating = newRating;
                }

                stars.forEach(s => {
                    const r = parseInt(s.dataset.rating);
                    s.textContent = r <= newRating ? STARRED_SYMBOL : UNSTARRED_SYMBOL;
                    s.classList.toggle("selected", r <= newRating);
                });

                rating.updateStars(null, data.filename, newRating);

                utils.apiRequest("/update_metadata", {
                    body: JSON.stringify({ filename: data.filename, rating: newRating })
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
            navigator.clipboard.writeText(prompt).then(() => {
                toast.show("Промпт скопирован", prompt);
            }).catch(console.error);
        }
    }
};

