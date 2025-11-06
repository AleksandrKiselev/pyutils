const tags = {
    async fetchAll() {
        try {
            const res = await fetch("/all_tags");
            state.allTags = await res.json();
        } catch (err) {
            console.error("Ошибка загрузки тегов:", err);
        }
    },

    renderPills(tags) {
        DOM.fullscreenTagsDisplay.innerHTML = "";

        tags.forEach(tag => {
            const span = document.createElement("span");
            span.className = "tag-pill";
            span.textContent = tag;
            span.onclick = () => {
                DOM.searchBox.value = `t:${tag}`;
                gallery.filter();
                fullscreen.close();
            };
            DOM.fullscreenTagsDisplay.appendChild(span);
        });
    }
};

