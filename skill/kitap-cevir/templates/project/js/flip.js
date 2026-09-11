const Flip = (function () {
  const DRAG_THRESHOLD = 90;
  const CORNER_ZONE = 100;
  const EDGE_ZONE = 80;
  const MAX_TILT_DEG = 16;
  const SPREAD_MAX_TILT_DEG = 22;
  const MAX_TRANSLATE_Z_PX = 28;

  let navHandlers = null;
  let dragState = null;

  function prefersReduced() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function isSpread() {
    return document.getElementById("book").classList.contains("spread");
  }

  function clearDragTilt() {
    document.querySelectorAll(".sheet.drag-tilt-next, .sheet.drag-tilt-prev, .sheet.drag-curl").forEach(function (el) {
      el.classList.remove("drag-tilt-next", "drag-tilt-prev", "drag-curl");
      el.style.transform = "";
    });
    const desk = document.querySelector(".desk");
    if (desk) desk.classList.remove("dragging");
  }

  function isInCornerZone(clientX, clientY) {
    const book = document.getElementById("book");
    const rect = book.getBoundingClientRect();
    const nearRight = clientX > rect.right - CORNER_ZONE;
    const nearLeft = clientX < rect.left + CORNER_ZONE;
    const nearBottom = clientY > rect.bottom - CORNER_ZONE * 1.2;
    const nearEdge = nearRight || nearLeft;
    if (isSpread()) return (nearRight || nearLeft) && clientY > rect.top && clientY < rect.bottom;
    return (nearEdge && nearBottom) || (nearRight && clientY > rect.top && clientY < rect.bottom);
  }

  function isNearEdge(clientX, forNext) {
    const book = document.getElementById("book");
    const rect = book.getBoundingClientRect();
    if (forNext) return clientX > rect.right - EDGE_ZONE;
    return clientX < rect.left + EDGE_ZONE;
  }

  function applyDragTilt(deltaX) {
    const sheet = isSpread()
      ? (deltaX < 0 ? document.getElementById("sheet-right") : document.getElementById("sheet-left"))
      : (document.getElementById("sheet-left").hidden ? document.getElementById("sheet-right") : document.getElementById("sheet-left"));
    if (!sheet || sheet.hidden) return;
    const absDelta = Math.min(Math.abs(deltaX), 140);
    const progress = absDelta / 140;
    const maxTilt = isSpread() ? SPREAD_MAX_TILT_DEG : MAX_TILT_DEG;
    const tilt = progress * maxTilt;
    const z = progress * MAX_TRANSLATE_Z_PX;
    if (deltaX < 0) {
      sheet.style.transform = "rotateY(" + (-tilt) + "deg) translateZ(" + z + "px)";
      sheet.classList.add("drag-curl");
    } else {
      sheet.style.transform = "rotateY(" + tilt + "deg) translateZ(" + z + "px)";
      sheet.classList.add("drag-curl");
    }
  }

  function onPointerDown(event) {
    const isTouch = event.type === "touchstart";
    const clientX = isTouch ? event.touches[0].clientX : event.clientX;
    const clientY = isTouch ? event.touches[0].clientY : event.clientY;
    const book = document.getElementById("book");
    if (!book.contains(event.target) && !event.target.closest(".turn")) return;
    if (event.target.closest("button, a, .word, .sentence")) return;
    const rect = book.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const wantsNext = clientX > centerX;
    const inZone = isInCornerZone(clientX, clientY) || isNearEdge(clientX, wantsNext) || event.target.closest(".sheet");
    if (!inZone) return;
    dragState = { startX: clientX, startY: clientY, currentX: clientX, active: false };
  }

  function onPointerMove(event) {
    if (!dragState) return;
    const isTouch = event.type === "touchmove";
    const clientX = isTouch ? event.touches[0].clientX : event.clientX;
    dragState.currentX = clientX;
    const deltaX = clientX - dragState.startX;
    const absDelta = Math.abs(deltaX);
    if (absDelta > 12 && !dragState.active) {
      dragState.active = true;
      const desk = document.querySelector(".desk");
      if (desk) desk.classList.add("dragging");
    }
    if (dragState.active) {
      if (isTouch) event.preventDefault();
      applyDragTilt(deltaX);
    }
  }

  function onPointerUp(event) {
    if (!dragState) return;
    const isTouch = event.type === "touchend";
    const clientX = isTouch ? (event.changedTouches[0] ? event.changedTouches[0].clientX : dragState.currentX) : event.clientX;
    const deltaX = clientX - dragState.startX;
    const wasActive = dragState.active;
    const wantsNext = deltaX < -DRAG_THRESHOLD;
    const wantsPrev = deltaX > DRAG_THRESHOLD;
    clearDragTilt();
    dragState = null;
    if (!wasActive) return;
    if (wantsNext && navHandlers) navHandlers.onNext();
    else if (wantsPrev && navHandlers) navHandlers.onPrev();
  }

  function bindDrag(handlers) {
    navHandlers = handlers;
    const book = document.getElementById("book");
    const desk = document.querySelector(".desk");
    const opts = { passive: true };
    book.addEventListener("mousedown", onPointerDown, opts);
    book.addEventListener("touchstart", onPointerDown, { passive: true });
    window.addEventListener("mousemove", onPointerMove, { passive: false });
    window.addEventListener("touchmove", onPointerMove, { passive: false });
    window.addEventListener("mouseup", onPointerUp, opts);
    window.addEventListener("touchend", onPointerUp, opts);
    book.addEventListener("mouseleave", function () {
      if (dragState && !dragState.active) { dragState = null; clearDragTilt(); }
    });
    if (desk) desk.addEventListener("selectstart", function (e) { if (dragState && dragState.active) e.preventDefault(); });
  }

  function init(handlers) { bindDrag(handlers); }

  return { init: init, prefersReduced: prefersReduced };
})();