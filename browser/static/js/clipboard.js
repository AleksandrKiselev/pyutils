const clipboard = {
    copy(event, text) {
        event.stopPropagation();
        navigator.clipboard.writeText(text).catch(console.error);
    }
};

