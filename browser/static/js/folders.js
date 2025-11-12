const folders = {
    async load() {
        if (!DOM.sidebar) return;
        const folderList = DOM.sidebar.querySelector(".sidebar-folders");
        if (!folderList) return;

        try {
            const response = await fetch("/");
            const doc = new DOMParser().parseFromString(await response.text(), "text/html");
            const incomingFolders = doc.querySelector(".sidebar-folders");

            if (incomingFolders) {
                folderList.innerHTML = incomingFolders.innerHTML;
                folders.rebindEventHandlers();
                folders.restoreState();
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

    getFolderPath(item) {
        return item.getAttribute("data-folder-path") || "";
    },

    saveState() {
        const collapsedPaths = new Set();
        document.querySelectorAll(".folder-item.has-children").forEach(item => {
            if (!item.classList.contains("expanded")) {
                const path = folders.getFolderPath(item);
                if (path) {
                    collapsedPaths.add(path);
                }
            }
        });
        localStorage.setItem("folderTreeState", JSON.stringify(Array.from(collapsedPaths)));
    },

    restoreState() {
        const raw = localStorage.getItem("folderTreeState");
        if (!raw) return;

        try {
            const collapsedPaths = new Set(JSON.parse(raw));
            document.querySelectorAll(".folder-item.has-children").forEach(item => {
                const path = folders.getFolderPath(item);
                if (path && collapsedPaths.has(path)) {
                    item.classList.remove("expanded");
                    const children = item.querySelector(".folder-children");
                    if (children) {
                        children.classList.add("hidden");
                    }
                }
            });
        } catch (e) {
            console.warn("Не удалось восстановить состояние дерева:", e);
        }
    },

    updateActiveHighlight() {
        const currentPath = window.location.pathname;
        document.querySelectorAll(".folder-tree a.active-folder")
            .forEach(el => el.classList.remove("active-folder"));

        const normalizePath = (path) => {
            try {
                return decodeURIComponent(path.replace(/^\/+/, ''));
            } catch {
                return path.replace(/^\/+/, '');
            }
        };
        
        const normalizedCurrent = normalizePath(currentPath);
        let activeLink = document.querySelector(`.folder-tree a[href="${currentPath}"]`);
        
        if (!activeLink) {
            document.querySelectorAll(".folder-tree a").forEach(link => {
                try {
                    const linkPath = link.href.startsWith('http') 
                        ? new URL(link.href).pathname 
                        : new URL(link.href, window.location.origin).pathname;
                    if (normalizePath(linkPath) === normalizedCurrent) {
                        activeLink = link;
                    }
                } catch {
                    const href = link.getAttribute("href");
                    if (href && normalizePath(href) === normalizedCurrent) {
                        activeLink = link;
                    }
                }
            });
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
        folders.saveState();
    },

    getFolderPathFromImagePath(imagePath) {
        if (!imagePath) return "";
        const pathParts = imagePath.split("/").filter(p => p);
        if (pathParts.length > 1) {
            pathParts.pop(); // Убираем имя файла
            return pathParts.join("/");
        }
        return "";
    }
};

