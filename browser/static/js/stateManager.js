const stateManager = {
    save() {
        const savedState = {
            currentPath: window.location.pathname,
            sortBy: DOM.sortSelect ? DOM.sortSelect.value : (state.sortBy || "date-desc"),
            sidebarVisible: document.body.classList.contains("sidebar-visible"),
            searchQuery: state.searchQuery || "",
            hideChecked: state.hideChecked || false
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

            if (saved.searchQuery && DOM.searchBox) {
                state.searchQuery = saved.searchQuery;
                DOM.searchBox.value = saved.searchQuery;
            }

            if (typeof saved.hideChecked === "boolean" && DOM.hideChecked) {
                state.hideChecked = saved.hideChecked;
                DOM.hideChecked.checked = saved.hideChecked;
            }
            
            // Обновляем формат отображения в дереве папок после восстановления состояния
            if (typeof folders !== "undefined" && folders.updateDisplayFormat) {
                // Небольшая задержка, чтобы дерево успело загрузиться
                setTimeout(() => {
                    folders.updateDisplayFormat();
                }, 100);
            }
        } catch (e) {
            console.warn("Не удалось восстановить состояние:", e);
        }
    }
};

