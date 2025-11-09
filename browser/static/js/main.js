window.updateUrl = navigation.updateUrl;
window.loadContent = navigation.loadContent;
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
window.copyToFavoritesFullscreen = favorites.copyFromFullscreen;
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

    folders.restoreState();

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
    if (DOM.fullscreenContainer.style.display === "flex") {
        fullscreen.close();
    }
    
    navigation.loadContent();
    gallery.loadCheckboxState();
    DOM.scrollToTop.classList.add("hidden");
};

