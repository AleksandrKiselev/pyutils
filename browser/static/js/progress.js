const progressBar = {
    eventSource: null,
    taskId: null,
    _fallbackTimer: null,

    connect() {
        if (!this.taskId) return;

        this.disconnect();
        this.eventSource = new EventSource(`/progress/${this.taskId}`);
        
        this._fallbackTimer = setTimeout(() => {
            if (this.taskId) {
                this.close();
                this._reloadGallery();
            }
        }, 5 * 60 * 1000);

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.update(data);
            } catch (error) {
                console.error("Ошибка парсинга прогресса:", error);
            }
        };

        this.eventSource.onerror = () => {
            if (this.eventSource?.readyState === EventSource.CLOSED) {
                this.disconnect();
                setTimeout(() => {
                    if (this.taskId) {
                        this.close();
                        this._reloadGallery();
                    }
                }, 1000);
            }
        };
    },

    update(data) {
        const { processed, total, status, message, percentage, error } = data;

        if (error) {
            this._showError(error);
            return;
        }

        // Показываем прогресс-бар только для долгих операций (total >= 10)
        if (total >= 10 && DOM.progressContainer?.classList.contains("hidden")) {
            this.show();
        }

        if (DOM.progressMessage) DOM.progressMessage.textContent = message || "";
        if (DOM.progressText) DOM.progressText.textContent = `${processed} / ${total}`;
        if (DOM.progressPercentage) DOM.progressPercentage.textContent = `${Math.round(percentage)}%`;
        if (DOM.progressBar) DOM.progressBar.style.width = `${percentage}%`;

        if (status === "completed" || status === "error") {
            if (status === "completed" && total > 0) {
                if (DOM.progressBar) DOM.progressBar.style.width = "100%";
                if (DOM.progressPercentage) DOM.progressPercentage.textContent = "100%";
                if (DOM.progressText) DOM.progressText.textContent = `${total} / ${total}`;
            }
            
            this.disconnect();
            const delay = status === "completed" ? 500 : 2000;
            setTimeout(() => {
                this.close();
                this._reloadGallery();
            }, delay);
        }
    },

    _showError(errorMessage) {
        if (DOM.progressMessage) DOM.progressMessage.textContent = `Ошибка: ${errorMessage}`;
        if (DOM.progressBar) DOM.progressBar.style.background = "#ff4444";
        setTimeout(() => {
            this.disconnect();
            this.close();
            this._reloadGallery();
        }, 2000);
    },

    _reloadGallery() {
        if (window.location.pathname !== "/") {
            gallery.load();
        }
    },

    show() {
        if (!DOM.progressContainer) return;
        
        DOM.progressContainer.classList.remove("hidden");
        if (DOM.progressBar) {
            DOM.progressBar.style.width = "0%";
            DOM.progressBar.style.background = "";
        }
        if (DOM.progressText) DOM.progressText.textContent = "0 / 0";
        if (DOM.progressPercentage) DOM.progressPercentage.textContent = "0%";
        this.blockNavigation();
    },

    close() {
        this.disconnect();
        if (DOM.progressContainer) {
            DOM.progressContainer.classList.add("hidden");
        }
        this.taskId = null;
        this.unblockNavigation();
    },

    _toggleNavigation(block) {
        const sidebar = DOM.sidebar;
        if (!sidebar) return;

        const elements = [
            ...sidebar.querySelectorAll(".folder-tree a"),
            ...sidebar.querySelectorAll(".folder-toggle"),
            ...sidebar.querySelectorAll("button.reset-checkboxes-btn, button.delete-metadata-btn")
        ];

        if (DOM.searchBox) elements.push(DOM.searchBox);
        if (DOM.sortSelect) elements.push(DOM.sortSelect);

        elements.forEach(el => {
            if (block) {
                el.classList.add("disabled");
                el.disabled = true;
                el.style.pointerEvents = "none";
                el.style.opacity = "0.5";
                el.style.cursor = "not-allowed";
            } else {
                el.classList.remove("disabled");
                el.disabled = false;
                el.style.pointerEvents = "";
                el.style.opacity = "";
                el.style.cursor = "";
            }
        });
    },

    blockNavigation() {
        this._toggleNavigation(true);
    },

    unblockNavigation() {
        this._toggleNavigation(false);
    },

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        if (this._fallbackTimer) {
            clearTimeout(this._fallbackTimer);
            this._fallbackTimer = null;
        }
    }
};

