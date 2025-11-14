const rating = {
    set(event, metadataId, ratingValue) {
        event.stopPropagation();
        const img = utils.findImageById(metadataId);
        if (!img) return;

        const currentRating = img.rating || 0;
        const newRating = currentRating === ratingValue ? 0 : ratingValue;

        img.rating = newRating;

        rating.updateStars(null, metadataId, newRating);

        utils.apiRequest("/metadata", {
            method: "POST",
            body: JSON.stringify({ id: metadataId, rating: newRating })
        }).catch(error => {
            console.error("Ошибка сохранения рейтинга:", error);
        });
    },

    updateStars(event, metadataId, ratingValue) {
        if (event) event.stopPropagation();
        document.querySelectorAll(`.star[data-id='${metadataId}']`).forEach(star => {
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

