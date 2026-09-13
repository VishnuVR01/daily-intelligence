document.addEventListener("DOMContentLoaded", function () {
  // Delegate click listener for Save / Saved toggle buttons
  document.body.addEventListener("click", function (e) {
    const saveBtn = e.target.closest(".save-toggle-btn");
    if (saveBtn) {
      e.preventDefault();
      const articleId = saveBtn.getAttribute("data-article-id");
      const isSaved = saveBtn.classList.contains("is-saved");

      if (isSaved) {
        // Unsave article
        fetch(`/api/articles/${articleId}/save`, { method: "DELETE" })
          .then(res => {
            if (res.ok) {
              saveBtn.classList.remove("is-saved");
              saveBtn.setAttribute("title", "Save for Later");
              saveBtn.innerHTML = '<span class="save-icon">🔖 Save</span>';
            }
          })
          .catch(err => console.error("Error unsaving article:", err));
      } else {
        // Save article
        fetch(`/api/articles/${articleId}/save`, { method: "POST" })
          .then(res => {
            if (res.ok) {
              saveBtn.classList.add("is-saved");
              saveBtn.setAttribute("title", "Remove from Saved");
              saveBtn.innerHTML = '<span class="save-icon">🔖 Saved</span>';
            }
          })
          .catch(err => console.error("Error saving article:", err));
      }
      return;
    }

    // Mark as Read button on Saved Page
    const readBtn = e.target.closest(".mark-read-btn");
    if (readBtn) {
      e.preventDefault();
      const articleId = readBtn.getAttribute("data-article-id");
      fetch(`/api/articles/${articleId}/read`, { method: "POST" })
        .then(res => res.json())
        .then(data => {
          if (data.status === "read") {
            const card = document.getElementById(`saved-card-${articleId}`);
            if (card) {
              card.classList.add("is-read-card");
            }
            const badge = document.getElementById(`read-badge-${articleId}`);
            if (badge) {
              badge.className = "status-badge status-inactive";
              badge.textContent = "Read";
            }
            readBtn.className = "action-btn mark-unread-btn";
            readBtn.textContent = "Mark as Unread";
          }
        })
        .catch(err => console.error("Error marking read:", err));
      return;
    }

    // Mark as Unread button on Saved Page
    const unreadBtn = e.target.closest(".mark-unread-btn");
    if (unreadBtn) {
      e.preventDefault();
      const articleId = unreadBtn.getAttribute("data-article-id");
      fetch(`/api/articles/${articleId}/unread`, { method: "POST" })
        .then(res => res.json())
        .then(data => {
          if (data.status === "unread") {
            const card = document.getElementById(`saved-card-${articleId}`);
            if (card) {
              card.classList.remove("is-read-card");
            }
            const badge = document.getElementById(`read-badge-${articleId}`);
            if (badge) {
              badge.className = "status-badge status-active";
              badge.textContent = "Unread";
            }
            unreadBtn.className = "action-btn mark-read-btn";
            unreadBtn.textContent = "Mark as Read";
          }
        })
        .catch(err => console.error("Error marking unread:", err));
      return;
    }

    // Remove from Saved button on Saved Page
    const removeBtn = e.target.closest(".remove-saved-btn");
    if (removeBtn) {
      e.preventDefault();
      const articleId = removeBtn.getAttribute("data-article-id");
      fetch(`/api/articles/${articleId}/save`, { method: "DELETE" })
        .then(res => {
          if (res.ok) {
            const card = document.getElementById(`saved-card-${articleId}`);
            if (card) {
              card.style.opacity = "0";
              card.style.transform = "scale(0.95)";
              card.style.transition = "all 0.2s ease";
              setTimeout(() => card.remove(), 200);
            }
          }
        })
        .catch(err => console.error("Error removing saved article:", err));
      return;
    }
  });
});
