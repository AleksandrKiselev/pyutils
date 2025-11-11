window.updateUrl = navigation.updateUrl;
window.loadContent = navigation.loadContent;
window.filterImages = gallery.filter;
window.changeSort = ui.changeSort;
window.toggleFolder = folders.toggle;
window.scrollToTop = ui.scrollToTop;
window.uncheckAllCheckboxes = gallery.uncheckAll;
window.deleteCheckedImages = gallery.deleteCheckedImages;
window.prevImage = fullscreen.prev;
window.nextImage = fullscreen.next;
window.deleteFullscreen = fullscreen.delete;
window.copyPromptFullscreen = fullscreen.copyPrompt;
window.copyToFavoritesFullscreen = favorites.copyFromFullscreen;
window.toggleBookmarkFullscreen = bookmarks.toggleFromFullscreen.bind(bookmarks);
window.deleteThumbnail = gallery.deleteThumbnail;
window.setRating = rating.set;
window.showStars = rating.showStars;
window.hideStars = rating.hideStars;

window.onload = function () {
    document.body.classList.add("no-transition");
    
    // Восстанавливаем состояние из localStorage
    const saved = localStorage.getItem("galleryState");
    if (saved) {
        try {
            const savedState = JSON.parse(saved);
            if (savedState.currentPath && savedState.currentPath !== "/") {
                window.history.replaceState({ path: savedState.currentPath }, "", savedState.currentPath);
            } else {
                window.history.replaceState({ path: window.location.pathname }, "", window.location.pathname);
            }
        } catch (e) {
            console.warn("Ошибка восстановления пути:", e);
        }
    }
    
    // Восстанавливаем остальное состояние через stateManager
    stateManager.restore();
    
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            document.body.classList.remove("no-transition");
        });
    });

    navigation.loadContent();
    if (DOM.scrollToTop) DOM.scrollToTop.classList.add("hidden");
    
    if (typeof bookmarks !== "undefined") {
        bookmarks.render().catch(console.error);
    }
    
    if (typeof sidebarResize !== "undefined") {
        sidebarResize.init().catch(console.error);
    }

    if (DOM.menuToggle) {
        DOM.menuToggle.addEventListener("click", ui.closeSidebar);
    }
    if (DOM.menuToggleFloating) {
        DOM.menuToggleFloating.addEventListener("click", ui.toggleSidebar);
    }

    document.querySelectorAll(".folder-row").forEach(row => {
        if (row.dataset.hasChildren === "true") {
            row.addEventListener("click", folders.toggle);
        }
    });

    folders.restoreState();

    window.addEventListener("scroll", () => {
        if (window.innerHeight + window.scrollY >= document.body.offsetHeight - SCROLL_THRESHOLD) {
            gallery.loadMore();
        }
        if (DOM.scrollToTop) {
            DOM.scrollToTop.classList.toggle("hidden", window.scrollY <= SCROLL_TO_TOP_THRESHOLD);
        }
    });

    window.addEventListener("beforeunload", stateManager.save);

    document.addEventListener("change", e => {
        if (e.target.classList.contains("image-checkbox")) {
            gallery.saveCheckboxState(e);
            gallery.updateImageOpacity();
        }
    });

    if (DOM.searchBox) {
        DOM.searchBox.addEventListener("keydown", e => {
            if (e.key === "Enter") {
                e.preventDefault();
                gallery.filter();
            }
        });
    }

    document.addEventListener("keydown", keyboard.handleKeydown);

    if (DOM.fullscreenContainer) {
        DOM.fullscreenContainer.addEventListener("click", e => {
            const isOutside = !e.target.closest(".fullscreen-image-wrapper")
                && !e.target.closest(".nav-arrow");
            if (isOutside) fullscreen.close();
        });
    }
};

window.onpopstate = (event) => {
    // Блокируем переключение папок, если идет генерация метаданных
    if (progressBar.taskId) {
        // Возвращаемся обратно к предыдущему состоянию
        const previousPath = event.state?.path || window.location.pathname;
        window.history.pushState({ path: previousPath }, '', previousPath);
        toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
        return;
    }

    // Закрываем полноэкранный режим при переключении папки (назад/вперед)
    if (DOM.fullscreenContainer && DOM.fullscreenContainer.style.display === "flex") {
        fullscreen.close();
    }
    
    navigation.loadContent();
    gallery.loadCheckboxState();
    if (DOM.scrollToTop) DOM.scrollToTop.classList.add("hidden");
};

