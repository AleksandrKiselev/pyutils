const ui = {
    changeSort() {
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

