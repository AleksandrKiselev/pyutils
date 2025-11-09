const keyboard = {
    handleKeydown(e) {
        const isFullscreen = DOM.fullscreenContainer && DOM.fullscreenContainer.style.display === "flex";
        const isSidebarVisible = document.body.classList.contains("sidebar-visible");

        if (e.key === "Escape" && isSidebarVisible && !isFullscreen) {
            ui.closeSidebar();
            return;
        }

        if (isFullscreen) {
            keyboard.handleFullscreenKeys(e);
        }

        keyboard.handleCopyShortcut(e, isFullscreen);
    },

    handleFullscreenKeys(e) {
        if (e.key === "ArrowLeft") fullscreen.prev();
        if (e.key === "ArrowRight") fullscreen.next();
        if (e.key === "Delete") fullscreen.delete();
        if (e.key === "Escape") fullscreen.close();
    },

    handleCopyShortcut(e, isFullscreen) {
        if (!e.ctrlKey || (e.key.toLowerCase() !== "c" && e.key.toLowerCase() !== "с")) return;

        const selection = window.getSelection();
        const isTextSelected = selection && selection.toString().length > 0;

        if (isTextSelected) return;

        if (isFullscreen) {
            e.preventDefault();
            fullscreen.copyPrompt();
        } else {
            if (state.lastHoveredPrompt) {
                e.preventDefault();
                navigator.clipboard.writeText(state.lastHoveredPrompt).then(() => {
                    toast.show("Промпт скопирован", state.lastHoveredPrompt);
                }).catch(console.error);
            }
        }
    }
};

