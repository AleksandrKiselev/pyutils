const bookmarks = {
    STORAGE_KEY: "fullscreenBookmarks",
    
    getAll() {
        const raw = localStorage.getItem(this.STORAGE_KEY);
        if (!raw) return [];
        try {
            return JSON.parse(raw);
        } catch (e) {
            console.warn("Ошибка чтения закладок:", e);
            return [];
        }
    },
    
    save(bookmarksList) {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(bookmarksList));
        } catch (e) {
            console.error("Ошибка сохранения закладок:", e);
        }
    },
    
    add(metadataId, imageData) {
        const all = this.getAll();
        if (all.find(b => b.id === metadataId)) {
            return false;
        }
        
        const imagePath = imageData.image_path || "";
        const pathParts = imagePath.split(/[/\\]/);
        const filename = pathParts.pop() || "";
        const folderPath = pathParts.join("/");
        
        const bookmark = {
            id: metadataId,
            imagePath: imagePath,
            folderPath: folderPath,
            prompt: imageData.prompt || "",
            filename: filename,
            timestamp: Date.now()
        };
        
        all.push(bookmark);
        this.save(all);
        return true;
    },
    
    remove(metadataId) {
        const all = this.getAll();
        const filtered = all.filter(b => b.id !== metadataId);
        if (filtered.length === all.length) {
            return false;
        }
        this.save(filtered);
        return true;
    },
    
    has(metadataId) {
        return this.getAll().some(b => b.id === metadataId);
    },
    
    toggle(metadataId, imageData) {
        if (this.has(metadataId)) {
            this.remove(metadataId);
            return false;
        } else {
            this.add(metadataId, imageData);
            return true;
        }
    },
    
    render() {
        const container = DOM.bookmarksContainer;
        if (!container) return;
        
        const all = this.getAll();
        if (all.length === 0) {
            container.innerHTML = '<div class="bookmarks-empty">Нет закладок</div>';
            return;
        }
        
        container.innerHTML = "";
        all.forEach(bookmark => {
            const item = document.createElement("div");
            item.className = "bookmark-item";
            item.dataset.id = bookmark.id;
            
            const content = document.createElement("div");
            content.className = "bookmark-content";
            content.onclick = () => this.openFromBookmark(bookmark.id);
            
            const filename = document.createElement("div");
            filename.className = "bookmark-filename";
            filename.textContent = bookmark.filename || "Без имени";
            
            const prompt = document.createElement("div");
            prompt.className = "bookmark-prompt";
            const promptPreview = bookmark.prompt 
                ? (bookmark.prompt.length > 50 ? bookmark.prompt.substring(0, 50) + "..." : bookmark.prompt)
                : bookmark.filename;
            prompt.textContent = promptPreview;
            
            content.appendChild(filename);
            content.appendChild(prompt);
            
            const removeBtn = document.createElement("button");
            removeBtn.className = "bookmark-remove";
            removeBtn.title = "Удалить закладку";
            removeBtn.textContent = "✕";
            removeBtn.onclick = (e) => {
                e.stopPropagation();
                this.removeFromList(bookmark.id);
            };
            
            item.appendChild(content);
            item.appendChild(removeBtn);
            container.appendChild(item);
        });
    },
    
    async openFromBookmark(metadataId) {
        const all = this.getAll();
        const bookmark = all.find(b => b.id === metadataId);
        if (!bookmark) {
            toast.show("Закладка не найдена", "");
            return;
        }
        
        const targetFolderPath = bookmark.folderPath || "";
        const currentPath = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
        
        const currentImages = state.currentImages || [];
        let index = currentImages.findIndex(img => img.id === metadataId);
        
        if (index === -1 || currentPath !== targetFolderPath) {
            if (currentPath !== targetFolderPath) {
                if (progressBar && progressBar.taskId) {
                    toast.show("Дождитесь завершения генерации метаданных", "Обработка изображений...");
                    return;
                }
                
                if (DOM.fullscreenContainer && DOM.fullscreenContainer.style.display === "flex") {
                    fullscreen.close();
                }
                
                state.loading = false;
                stateManager.save();
                const newPath = targetFolderPath ? `/${targetFolderPath}` : "/";
                window.history.pushState({ path: newPath }, '', newPath);
                
                try {
                    await folders.load();
                    folders.updateActiveHighlight();
                } catch (error) {
                    console.error("Ошибка переключения папки:", error);
                    toast.show("Ошибка переключения папки", "Не удалось открыть закладку");
                    return;
                }
            }
            
            try {
                const [sort, order] = (state.sortBy || "date-desc").split("-");
                const searchQuery = state.searchQuery || "";
                const path = targetFolderPath ? `/${targetFolderPath}` : "";
                const query = `/images${path}?limit=1000&offset=0&search=${encodeURIComponent(searchQuery)}&sort_by=${sort}&order=${order}`;
                const response = await fetch(query);
                const images = await response.json();
                
                images.forEach(img => {
                    if (img.rating === undefined || img.rating === null) {
                        img.rating = 0;
                    }
                });
                
                const foundIndex = images.findIndex(img => img.id === metadataId);
                
                if (foundIndex === -1) {
                    toast.show("Изображение не найдено", "Закладка может быть устаревшей");
                    this.remove(metadataId);
                    this.render();
                    return;
                }
                
                state.currentImages = images;
                state.offset = images.length;
                index = foundIndex;
                
                if (DOM.gallery) {
                    const startIndex = 0;
                    const cardsHTML = gallery.renderCards(images, startIndex);
                    DOM.gallery.innerHTML = cardsHTML;
                    gallery.loadCheckboxState();
                    images.forEach(img => {
                        const imgMetadataId = img?.id || "";
                        rating.updateStars(null, imgMetadataId, img?.rating || 0);
                    });
                }
            } catch (error) {
                console.error("Ошибка загрузки изображений:", error);
                toast.show("Ошибка загрузки", "Не удалось открыть закладку");
                return;
            }
        }
        
        if (index === -1 || !state.currentImages[index]) {
            console.error("Изображение не найдено в списке", { index, totalImages: state.currentImages.length });
            toast.show("Ошибка открытия", "Изображение не найдено");
            return;
        }
        
        fullscreen.open(index);
    },
    
    removeFromList(metadataId) {
        this.remove(metadataId);
        this.render();
        toast.show("Закладка удалена", "");
    },
    
    toggleFromFullscreen() {
        const data = state.currentImages[state.currentIndex];
        if (!data) return;
        
        const metadataId = data?.id || "";
        if (!metadataId) return;
        
        const [sort] = (state.sortBy || "date-desc").split("-");
        if (sort === "random") {
            toast.show("Закладки недоступны в режиме случайной сортировки", "");
            return;
        }
        
        const isAdded = this.toggle(metadataId, data);
        this.updateFullscreenButton(metadataId);
        this.render();
        
        toast.show(isAdded ? "Закладка добавлена" : "Закладка удалена", "");
    },
    
    updateFullscreenButton(metadataId) {
        const btn = DOM.fullscreenBookmarkBtn;
        if (!btn) return;
        
        const [sort] = (state.sortBy || "date-desc").split("-");
        if (sort === "random") {
            btn.style.display = "none";
            return;
        }
        
        btn.style.display = "";
        const hasBookmark = this.has(metadataId);
        btn.classList.toggle("active", hasBookmark);
        btn.title = hasBookmark ? "Удалить закладку" : "Добавить закладку";
    }
};

