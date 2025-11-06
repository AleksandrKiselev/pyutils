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
    }
};

