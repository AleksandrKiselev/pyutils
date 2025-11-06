const toast = {
    show(message, prompt = null, duration = 3000) {
        if (!DOM.toast) return;
        
        if (prompt) {
            DOM.toast.innerHTML = `
                <div class="toast-title">${message}</div>
                <div class="toast-prompt">${utils.escapeHTML(prompt)}</div>
            `;
        } else {
            DOM.toast.textContent = message;
        }
        
        DOM.toast.classList.add("visible");
        
        setTimeout(() => {
            toast.hide();
        }, duration);
    },

    hide() {
        if (!DOM.toast) return;
        DOM.toast.classList.remove("visible");
    }
};

