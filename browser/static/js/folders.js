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
        
        // Восстанавливаем блокировку навигации, если идет генерация
        if (progressBar.taskId) {
            progressBar.blockNavigation();
        }
    },

    updateActiveHighlight() {
        const currentPath = window.location.pathname;
        document.querySelectorAll(".folder-tree a.active-folder")
            .forEach(el => el.classList.remove("active-folder"));

        // Функция для нормализации пути (декодирование и нормализация)
        const normalizePath = (path) => {
            try {
                // Убираем начальный слэш и декодируем
                return decodeURIComponent(path.replace(/^\/+/, ''));
            } catch (e) {
                return path.replace(/^\/+/, '');
            }
        };
        
        // Нормализуем текущий путь
        const normalizedCurrent = normalizePath(currentPath);
        
        // Ищем активную ссылку - проверяем несколько вариантов
        let activeLink = null;
        
        // Вариант 1: точное совпадение с текущим путем
        activeLink = document.querySelector(`.folder-tree a[href="${currentPath}"]`);
        
        // Вариант 2: если не нашли, проверяем все ссылки
        if (!activeLink) {
            const allLinks = document.querySelectorAll(".folder-tree a");
            for (const link of allLinks) {
                try {
                    // Используем link.href для получения полного URL, затем извлекаем pathname
                    // Это гарантирует правильное кодирование
                    let linkPath;
                    if (link.href.startsWith('http://') || link.href.startsWith('https://')) {
                        const linkUrl = new URL(link.href);
                        linkPath = linkUrl.pathname;
                    } else {
                        // Относительный путь - создаем полный URL
                        const linkUrl = new URL(link.href, window.location.origin);
                        linkPath = linkUrl.pathname;
                    }
                    
                    // Сравниваем нормализованные пути
                    const normalizedLink = normalizePath(linkPath);
                    if (normalizedLink === normalizedCurrent) {
                        activeLink = link;
                        break;
                    }
                } catch (e) {
                    // Если не удалось создать URL, пробуем использовать getAttribute
                    const href = link.getAttribute("href");
                    if (href) {
                        const normalizedHref = normalizePath(href);
                        if (normalizedHref === normalizedCurrent) {
                            activeLink = link;
                            break;
                        }
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
        
        // Блокируем разворачивание папок во время генерации метаданных
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

