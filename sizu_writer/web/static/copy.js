// Copy one target to the clipboard, and nothing else on the page.

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
        notify(button, "コピーしました");
        return;
      }
    } catch (error) {
      // Fall through to the manual instruction below.
    }
    notify(button, "コピーできませんでした。選択してコピーしてください");
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
      return;
    }

    var copyId = button.getAttribute("data-copy-target");
    if (!copyId) {
      return;
    }

    var element = document.getElementById(copyId);
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(textOf(element)).then(function () {
        notify(button, "コピーしました");
      }, function () {
        fallback(button, element);
      });
    } else {
      fallback(button, element);
    }
  });
})();
