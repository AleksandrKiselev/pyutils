const ui = {
    changeSort() {
        if (!DOM.sortSelect) return;
        
        if (progressBar.taskId) {
            toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
            DOM.sortSelect.value = state.sortBy;
            return;
        }
        
        const newSortBy = DOM.sortSelect.value;
        state.sortBy = newSortBy;
        stateManager.save();
        gallery.load();
    },

    scrollToTop() {
        window.scrollTo({ top: 0, behavior: "smooth" });
    },

    toggleSidebar() {
        document.body.classList.toggle("sidebar-visible");
    },

    closeSidebar() {
        document.body.classList.remove("sidebar-visible");
    }
};

