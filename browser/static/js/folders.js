const folders = {
    async load() {
        const folderList = DOM.sidebar.querySelector(".sidebar-folders");
        if (!folderList) return;

        try {
            const response = await fetch("/");
            const doc = new DOMParser().parseFromString(await response.text(), "text/html");
            const incomingFolders = doc.querySelector(".sidebar-folders");

            if (incomingFolders) {
                folderList.innerHTML = incomingFolders.innerHTML;
                folders.rebindEventHandlers();
                folders.updateActiveHighlight();
            } else {
                console.error("❌ Папки не найдены в ответе");
            }
        } catch (error) {
            console.error("Ошибка загрузки папок:", error);
        }
    },

    rebindEventHandlers() {
        document.querySelectorAll(".folder-row").forEach(row => {
            if (row.dataset.hasChildren === "true") {
                row.addEventListener("click", folders.toggle);
            }
        });
    },

    updateActiveHighlight() {
        const currentPath = window.location.pathname;
        document.querySelectorAll(".folder-tree a.active-folder")
            .forEach(el => el.classList.remove("active-folder"));

        const activeLink = document.querySelector(`.folder-tree a[href="${currentPath}"]`);
        if (activeLink) {
            activeLink.classList.add("active-folder");
            activeLink.scrollIntoView({ block: "center", behavior: "smooth" });
        }
    },

    toggle(event) {
        event.stopPropagation();
        const item = event.currentTarget.closest(".folder-item");
        const children = item.querySelector(".folder-children");
        if (!children) return;

        const expanded = item.classList.toggle("expanded");
        children.classList.toggle("hidden", !expanded);
    }
};

