const stateManager = {
    save() {
        const savedState = {
            currentPath: window.location.pathname,
            sortBy: DOM.sortSelect ? DOM.sortSelect.value : (state.sortBy || "date-desc"),
            sidebarVisible: document.body.classList.contains("sidebar-visible")
        };
        localStorage.setItem("galleryState", JSON.stringify(savedState));
        if (typeof folders !== "undefined" && folders.saveState) {
            folders.saveState();
        }
    },

    restore() {
        const raw = localStorage.getItem("galleryState");
        if (!raw) return;

        try {
            const saved = JSON.parse(raw);

            if (saved.sortBy && DOM.sortSelect) {
                state.sortBy = saved.sortBy;
                DOM.sortSelect.value = saved.sortBy;
            } else if (DOM.sortSelect) {
                state.sortBy = DOM.sortSelect.value;
            }

            if (typeof saved.sidebarVisible === "boolean" && DOM.sidebar) {
                DOM.sidebar.classList.toggle("hidden", !saved.sidebarVisible);
                document.body.classList.toggle("sidebar-visible", saved.sidebarVisible);
            }
        } catch (e) {
            console.warn("Не удалось восстановить состояние:", e);
        }
    }
};

