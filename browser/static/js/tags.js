const tags = {
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

