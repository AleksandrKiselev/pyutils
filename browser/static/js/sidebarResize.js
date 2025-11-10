const sidebarResize = {
    STORAGE_KEY: "sidebarWidth",
    MIN_WIDTH: 150,
    MAX_WIDTH: 500,
    DEFAULT_WIDTH: 210,
    
    async init() {
        await this.calculateMinWidth();
        const savedWidth = this.getSavedWidth();
        this.setWidth(savedWidth);
        this.createResizeHandle();
        this.setupResizeHandlers();
    },
    
    calculateMinWidth() {
        return new Promise((resolve) => {
            const searchSortBar = document.querySelector(".search-sort-bar");
            if (!searchSortBar) {
                resolve();
                return;
            }
            
            const sidebar = DOM.sidebar;
            if (!sidebar) {
                resolve();
                return;
            }
            
            const wasVisible = document.body.classList.contains("sidebar-visible");
            
            if (!wasVisible) {
                document.body.classList.add("sidebar-visible");
            }
            
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    const minWidth = searchSortBar.scrollWidth + 
                                  (parseInt(getComputedStyle(sidebar).paddingLeft, 10) || 0) + 
                                  (parseInt(getComputedStyle(sidebar).paddingRight, 10) || 0) + 10;
                    this.MIN_WIDTH = Math.max(150, Math.ceil(minWidth));
                    
                    if (!wasVisible) {
                        document.body.classList.remove("sidebar-visible");
                    }
                    
                    resolve();
                });
            });
        });
    },
    
    getSavedWidth() {
        const saved = localStorage.getItem(this.STORAGE_KEY);
        if (saved) {
            const width = parseInt(saved, 10);
            if (width >= this.MIN_WIDTH && width <= this.MAX_WIDTH) {
                return width;
            }
        }
        return this.DEFAULT_WIDTH;
    },
    
    saveWidth(width) {
        localStorage.setItem(this.STORAGE_KEY, width.toString());
    },
    
    setWidth(width) {
        const clampedWidth = Math.max(this.MIN_WIDTH, Math.min(this.MAX_WIDTH, width));
        document.documentElement.style.setProperty("--sidebar-width", `${clampedWidth}px`);
        this.saveWidth(clampedWidth);
    },
    
    createResizeHandle() {
        if (document.getElementById("sidebar-resize-handle")) {
            return;
        }
        
        const sidebar = DOM.sidebar;
        if (!sidebar) return;
        
        const handle = document.createElement("div");
        handle.id = "sidebar-resize-handle";
        handle.className = "sidebar-resize-handle";
        handle.title = "Перетащите для изменения ширины";
        sidebar.appendChild(handle);
    },
    
    setupResizeHandlers() {
        const handle = document.getElementById("sidebar-resize-handle");
        if (!handle) return;
        
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;
        
        handle.addEventListener("mousedown", (e) => {
            isResizing = true;
            startX = e.clientX;
            startWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--sidebar-width"), 10);
            
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
            
            e.preventDefault();
        });
        
        document.addEventListener("mousemove", (e) => {
            if (!isResizing) return;
            
            const diff = e.clientX - startX;
            const newWidth = startWidth + diff;
            this.setWidth(newWidth);
            
            e.preventDefault();
        });
        
        document.addEventListener("mouseup", () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = "";
                document.body.style.userSelect = "";
            }
        });
    }
};

