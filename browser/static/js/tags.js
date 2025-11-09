const tags = {
    renderPills(tags) {
        if (!DOM.fullscreenTagsDisplay) return;
        DOM.fullscreenTagsDisplay.innerHTML = "";

        tags.forEach(tag => {
            const span = document.createElement("span");
            span.className = "tag-pill";
            span.textContent = tag;
            span.onclick = () => {
                if (DOM.searchBox) {
                    DOM.searchBox.value = `t:${tag}`;
                    gallery.filter();
                }
                fullscreen.close();
            };
            DOM.fullscreenTagsDisplay.appendChild(span);
        });
    }
};

