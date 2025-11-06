/**
 * Модуль для отображения прогресса обработки изображений.
 */
const progressBar = {
    eventSource: null,
    taskId: null,

    async start() {
        const currentPath = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
        
        try {
            // Проверяем, нужна ли обработка
            const checkResponse = await fetch("/check_processing_needed", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: currentPath })
            });

            const { needs_processing } = await checkResponse.json();
            
            if (!needs_processing) {
                return; // Все изображения уже обработаны
            }

            // Запускаем обработку
            const response = await fetch("/process_images", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: currentPath })
            });

            const { success, task_id, error } = await response.json();
            
            if (!success) {
                throw new Error(error || "Ошибка запуска обработки");
            }

            this.taskId = task_id;
            this.show();
            this.connect();
        } catch (error) {
            console.error("Ошибка запуска обработки:", error);
        }
    },

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
                }, 1000);
            }
        };
    },

    update(data) {
        const { processed, total, status, message, percentage } = data;

        if (DOM.progressMessage) DOM.progressMessage.textContent = message || "Обработка изображений...";
        if (DOM.progressText) DOM.progressText.textContent = `${processed} / ${total}`;
        if (DOM.progressPercentage) DOM.progressPercentage.textContent = `${Math.round(percentage)}%`;
        if (DOM.progressBar) DOM.progressBar.style.width = `${percentage}%`;

        if (status === "completed" || status === "error") {
            this.disconnect();
            
            if (status === "completed") {
                if (DOM.progressMessage) DOM.progressMessage.textContent = "Обработка завершена успешно";
                setTimeout(() => this.close(), 1500);
            } else {
                if (DOM.progressMessage) DOM.progressMessage.textContent = `Ошибка: ${message || "Неизвестная ошибка"}`;
                if (DOM.progressBar) DOM.progressBar.style.background = "#ff4444";
                setTimeout(() => this.close(), 2000);
            }
        }
    },

    updateError(errorMessage) {
        if (DOM.progressMessage) DOM.progressMessage.textContent = `Ошибка: ${errorMessage}`;
        if (DOM.progressBar) DOM.progressBar.style.background = "#ff4444";
        setTimeout(() => this.close(), 3000);
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
    },

    close() {
        this.disconnect();
        if (DOM.progressContainer) {
            DOM.progressContainer.classList.add("hidden");
        }
        this.taskId = null;
    },

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
};

