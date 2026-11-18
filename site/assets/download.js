/* A file of a build is handed out after a question. A link with data-download leads to the
   provider's terms; this script shows them in a dialog instead, and the file is fetched only
   when the reader accepts. Nothing about the click is recorded or remembered: the question is
   asked each time. Without this script, or in a browser without <dialog>, the link leads to
   the terms and hands out nothing. Shared by every Sentier dataset site; the words are the
   site's own (site/config.json "download", written into the page by the build). */
(function () {
  "use strict";
  var dialog = document.getElementById("download-terms");
  if (!dialog || typeof dialog.showModal !== "function") return;
  var file = dialog.querySelector("[data-download-file]");
  var size = dialog.querySelector("[data-download-bytes]");
  var accept = dialog.querySelector("[data-download-accept]");
  var away = accept.getAttribute("href");
  var from = null;

  document.addEventListener("click", function (event) {
    var link = event.target.closest ? event.target.closest("a[data-download]") : null;
    // A click with a modifier opens the terms, as the link says; only a plain click asks here.
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    from = link;
    file.textContent = link.getAttribute("data-download-name") || "";
    size.textContent = link.getAttribute("data-download-size") || "";
    accept.setAttribute("href", link.getAttribute("data-download"));
    dialog.showModal();
  });

  // Accepting follows the link to the file; the dialog closes behind it.
  accept.addEventListener("click", function () {
    setTimeout(function () { dialog.close("accepted"); }, 0);
  });
  // A click beside the box is a no.
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) dialog.close("cancel");
  });
  dialog.addEventListener("close", function () {
    accept.setAttribute("href", away);
    if (from) from.focus();
    from = null;
  });
})();
