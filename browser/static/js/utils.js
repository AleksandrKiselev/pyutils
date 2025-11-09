const utils = {
    escapeHTML(str) {
        if (!str) return "";
        const map = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        };
        return str.replace(/[&<>"']/g, m => map[m]);
    },

    escapeJS(str) {
        if (!str) return "";
        return str
            .replace(/\\/g, "\\\\")
            .replace(/'/g, "\\'")
            .replace(/"/g, '\\"')
            .replace(/\n/g, "\\n")
            .replace(/\r/g, "\\r")
            .replace(/\t/g, "\\t");
    },

    formatFileSize(bytes) {
        if (bytes >= 1024 * 1024) {
            return (bytes / (1024 * 1024)).toFixed(2) + " MB";
        }
        if (bytes >= 1024) {
            return (bytes / 1024).toFixed(2) + " KB";
        }
        return bytes + " B";
    },

    findImageById(metadataId) {
        return state.currentImages.find(img => (img?.id || "") === metadataId);
    },

    async apiRequest(endpoint, options = {}) {
        const defaultOptions = {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            ...options
        };
        try {
            const response = await fetch(endpoint, defaultOptions);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `HTTP ${response.status}: ${response.statusText}` }));
                console.error(`Ошибка API запроса: ${endpoint}`, response.status, errorData);
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`Ошибка API запроса: ${endpoint}`, error);
            throw error;
        }
    },

    showError(message, error) {
        const errorMessage = error?.message || error?.toString() || "неизвестная ошибка";
        toast.show(message + ": " + errorMessage, null, 5000);
    }
};

