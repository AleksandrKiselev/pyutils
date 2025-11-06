const navigation = {
    async updateUrl(event, path) {
        event.preventDefault();
        if (window.location.pathname === `/${path}`) return;

        state.loading = false;
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
            console.error("Ошибка загрузки контента:", error);
        } finally {
            DOM.loading.style.display = "none";
        }
        tags.fetchAll();
    }
};

const contentLoader = {
    async load() {
        await navigation.loadContent();
    }
};

