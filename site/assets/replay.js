// The last run of a workflow, on the page that shows it: one step at a time beside what the
// run printed, and a replay of the run in which the steps come one after the other as they
// did. Without this script the page holds every step and every line, in order.
// The text of a line is never changed: a line is shown, hidden or dimmed, nothing else.
(function () {
  var CAP = 650, FLOOR = 38, DWELL = 1900; // waits of the run, shortened; the pause after a step
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Two runs on one page (the last one, and the last one made for a tag): a switch chooses
  // which is shown. Without this script both stand on the page, one after the other.
  [].forEach.call(document.querySelectorAll("[data-run-switch]"), function (choice) {
    var buttons = [].slice.call(choice.querySelectorAll("[data-run-view]"));
    var views = [].slice.call(choice.parentNode.querySelectorAll("[data-run-view-of]"));
    if (buttons.length < 2 || buttons.length !== views.length) return;
    function choose(ids) {
      buttons.forEach(function (button) {
        button.setAttribute("aria-pressed", button.getAttribute("data-run-view") === ids ? "true" : "false");
      });
      views.forEach(function (view) {
        var on = view.getAttribute("data-run-view-of") === ids, run = view.querySelector("[data-run]");
        view.hidden = !on;
        if (run) run.dispatchEvent(new CustomEvent(on ? "run:shown" : "run:hidden"));
      });
    }
    buttons.forEach(function (button) {
      button.addEventListener("click", function () { choose(button.getAttribute("data-run-view")); });
    });
    choice.hidden = false;
    // a link to a step or a line of the second run opens the page on that run
    var second = buttons[1].getAttribute("data-run-view");
    choose(second && location.hash.indexOf("#" + second) === 0 ? second : buttons[0].getAttribute("data-run-view"));
    window.addEventListener("hashchange", function () {
      if (second && location.hash.indexOf("#" + second + "run-") === 0) choose(second);
    });
  });

  [].forEach.call(document.querySelectorAll("[data-run]"), function (run) {
    var ids = run.getAttribute("data-run") || ""; // what the ids of this run's steps and lines begin with
    var tabs = [].slice.call(run.querySelectorAll(".run-tab")), panels = [].slice.call(run.querySelectorAll(".run-panel"));
    var lines = [].slice.call(run.querySelectorAll(".tl")), pre = run.querySelector("pre.transcript");
    var play = run.querySelector("[data-run-play]"), label = run.querySelector("[data-run-play-label]");
    var clock = run.querySelector("[data-run-clock]"), strip = run.querySelector(".run-tabs");
    var tools = run.querySelector(".run-term-tools"), bar = run.querySelector("[data-run-progress]");
    var stage = run.querySelector(".run-stage");
    if (!tabs.length || tabs.length !== panels.length) return;
    var stepOf = lines.map(function (line) { return Math.min(panels.length - 1, +line.getAttribute("data-step")); });
    var time = lines.map(function (line) { return +line.getAttribute("data-t"); });
    var end = lines.length ? lines[lines.length - 1].getAttribute("data-clock") : "";
    var current = 0, at = 0, timer = null;
    run.classList.add("is-live");
    if (play && lines.length) play.hidden = false;

    function first(step) { return stepOf.indexOf(step); }
    function toStep() { // the lines of the step that is shown, at the top of their window
      var n = first(current);
      if (pre && n >= 0) pre.scrollTop = Math.max(0, lines[n].offsetTop - 10);
    }
    function tell(n) { // how far the replay is; at rest, how long the run took
      if (clock) clock.textContent = n && lines.length ? lines[n - 1].getAttribute("data-clock") + " / " + end : end;
      if (bar) bar.style.transform = "scaleX(" + (lines.length ? n / lines.length : 0) + ")";
    }
    function cursor(n) { // the line after which the next one will come, while the run is replayed
      lines.forEach(function (line, i) { line.classList.toggle("is-last", i === n); });
    }
    function show(step, follow) {
      current = Math.max(0, Math.min(panels.length - 1, step));
      tabs.forEach(function (tab, n) {
        if (n === current) tab.setAttribute("aria-current", "step"); else tab.removeAttribute("aria-current");
        tab.classList.toggle("is-ahead", n > current); // drawn only while the run is replayed
      });
      panels.forEach(function (panel, n) {
        panel.classList.toggle("is-shown", n === current);
        panel.setAttribute("aria-hidden", n === current ? "false" : "true");
      });
      lines.forEach(function (line, n) { line.classList.toggle("is-on", stepOf[n] === current); });
      if (strip && strip.scrollWidth > strip.clientWidth) {
        var tab = tabs[current].parentNode;
        strip.scrollLeft = tab.offsetLeft - (strip.clientWidth - tab.offsetWidth) / 2;
      }
      if (follow !== false) toStep();
    }
    function rest() { // the replay is over or was ended: every line is on the page again
      clearTimeout(timer);
      timer = null;
      run.classList.remove("is-playing");
      if (label) label.textContent = "Replay";
      lines.forEach(function (line) { line.hidden = false; });
      cursor(-1);
      at = 0;
      tell(0);
    }
    function tick() {
      if (at >= lines.length) {
        rest();
        show(panels.length - 1, false);
        if (pre) pre.scrollTop = pre.scrollHeight;
        return;
      }
      if (stepOf[at] !== current) show(stepOf[at], false);
      lines[at].hidden = false;
      cursor(at);
      pre.scrollTop = pre.scrollHeight;
      tell(at + 1);
      var wait = DWELL;
      if (at + 1 < lines.length) {
        wait = stepOf[at + 1] !== stepOf[at] ? DWELL : Math.max(FLOOR, Math.min(CAP, (time[at + 1] - time[at]) * 1000));
      }
      at += 1;
      timer = setTimeout(tick, wait);
    }
    function start() {
      lines.forEach(function (line) { line.hidden = true; });
      at = 0;
      show(lines.length ? stepOf[0] : 0, false);
      run.classList.add("is-playing");
      if (label) label.textContent = "Skip";
      tick();
    }
    function choose(step) { // the reader takes over: the replay ends, everything is there
      rest();
      show(step);
    }

    // One button: replay the run; while it plays, go straight to its end. There is nothing to
    // pause for: the end is the page as it is, with every step and every line.
    if (play) play.addEventListener("click", function () {
      if (run.classList.contains("is-playing")) choose(panels.length - 1); else start();
    });
    tabs.forEach(function (tab, n) {
      tab.addEventListener("click", function (event) {
        event.preventDefault();
        choose(n);
      });
      tab.addEventListener("keydown", function (event) {
        var to = event.key === "ArrowRight" ? n + 1 : event.key === "ArrowLeft" ? n - 1 : -1;
        if (to < 0 || to >= tabs.length) return;
        event.preventDefault();
        choose(to);
        tabs[to].focus();
      });
    });
    var stepLink = "#" + ids + "run-step-";
    [].forEach.call(run.querySelectorAll('a[href^="' + stepLink + '"]:not(.run-tab)'), function (link) {
      link.addEventListener("click", function (event) {
        var n = +link.getAttribute("href").slice(stepLink.length) - 1;
        if (!(n >= 0 && n < panels.length)) return;
        event.preventDefault();
        choose(n);
        if (stage) stage.scrollIntoView({ block: "nearest" });
      });
    });

    // How the lines are laid out is the reader's choice: wrapped or each on one line, in the
    // page or over the whole window. And the lines as the run printed them, for the clipboard:
    // the times are drawn and are no text.
    if (tools) {
      tools.hidden = false;
      var wrap = tools.querySelector("[data-run-wrap]"), full = tools.querySelector("[data-run-full]");
      var copy = tools.querySelector("[data-run-copy]");
      if (wrap) wrap.addEventListener("click", function () {
        var on = wrap.getAttribute("aria-pressed") !== "true";
        wrap.setAttribute("aria-pressed", on ? "true" : "false");
        run.classList.toggle("no-wrap", !on);
        if (!timer) toStep();
      });
      function whole(on) {
        run.classList.toggle("is-full", on);
        document.documentElement.classList.toggle("run-has-full", on);
        full.setAttribute("aria-pressed", on ? "true" : "false");
        full.setAttribute("aria-label", on ? "Leave full screen" : "Full screen");
        full.title = on ? "Leave full screen (Esc)" : "Full screen";
        if (!on && stage) stage.scrollIntoView({ block: "nearest" });
        if (timer) pre.scrollTop = pre.scrollHeight; else toStep();
      }
      if (full) {
        full.addEventListener("click", function () { whole(!run.classList.contains("is-full")); });
        document.addEventListener("keydown", function (event) {
          if (event.key === "Escape" && run.classList.contains("is-full")) whole(false);
        });
      }
      if (copy && !(navigator.clipboard && navigator.clipboard.writeText)) copy.hidden = true;
      if (copy) copy.addEventListener("click", function () {
        navigator.clipboard.writeText(lines.map(function (line) { return line.textContent; }).join("")).then(function () {
          copy.classList.add("is-done");
          copy.title = "Copied";
          setTimeout(function () { copy.classList.remove("is-done"); copy.title = copy.getAttribute("aria-label"); }, 1600);
        }, function () { copy.hidden = true; });
      });
    }

    // A line can be pointed at: its time is its link. The page opens on the step the line is in.
    function point(n, keep) {
      if (!(n >= 0 && n < lines.length)) return false;
      choose(stepOf[n]);
      lines.forEach(function (line, i) { line.classList.toggle("is-marked", i === n); });
      pre.scrollTop = Math.max(0, lines[n].offsetTop - pre.clientHeight / 3);
      if (keep && window.history && history.replaceState) history.replaceState(null, "", "#" + lines[n].id);
      return true;
    }
    lines.forEach(function (line, n) {
      var at = line.querySelector(".tl-at");
      if (at) at.addEventListener("click", function (event) {
        event.preventDefault();
        point(n, true);
      });
    });
    function pointed() { // a link to a line was followed: the stage in view, the line in its window
      var found = new RegExp("^#" + ids + "run-line-(\\d+)$").exec(location.hash), n = found ? +found[1] - 1 : -1;
      if (!point(n, false)) return false;
      function settle() {
        if (stage) stage.scrollIntoView({ block: "start" });
        pre.scrollTop = Math.max(0, lines[n].offsetTop - pre.clientHeight / 3);
      }
      settle();
      if (document.readyState !== "complete") window.addEventListener("load", settle); // after the browser's own jump
      return true;
    }
    window.addEventListener("hashchange", pointed);

    var asked = new RegExp("^#" + ids + "run-step-(\\d+)$").exec(location.hash);
    // shown again after the other run was: its lines where they belong; put away: no replay goes on unseen
    run.addEventListener("run:shown", function () { toStep(); });
    run.addEventListener("run:hidden", function () { if (timer) choose(current); });
    tell(0);
    if (!pointed()) show(asked ? +asked[1] - 1 : 0);
    // What moves on this page moves from here on: setting the page up is not shown as a change.
    var frame = window.requestAnimationFrame || function (f) { setTimeout(f, 30); };
    frame(function () { frame(function () { run.classList.add("is-ready"); }); });
    // The run plays once by itself when the page opens on it. Not for a reader who asked for
    // less motion, who followed a link to another part of the page, or who has left the tab.
    if (!still && !location.hash && lines.length && !document.hidden && !(run.closest && run.closest("[hidden]"))) {
      var top = run.getBoundingClientRect().top;
      if (top < window.innerHeight * 0.7) timer = setTimeout(function () { timer = null; start(); }, 900);
    }
  });

  // What stands beside the text for a part of the page appears once the reader is past that part.
  [].forEach.call(document.querySelectorAll("[data-show-after]"), function (box) {
    var part = document.getElementById(box.getAttribute("data-show-after"));
    if (!part || !("IntersectionObserver" in window)) return;
    box.hidden = true;
    new IntersectionObserver(function (entries) {
      var entry = entries[entries.length - 1];
      box.hidden = entry.isIntersecting || entry.boundingClientRect.top > 0;
    }).observe(part);
  });
})();
