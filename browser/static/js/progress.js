const progressBar = {
    eventSource: null,
    taskId: null,
    _fallbackTimer: null,

    connect() {
        if (!this.taskId) return;

        this.disconnect();
        this.eventSource = new EventSource(`/processing/${this.taskId}/progress`);
        
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
                    } else {
                        this.close();
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

        if (DOM.progressContainer?.classList.contains("hidden")) {
            this.show();
        }

        if (DOM.progressBar && DOM.progressBar.style.animation) {
            DOM.progressBar.style.animation = "";
            DOM.progressBar.style.backgroundSize = "";
            DOM.progressBar.style.background = "linear-gradient(90deg, var(--accent-color) 0%, #ffb74d 100%)";
        }

        if (DOM.progressMessage) {
            if (message && message.trim()) {
                DOM.progressMessage.textContent = message;
            }
        }
        if (DOM.progressText) {
            DOM.progressText.style.display = "block";
            DOM.progressText.textContent = `${processed} / ${total}`;
        }
        if (DOM.progressPercentage) {
            DOM.progressPercentage.style.display = "block";
            DOM.progressPercentage.textContent = `${Math.round(percentage)}%`;
        }
        if (DOM.progressBar) DOM.progressBar.style.width = `${percentage}%`;

        if (status === "completed" || status === "error") {
            if (status === "completed") {
                if (total > 0) {
                    if (DOM.progressBar) DOM.progressBar.style.width = "100%";
                    if (DOM.progressPercentage) DOM.progressPercentage.textContent = "100%";
                    if (DOM.progressText) DOM.progressText.textContent = `${total} / ${total}`;
                }
                if (DOM.progressMessage) {
                    DOM.progressMessage.textContent = message || "Завершено";
                }
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
        
        if (DOM.progressMessage) {
            DOM.progressMessage.style.display = "block";
        }
        if (DOM.progressText) {
            DOM.progressText.style.display = "block";
        }
        if (DOM.progressPercentage) {
            DOM.progressPercentage.style.display = "block";
        }
        
        DOM.progressContainer.classList.remove("hidden");
        if (DOM.progressBar) {
            DOM.progressBar.style.width = "0%";
            DOM.progressBar.style.background = "linear-gradient(90deg, var(--accent-color) 0%, #ffb74d 100%)";
            DOM.progressBar.style.backgroundSize = "";
            DOM.progressBar.style.animation = "";
        }
        if (DOM.progressText) DOM.progressText.textContent = "0 / 0";
        if (DOM.progressPercentage) DOM.progressPercentage.textContent = "0%";
        this.blockNavigation();
    },

    showChecking(message) {
        if (!DOM.progressContainer) return;
        
        const msg = message || "Проверка...";
        
        if (DOM.progressMessage) {
            DOM.progressMessage.textContent = msg;
            DOM.progressMessage.style.display = "block";
        }
        
        if (DOM.progressText) {
            DOM.progressText.textContent = "";
            DOM.progressText.style.display = "none";
        }
        if (DOM.progressPercentage) {
            DOM.progressPercentage.textContent = "";
            DOM.progressPercentage.style.display = "none";
        }
        
        if (DOM.progressBar) {
            DOM.progressBar.style.width = "30%";
            DOM.progressBar.style.background = "linear-gradient(90deg, var(--accent-color) 0%, #ffb74d 50%, var(--accent-color) 100%)";
            DOM.progressBar.style.backgroundSize = "200% 100%";
            DOM.progressBar.style.animation = "progress-pulse 1.5s ease-in-out infinite";
        }
        
        DOM.progressContainer.classList.remove("hidden");
        DOM.progressContainer.style.opacity = "1";
        DOM.progressContainer.style.visibility = "visible";
        
        this.blockNavigation();
    },

    close() {
        this.disconnect();
        if (DOM.progressContainer) {
            DOM.progressContainer.classList.add("hidden");
            DOM.progressContainer.style.opacity = "";
            DOM.progressContainer.style.visibility = "";
        }
        if (DOM.progressBar) {
            DOM.progressBar.style.animation = "";
            DOM.progressBar.style.backgroundSize = "";
            DOM.progressBar.style.width = "0%";
        }
        if (DOM.progressMessage) {
            DOM.progressMessage.textContent = "";
        }
        if (DOM.progressText) {
            DOM.progressText.textContent = "";
            DOM.progressText.style.display = "";
        }
        if (DOM.progressPercentage) {
            DOM.progressPercentage.textContent = "";
            DOM.progressPercentage.style.display = "";
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

