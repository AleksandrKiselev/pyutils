const favorites = {
    async copy(event, metadataId) {
        event.stopPropagation();

        try {
            const result = await utils.apiRequest("/copy_to_favorites", {
                body: JSON.stringify({ id: metadataId })
            });

            if (!result.success) {
                toast.show("Ошибка копирования: " + (result.error || "неизвестная"), null, 5000);
            }
        } catch (err) {
            utils.showError("Ошибка соединения", err);
        }
    },

    copyFromFullscreen() {
        const data = state.currentImages[state.currentIndex];
        if (!data) return;
        const metadataId = data?.id || "";
        favorites.copy({ stopPropagation: () => { } }, metadataId);
    }
};

