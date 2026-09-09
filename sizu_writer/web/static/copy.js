// Progressive browser helpers for copying, form feedback and textarea sizing.

(function () {
  "use strict";

  function textOf(element) {
    return element.value !== undefined ? element.value : element.textContent;
  }

  function notify(button, message) {
    var note = button.nextElementSibling;
    if (!note || !note.classList.contains("copied")) {
      note = document.createElement("span");
      note.className = "copied";
      button.parentNode.insertBefore(note, button.nextSibling);
    }
    note.textContent = message;
    window.setTimeout(function () { note.textContent = ""; }, 2000);
  }

  function fallback(button, element) {
    // Keep the text selected so that it can be copied by hand.
    if (element.select) {
      element.select();
    } else {
      var range = document.createRange();
      range.selectNodeContents(element);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
    }
    try {
      if (document.execCommand("copy")) {
        notify(button, "Copied");
        return;
      }
    } catch (error) {
      // Fall through to the manual instruction below.
    }
    notify(button, "Could not copy. Select the text and copy it by hand.");
  }

  function updateCharacterCount(field) {
    var counterId = field.getAttribute("data-character-count-target");
    if (!counterId) {
      return;
    }

    var counter = document.getElementById(counterId);
    if (!counter) {
      return;
    }

    counter.textContent = field.value.length + " / " + field.maxLength;
  }

  function watchCharacterCount(field) {
    updateCharacterCount(field);
    field.addEventListener("input", function () {
      updateCharacterCount(field);
    });
  }

  function autoGrow(element) {
    element.style.height = "auto";
    element.style.height = element.scrollHeight + "px";
    element.style.overflowY = "hidden";
  }

  function preserveSubmitValue(form, button) {
    if (!button || !button.name) {
      return;
    }

    var hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = button.name;
    hidden.value = button.value;
    hidden.setAttribute("data-submitted-button", "");
    form.appendChild(hidden);
  }

  function showWorking(button) {
    if (!button) {
      return;
    }

    var note = document.createElement("span");
    note.className = "meta";
    note.setAttribute("aria-live", "polite");
    note.textContent = "Generating...";
    button.parentNode.insertBefore(note, button.nextSibling);
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("button");
    if (!button) {
      return;
    }

    var clearId = button.getAttribute("data-clear-target");
    if (clearId) {
      var field = document.getElementById(clearId);
      field.value = "";
      field.focus();
      updateCharacterCount(field);
      return;
    }

    var copyId = button.getAttribute("data-copy-target");
    if (!copyId) {
      return;
    }

    var element = document.getElementById(copyId);
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(textOf(element)).then(function () {
        notify(button, "Copied");
      }, function () {
        fallback(button, element);
      });
    } else {
      fallback(button, element);
    }
  });

  document.addEventListener("submit", function (event) {
    var form = event.target;
    var method = (form.getAttribute("method") || "get").toLowerCase();
    if (method !== "post") {
      return;
    }

    if (form.getAttribute("data-submitting") === "true") {
      event.preventDefault();
      return;
    }

    var submitter = event.submitter;
    if (!submitter) {
      submitter = form.querySelector('button[type="submit"]');
    }

    preserveSubmitValue(form, submitter);
    form.setAttribute("data-submitting", "true");
    form.setAttribute("aria-busy", "true");

    var buttons = form.querySelectorAll('button[type="submit"]');
    for (var i = 0; i < buttons.length; i += 1) {
      buttons[i].disabled = true;
    }

    showWorking(submitter);
  });

  var countedFields = document.querySelectorAll("[data-character-count-target]");
  for (var i = 0; i < countedFields.length; i += 1) {
    watchCharacterCount(countedFields[i]);
  }

  var growingFields = document.querySelectorAll("[data-auto-grow]");
  for (var j = 0; j < growingFields.length; j += 1) {
    autoGrow(growingFields[j]);
  }

  window.addEventListener("resize", function () {
    for (var k = 0; k < growingFields.length; k += 1) {
      autoGrow(growingFields[k]);
    }
  });
})();
