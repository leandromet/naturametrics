(function () {
  "use strict";

  // Cloud Run bills for as long as this tab keeps the Reflex WebSocket alive
  // and reconnecting (it force-reconnects every ~5min on the server's request
  // timeout). An idle tab left open all day pins a billed instance with nobody
  // there. After IDLE_MS with no input, navigate away entirely — that's what
  // actually closes the socket and lets the instance scale down — to a static
  // page with no Reflex/socket of its own. See assets/paused.html.
  var IDLE_MS = 10 * 60 * 1000;
  var timer = null;

  // Optional escape hatch: a page can render <div id="idle-guard-marker"
  // data-busy="true"> (reactively bound to server state) to defer pausing
  // while a real background job is running server-side. Absent element or
  // any value other than "true" means "not busy".
  function isBusy() {
    var marker = document.getElementById("idle-guard-marker");
    return !!marker && marker.getAttribute("data-busy") === "true";
  }

  function pause() {
    if (isBusy()) {
      reset();
      return;
    }
    try {
      sessionStorage.setItem("idle_guard_resume_url", window.location.href);
    } catch (e) {
      /* sessionStorage unavailable (private mode etc.) — resume falls back to "/" */
    }
    window.location.href = "/assets/paused.html";
  }

  function reset() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(pause, IDLE_MS);
  }

  [
    "mousemove",
    "mousedown",
    "keydown",
    "touchstart",
    "wheel",
    "scroll",
  ].forEach(function (evt) {
    document.addEventListener(evt, reset, { passive: true, capture: true });
  });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") reset();
  });

  reset();
})();
