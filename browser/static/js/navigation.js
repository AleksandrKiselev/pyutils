const navigation = {
    async updateUrl(event, path) {
        event.preventDefault();
        if (window.location.pathname === `/${path}`) return;

        // Блокируем переключение папок, если идет генерация метаданных
        if (progressBar.taskId) {
            event.stopPropagation();
            toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
            return;
        }

        // Закрываем полноэкранный режим при переключении папки
        if (DOM.fullscreenContainer.style.display === "flex") {
            fullscreen.close();
        }

        state.loading = false;
        stateManager.save();
        window.history.pushState({ path: `/${path}` }, '', `/${path}`);
        await navigation.loadContent();
        folders.updateActiveHighlight();
    },

    async loadContent() {
        DOM.loading.style.display = "block";
        try {
            const path = window.location.pathname;
            stateManager.restore();
            await (path === "/" ? folders.load() : gallery.load());
        } catch (error) {
            console.error("Ошибка загрузки контента:", error);
        } finally {
            DOM.loading.style.display = "none";
        }
        tags.fetchAll();
    }
};

