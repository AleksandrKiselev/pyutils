const favorites = {
    async copy(event, filename) {
        event.stopPropagation();

        try {
            const result = await utils.apiRequest("/copy_to_favorites", {
                body: JSON.stringify({ filename })
            });

            if (result.success) {
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
        const imagePath = data.metadata?.image_path || "";
        favorites.copy({ stopPropagation: () => { } }, imagePath);
    }
};

