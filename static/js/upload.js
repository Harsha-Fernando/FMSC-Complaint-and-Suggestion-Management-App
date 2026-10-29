/* Upload feedback (Section 12: "file uploads should include validation and progress feedback").
   Works as progressive enhancement: without JavaScript the form still submits normally. */
(function () {
  "use strict";
  const gettext = window.gettext || (text => text);

  function formatSize(bytes) {
    if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function listFiles(input) {
    var box = input.closest(".upload-box");
    if (!box) return true;
    var list = box.querySelector(".upload-list");
    if (!list) {
      list = document.createElement("ul");
      list.className = "upload-list";
      list.setAttribute("aria-live", "polite");
      box.appendChild(list);
    }
    list.innerHTML = "";
    const caption = box.querySelector('[data-file-caption]');
    if (caption) caption.textContent = input.files.length === 1 ? input.files[0].name : input.files.length ? interpolate(gettext("Files selected: %(count)s"), {count: input.files.length}, true) : gettext("No files chosen");
    var maxBytes = parseFloat(input.dataset.maxMb || "0") * 1024 * 1024;
    var ok = true;
    Array.prototype.forEach.call(input.files, function (file) {
      var li = document.createElement("li");
      var name = document.createElement("span");
      name.textContent = file.name;
      var size = document.createElement("span");
      if (maxBytes && file.size > maxBytes) {
        size.className = "bad";
        size.textContent = interpolate(gettext("%(size)s (too large, limit %(limit)s MB)"), {size:formatSize(file.size), limit:input.dataset.maxMb}, true);
        ok = false;
      } else {
        size.textContent = formatSize(file.size);
      }
      li.appendChild(name);
      li.appendChild(size);
      list.appendChild(li);
    });
    input.setCustomValidity(ok ? "" : gettext("One or more files are larger than the limit."));
    return ok;
  }

  document.querySelectorAll("input[type=file][data-max-mb]").forEach(function (input) {
    input.addEventListener("change", function () { listFiles(input); });
  });

  // Show the resolution note only when the authority chooses "Solved" (Wireframe 7).
  document.querySelectorAll("select[name=new_status]").forEach(function (select) {
    var note = document.getElementById("id_resolution_note");
    var box = note && note.closest(".field");
    if (!box) return;
    function update() {
      var solving = select.value === "solved";
      box.hidden = !solving && !box.classList.contains("has-error");
    }
    select.addEventListener("change", update);
    update();
  });

  document.querySelectorAll("form[data-upload]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      var inputs = form.querySelectorAll("input[type=file]");
      var hasFiles = Array.prototype.some.call(inputs, function (i) { return i.files && i.files.length; });
      if (!hasFiles || !window.FormData || !window.XMLHttpRequest) return;

      for (var i = 0; i < inputs.length; i++) {
        if (!listFiles(inputs[i])) { event.preventDefault(); inputs[i].reportValidity(); return; }
      }

      event.preventDefault();
      var progress = form.querySelector(".progress");
      var fill = form.querySelector(".progress-fill");
      var text = form.querySelector(".progress-text");
      var button = form.querySelector("button[type=submit]");
      if (button) button.disabled = true;
      if (progress) progress.classList.add("visible");

      var xhr = new XMLHttpRequest();
      xhr.open(form.method || "POST", form.action || window.location.href);
      xhr.upload.addEventListener("progress", function (e) {
        if (!e.lengthComputable) return;
        var pct = Math.round((e.loaded / e.total) * 100);
        if (fill) fill.style.width = pct + "%";
        if (text) text.textContent = pct < 100
          ? interpolate(gettext("Uploading %(progress)s (%(loaded)s of %(total)s)"), {progress:pct+"%", loaded:formatSize(e.loaded), total:formatSize(e.total)}, true)
          : gettext("Upload finished. Saving the case…");
      });
      xhr.addEventListener("load", function () {
        // The request already followed the server's redirect, and that page carries the
        // one-time confirmation message. Show it as-is instead of loading the page again,
        // which would lose the message. Validation errors arrive the same way.
        var finalUrl = xhr.responseURL || "";
        var postedTo = (form.action || window.location.href).split("#")[0];
        if (finalUrl && finalUrl.split("#")[0] !== postedTo && window.history.replaceState) {
          window.history.replaceState(null, "", finalUrl);
        }
        document.open();
        document.write(xhr.responseText);
        document.close();
      });
      xhr.addEventListener("error", function () {
        if (button) button.disabled = false;
        if (text) text.textContent = gettext("The upload stopped. Check your connection and submit again.");
      });
      xhr.send(new FormData(form));
    });
  });
})();
