document.addEventListener("DOMContentLoaded", function () {
  // Scrape form loading state
  const form = document.getElementById("scrape-form");
  if (form) {
    form.addEventListener("submit", function () {
      const btn = document.getElementById("scrape-btn");
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span>Scraping...';
    });
  }

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".tab-btn").forEach(function (b) { b.classList.remove("active"); });
      document.querySelectorAll(".tab-panel").forEach(function (p) { p.classList.remove("active"); });
      btn.classList.add("active");
      var panel = document.getElementById(btn.dataset.tab);
      if (panel) panel.classList.add("active");
    });
  });

  // Image upload: click, drag-drop, preview
  var uploadArea = document.getElementById("uploadArea");
  var imageFile = document.getElementById("imageFile");
  var uploadPreview = document.getElementById("uploadPreview");
  var uploadPrompt = document.getElementById("uploadPrompt");

  if (uploadArea && imageFile) {
    uploadArea.addEventListener("click", function () { imageFile.click(); });

    imageFile.addEventListener("change", function () {
      if (imageFile.files && imageFile.files[0]) {
        showPreview(imageFile.files[0]);
      }
    });

    uploadArea.addEventListener("dragover", function (e) {
      e.preventDefault();
      uploadArea.classList.add("dragover");
    });

    uploadArea.addEventListener("dragleave", function () {
      uploadArea.classList.remove("dragover");
    });

    uploadArea.addEventListener("drop", function (e) {
      e.preventDefault();
      uploadArea.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        imageFile.files = e.dataTransfer.files;
        showPreview(e.dataTransfer.files[0]);
      }
    });

    function showPreview(file) {
      var reader = new FileReader();
      reader.onload = function (e) {
        uploadPreview.src = e.target.result;
        uploadPreview.hidden = false;
        uploadPrompt.hidden = true;
      };
      reader.readAsDataURL(file);
    }
  }

  // Upload form loading state
  var uploadForm = document.getElementById("upload-form");
  if (uploadForm) {
    uploadForm.addEventListener("submit", function () {
      var btn = document.getElementById("upload-btn");
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span>Reading poster...';
    });
  }

  // Pill-toggle active state
  document.querySelectorAll(".pill-toggle").forEach(function (label) {
    label.addEventListener("click", function () {
      var cb = label.querySelector("input[type=checkbox]");
      // Toggle happens naturally; we sync the class after
      setTimeout(function () {
        if (cb.checked) {
          label.classList.add("active");
        } else {
          label.classList.remove("active");
        }
        applyFilters();
      }, 0);
    });
  });

  // Artist filtering
  const cards = document.querySelectorAll(".artist-card");
  const countEl = document.getElementById("artist-count");

  function applyFilters() {
    const selectedGenres = Array.from(document.querySelectorAll(".filter-genre:checked"))
      .map(function (cb) { return cb.value; });
    const selectedTimbres = Array.from(document.querySelectorAll(".filter-timbre:checked"))
      .map(function (cb) { return cb.value; });

    var visible = 0;
    cards.forEach(function (card) {
      var cardGenres = (card.dataset.genres || "").split(",").filter(Boolean);
      var cardTimbre = (card.dataset.timbre || "").split(",").filter(Boolean);

      var genreMatch =
        selectedGenres.length === 0 ||
        selectedGenres.some(function (g) { return cardGenres.includes(g); });
      var timbreMatch =
        selectedTimbres.length === 0 ||
        selectedTimbres.some(function (t) { return cardTimbre.includes(t); });

      if (genreMatch && timbreMatch) {
        card.style.display = "";
        visible++;
      } else {
        card.style.display = "none";
      }
    });

    if (countEl) {
      countEl.textContent = "(" + visible + ")";
    }
  }
});
