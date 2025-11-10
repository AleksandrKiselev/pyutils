const bookmarks = {
    _cache: null,
    
    async getAll() {
        if (this._cache !== null) {
            return this._cache;
        }
        try {
            const response = await fetch("/bookmarks");
            const data = await response.json();
            this._cache = Array.isArray(data) ? data : [];
            return this._cache;
        } catch (e) {
            console.warn("Ошибка чтения закладок:", e);
            return [];
        }
    },
    
    _clearCache() {
        this._cache = null;
    },
    
    async add(metadataId, imageData) {
        try {
            const response = await utils.apiRequest("/bookmarks", {
                method: "POST",
                body: JSON.stringify({
                    id: metadataId,
                    sort_by: state.sortBy || "date-desc",
                    search_query: state.searchQuery || ""
                })
            });
            if (response.success) {
                this._clearCache();
                return true;
            }
            return false;
        } catch (e) {
            console.error("Ошибка добавления закладки:", e);
            return false;
        }
    },
    
    async remove(metadataId) {
        try {
            const response = await utils.apiRequest(`/bookmarks/${metadataId}`, {
                method: "DELETE"
            });
            if (response.success) {
                this._clearCache();
                return response.removed || false;
            }
            return false;
        } catch (e) {
            console.error("Ошибка удаления закладки:", e);
            return false;
        }
    },
    
    async has(metadataId) {
        try {
            const response = await fetch(`/bookmarks/${metadataId}/has`);
            const data = await response.json();
            return data.has || false;
        } catch (e) {
            console.warn("Ошибка проверки закладки:", e);
            return false;
        }
    },
    
    async toggle(metadataId, imageData) {
        const hasBookmark = await this.has(metadataId);
        if (hasBookmark) {
            await this.remove(metadataId);
            return false;
        } else {
            await this.add(metadataId, imageData);
            return true;
        }
    },
    
    async render() {
        const container = DOM.bookmarksContainer;
        if (!container) return;
        
        const all = await this.getAll();
        if (all.length === 0) {
            container.innerHTML = '<div class="bookmarks-empty">Нет закладок</div>';
            return;
        }
        
        container.innerHTML = "";
        all.forEach(bookmark => {
            const item = document.createElement("div");
            item.className = "bookmark-item";
            item.dataset.id = bookmark.metadata_id;
            
            const content = document.createElement("div");
            content.className = "bookmark-content";
            content.onclick = () => this.openFromBookmark(bookmark.metadata_id);
            
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
            removeBtn.onclick = async (e) => {
                e.stopPropagation();
                await this.removeFromList(bookmark.metadata_id);
            };
            
            item.appendChild(content);
            item.appendChild(removeBtn);
            container.appendChild(item);
        });
    },
    
    async openFromBookmark(metadataId) {
        const all = await this.getAll();
        const bookmark = all.find(b => b.metadata_id === metadataId);
        if (!bookmark) {
            toast.show("Закладка не найдена", "");
            return;
        }
        
        const targetFolderPath = bookmark.folder_path || "";
        const currentPath = window.location.pathname === "/" ? "" : window.location.pathname.replace(/^\//, "");
        const bookmarkSortBy = bookmark.sort_by || state.sortBy || "date-desc";
        const currentSortBy = state.sortBy || "date-desc";
        const bookmarkSearchQuery = bookmark.search_query || "";
        const currentSearchQuery = state.searchQuery || "";
        
        const currentImages = state.currentImages || [];
        let index = currentImages.findIndex(img => img.id === metadataId);
        
        const needReload = index === -1 || currentPath !== targetFolderPath || bookmarkSortBy !== currentSortBy || bookmarkSearchQuery !== currentSearchQuery;
        
        if (needReload) {
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
            
            if (bookmarkSortBy !== currentSortBy && DOM.sortSelect) {
                state.sortBy = bookmarkSortBy;
                DOM.sortSelect.value = bookmarkSortBy;
            }
            
            if (bookmarkSearchQuery !== currentSearchQuery) {
                state.searchQuery = bookmarkSearchQuery;
                if (DOM.searchBox) {
                    DOM.searchBox.value = bookmarkSearchQuery;
                }
            }
            
            try {
                const [sort, order] = bookmarkSortBy.split("-");
                const path = targetFolderPath ? `/${targetFolderPath}` : "";
                const query = `/images${path}?limit=1000&offset=0&search=${encodeURIComponent(bookmarkSearchQuery)}&sort_by=${sort}&order=${order}`;
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
                    
                    requestAnimationFrame(() => {
                        const container = document.querySelector(`.image-checkbox[data-id="${metadataId}"]`)?.closest(".image-container");
                        if (container) {
                            container.scrollIntoView({ behavior: "smooth", block: "center" });
                        }
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
        
        const container = document.querySelector(`.image-checkbox[data-id="${metadataId}"]`)?.closest(".image-container");
        if (container) {
            container.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        
        fullscreen.open(index);
    },
    
    async removeFromList(metadataId) {
        await this.remove(metadataId);
        await this.render();
        toast.show("Закладка удалена", "");
    },
    
    async toggleFromFullscreen() {
        const data = state.currentImages[state.currentIndex];
        if (!data) return;
        
        const metadataId = data?.id || "";
        if (!metadataId) return;
        
        const [sort] = (state.sortBy || "date-desc").split("-");
        if (sort === "random") {
            toast.show("Закладки недоступны в режиме случайной сортировки", "");
            return;
        }
        
        const isAdded = await this.toggle(metadataId, data);
        await this.updateFullscreenButton(metadataId);
        await this.render();
        
        toast.show(isAdded ? "Закладка добавлена" : "Закладка удалена", "");
    },
    
    async updateFullscreenButton(metadataId) {
        const btn = DOM.fullscreenBookmarkBtn;
        if (!btn) return;
        
        const [sort] = (state.sortBy || "date-desc").split("-");
        if (sort === "random") {
            btn.style.display = "none";
            return;
        }
        
        btn.style.display = "";
        const hasBookmark = await this.has(metadataId);
        btn.classList.toggle("active", hasBookmark);
        btn.title = hasBookmark ? "Удалить закладку" : "Добавить закладку";
    }
};

