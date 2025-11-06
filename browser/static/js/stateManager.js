const stateManager = {
    save() {
        const state = {
            currentPath: window.location.pathname,
            searchQuery: DOM.searchBox.value.trim(),
            sortBy: DOM.sortSelect.value,
            sidebarVisible: document.body.classList.contains("sidebar-visible")
        };
        localStorage.setItem("galleryState", JSON.stringify(state));
    },

    restore() {
        const raw = localStorage.getItem("galleryState");
        if (!raw) return;

        try {
            const saved = JSON.parse(raw);

            if (saved.searchQuery !== undefined) {
                state.searchQuery = saved.searchQuery;
                DOM.searchBox.value = saved.searchQuery;
            }

            if (saved.sortBy) {
                state.sortBy = saved.sortBy;
                DOM.sortSelect.value = saved.sortBy;
            } else {
                state.sortBy = DOM.sortSelect.value;
            }

            if (typeof saved.sidebarVisible === "boolean") {
                DOM.sidebar.classList.toggle("hidden", !saved.sidebarVisible);
                document.body.classList.toggle("sidebar-visible", saved.sidebarVisible);
            }
        } catch (e) {
            console.warn("Не удалось восстановить состояние:", e);
        }
    }
};

