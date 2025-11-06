const rating = {
    set(event, filename, ratingValue) {
        event.stopPropagation();
        const img = state.currentImages.find(i => i.filename === filename);
        if (!img) return;

        const currentRating = img.metadata.rating || 0;
        const newRating = currentRating === ratingValue ? 0 : ratingValue;

        img.metadata.rating = newRating;

        rating.updateStars(null, filename, newRating);

        utils.apiRequest("/update_metadata", {
            body: JSON.stringify({ filename, rating: newRating })
        }).catch(error => {
            console.error("Ошибка сохранения рейтинга:", error);
        });
    },

    updateStars(event, filename, ratingValue) {
        if (event) event.stopPropagation();
        document.querySelectorAll(`.star[data-filename='${filename}']`).forEach(star => {
            star.textContent = star.dataset.rating <= ratingValue ? STARRED_SYMBOL : UNSTARRED_SYMBOL;
        });
    },

    showStars(event) {
        event.currentTarget.querySelector(".image-rating").style.opacity = "1";
    },

    hideStars(event) {
        event.currentTarget.querySelector(".image-rating").style.opacity = "0";
    }
};

