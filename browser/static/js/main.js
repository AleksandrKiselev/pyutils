window.updateUrl = navigation.updateUrl;
window.loadContent = contentLoader.load;
window.filterImages = gallery.filter;
window.changeSort = ui.changeSort;
window.toggleFolder = folders.toggle;
window.scrollToTop = ui.scrollToTop;
window.uncheckAllCheckboxes = gallery.uncheckAll;
window.deleteMetadata = gallery.deleteMetadata;
window.prevImage = fullscreen.prev;
window.nextImage = fullscreen.next;
window.deleteFullscreen = fullscreen.delete;
window.copyPromptFullscreen = fullscreen.copyPrompt;
window.copyToClipboard = clipboard.copy;
window.copyToFavorites = favorites.copy;
window.copyToFavoritesFullscreen = favorites.copyFromFullscreen;
window.deleteThumbnail = gallery.deleteThumbnail;
window.setRating = rating.set;
window.showStars = rating.showStars;
window.hideStars = rating.hideStars;

// Экспортируем функцию прогресс-бара для ручного запуска
window.startProgress = progressBar.start.bind(progressBar);

window.onload = function () {
    document.body.classList.add("no-transition");
    
    const saved = localStorage.getItem("galleryState");
    if (saved) {
        try {
            const state = JSON.parse(saved);
            if (state.currentPath && state.currentPath !== "/") {
                window.history.replaceState({}, "", state.currentPath);
            }
            if (typeof state.sidebarVisible === "boolean") {
                DOM.sidebar.classList.toggle("hidden", !state.sidebarVisible);
                document.body.classList.toggle("sidebar-visible", state.sidebarVisible);
            }
        } catch (e) {
            console.warn("Ошибка восстановления пути:", e);
        }
    }
    
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            document.body.classList.remove("no-transition");
        });
    });

    contentLoader.load();
    DOM.scrollToTop.classList.add("hidden");

    DOM.menuToggle.addEventListener("click", ui.closeSidebar);
    if (DOM.menuToggleFloating) {
        DOM.menuToggleFloating.addEventListener("click", ui.toggleSidebar);
    }

    document.querySelectorAll(".folder-row").forEach(row => {
        if (row.dataset.hasChildren === "true") {
            row.addEventListener("click", folders.toggle);
        }
    });

    window.addEventListener("scroll", () => {
        if (window.innerHeight + window.scrollY >= document.body.offsetHeight - SCROLL_THRESHOLD) {
            gallery.loadMore();
        }
        DOM.scrollToTop.classList.toggle("hidden", window.scrollY <= SCROLL_TO_TOP_THRESHOLD);
    });

    window.addEventListener("beforeunload", stateManager.save);

    document.addEventListener("change", e => {
        if (e.target.classList.contains("image-checkbox")) {
            gallery.saveCheckboxState(e);
            gallery.updateImageOpacity();
        }
    });

    document.addEventListener("keydown", keyboard.handleKeydown);

    DOM.fullscreenContainer.addEventListener("click", e => {
        const isOutside = !e.target.closest(".fullscreen-image-wrapper")
            && !e.target.closest(".nav-arrow");
        if (isOutside) fullscreen.close();
    });
};

window.onpopstate = () => {
    contentLoader.load();
    gallery.loadCheckboxState();
    DOM.scrollToTop.classList.add("hidden");
};

