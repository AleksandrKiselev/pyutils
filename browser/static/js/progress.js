/**
 * Модуль для отображения прогресса обработки изображений.
 */
const progressBar = {
    eventSource: null,
    taskId: null,

    connect() {
        if (!this.taskId) return;

        this.disconnect();
        this.eventSource = new EventSource(`/progress/${this.taskId}`);

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.error) {
                    this.updateError(data.error);
                    return;
                }
                this.update(data);
            } catch (error) {
                console.error("Ошибка парсинга прогресса:", error);
            }
        };

        this.eventSource.onerror = () => {
            if (this.eventSource?.readyState === EventSource.CLOSED) {
                this.disconnect();
                // Закрываем прогресс-бар если соединение закрылось
                setTimeout(() => {
                    if (this.taskId && DOM.progressContainer && !DOM.progressContainer.classList.contains("hidden")) {
                        this.close();
                    }
                }, 500);
            }
        };
    },

    update(data) {
        const { processed, total, status, message, percentage } = data;

        if (DOM.progressMessage) DOM.progressMessage.textContent = message || "Обработка изображений…";
        if (DOM.progressText) DOM.progressText.textContent = `${processed} / ${total}`;
        if (DOM.progressPercentage) DOM.progressPercentage.textContent = `${Math.round(percentage)}%`;
        if (DOM.progressBar) DOM.progressBar.style.width = `${percentage}%`;

        if (status === "completed" || status === "error") {
            this.disconnect();
            
            if (status === "completed") {
                if (DOM.progressMessage) DOM.progressMessage.textContent = "Обработка завершена успешно";
                setTimeout(() => this.close(), 300);
            } else {
                if (DOM.progressMessage) DOM.progressMessage.textContent = `Ошибка: ${message || "Неизвестная ошибка"}`;
                if (DOM.progressBar) DOM.progressBar.style.background = "#ff4444";
                setTimeout(() => this.close(), 1500);
            }
        }
    },

    updateError(errorMessage) {
        if (DOM.progressMessage) DOM.progressMessage.textContent = `Ошибка: ${errorMessage}`;
        if (DOM.progressBar) DOM.progressBar.style.background = "#ff4444";
        setTimeout(() => this.close(), 2000);
    },

    show() {
        if (!DOM.progressContainer || !DOM.progressBar || !DOM.progressMessage || 
            !DOM.progressText || !DOM.progressPercentage) {
            console.error("Progress bar elements not found in DOM");
            return;
        }
        
        DOM.progressContainer.classList.remove("hidden");
        DOM.progressBar.style.width = "0%";
        DOM.progressBar.style.background = "";
        DOM.progressText.textContent = "0 / 0";
        DOM.progressPercentage.textContent = "0%";
        
        // Блокируем переключение папок
        this.blockNavigation();
    },

    close() {
        this.disconnect();
        if (DOM.progressContainer) {
            DOM.progressContainer.classList.add("hidden");
        }
        this.taskId = null;
        
        // Разблокируем переключение папок
        this.unblockNavigation();
    },

    blockNavigation() {
        // Блокируем все контролы сайдбара
        const sidebar = DOM.sidebar;
        if (!sidebar) return;

        // Блокируем ссылки папок
        sidebar.querySelectorAll(".folder-tree a").forEach(link => {
            link.classList.add("disabled");
            link.style.pointerEvents = "none";
            link.style.opacity = "0.5";
        });

        // Блокируем кнопки разворачивания папок
        sidebar.querySelectorAll(".folder-toggle").forEach(toggle => {
            toggle.style.pointerEvents = "none";
            toggle.style.opacity = "0.5";
            toggle.style.cursor = "not-allowed";
        });

        // Блокируем поле поиска
        if (DOM.searchBox) {
            DOM.searchBox.disabled = true;
            DOM.searchBox.style.opacity = "0.5";
            DOM.searchBox.style.cursor = "not-allowed";
        }

        // Блокируем выпадающий список сортировки
        if (DOM.sortSelect) {
            DOM.sortSelect.disabled = true;
            DOM.sortSelect.style.opacity = "0.5";
            DOM.sortSelect.style.cursor = "not-allowed";
        }

        // Блокируем кнопки действий
        sidebar.querySelectorAll("button.reset-checkboxes-btn, button.delete-metadata-btn").forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = "0.5";
            btn.style.cursor = "not-allowed";
        });
    },

    unblockNavigation() {
        // Разблокируем все контролы сайдбара
        const sidebar = DOM.sidebar;
        if (!sidebar) return;

        // Разблокируем ссылки папок
        sidebar.querySelectorAll(".folder-tree a").forEach(link => {
            link.classList.remove("disabled");
            link.style.pointerEvents = "";
            link.style.opacity = "";
        });

        // Разблокируем кнопки разворачивания папок
        sidebar.querySelectorAll(".folder-toggle").forEach(toggle => {
            toggle.style.pointerEvents = "";
            toggle.style.opacity = "";
            toggle.style.cursor = "";
        });

        // Разблокируем поле поиска
        if (DOM.searchBox) {
            DOM.searchBox.disabled = false;
            DOM.searchBox.style.opacity = "";
            DOM.searchBox.style.cursor = "";
        }

        // Разблокируем выпадающий список сортировки
        if (DOM.sortSelect) {
            DOM.sortSelect.disabled = false;
            DOM.sortSelect.style.opacity = "";
            DOM.sortSelect.style.cursor = "";
        }

        // Разблокируем кнопки действий
        sidebar.querySelectorAll("button.reset-checkboxes-btn, button.delete-metadata-btn").forEach(btn => {
            btn.disabled = false;
            btn.style.opacity = "";
            btn.style.cursor = "";
        });
    },

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
};

