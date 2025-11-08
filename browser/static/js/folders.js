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
                console.error("Папки не найдены в ответе");
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
        
        if (progressBar.taskId) {
            progressBar.blockNavigation();
        }
    },

    updateActiveHighlight() {
        const currentPath = window.location.pathname;
        document.querySelectorAll(".folder-tree a.active-folder")
            .forEach(el => el.classList.remove("active-folder"));

        const normalizePath = (path) => {
            try {
                return decodeURIComponent(path.replace(/^\/+/, ''));
            } catch (e) {
                return path.replace(/^\/+/, '');
            }
        };
        
        const normalizedCurrent = normalizePath(currentPath);
        let activeLink = document.querySelector(`.folder-tree a[href="${currentPath}"]`);
        
        if (!activeLink) {
            const allLinks = document.querySelectorAll(".folder-tree a");
            for (const link of allLinks) {
                try {
                    let linkPath;
                    if (link.href.startsWith('http://') || link.href.startsWith('https://')) {
                        linkPath = new URL(link.href).pathname;
                    } else {
                        linkPath = new URL(link.href, window.location.origin).pathname;
                    }
                    
                    if (normalizePath(linkPath) === normalizedCurrent) {
                        activeLink = link;
                        break;
                    }
                } catch (e) {
                    const href = link.getAttribute("href");
                    if (href && normalizePath(href) === normalizedCurrent) {
                        activeLink = link;
                        break;
                    }
                }
            }
        }
        
        if (activeLink) {
            activeLink.classList.add("active-folder");
            activeLink.scrollIntoView({ block: "center", behavior: "smooth" });
        }
    },

    toggle(event) {
        event.stopPropagation();
        
        if (progressBar.taskId) {
            toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
            return;
        }
        
        const item = event.currentTarget.closest(".folder-item");
        const children = item.querySelector(".folder-children");
        if (!children) return;

        const expanded = item.classList.toggle("expanded");
        children.classList.toggle("hidden", !expanded);
    }
};

