(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Lift the loader curtain once the page (and hero photo) are ready.
  const lift = () => document.body.classList.add("loaded");
  window.addEventListener("load", () => setTimeout(lift, 450));
  setTimeout(lift, 2600); // never block on slow images

  // Nav: solid on scroll + mobile drawer.
  const nav = document.querySelector(".nav");
  const onScroll = () => nav && nav.classList.toggle("scrolled", scrollY > 30);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  document.querySelector(".nav-toggle")?.addEventListener("click", () => nav.classList.toggle("open"));

  // Reveal-on-scroll.
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    });
  }, { threshold: 0.14, rootMargin: "0px 0px -6% 0px" });
  document.querySelectorAll("[data-reveal], .clip-reveal, .step").forEach((el) => io.observe(el));

  // Staggered children.
  document.querySelectorAll("[data-stagger]").forEach((group) => {
    [...group.children].forEach((child, i) => {
      child.setAttribute("data-reveal", child.getAttribute("data-reveal") || "");
      child.style.setProperty("--d", `${(i % 6) * 0.09}s`);
      io.observe(child);
    });
  });

  // Hero headline: split into words that rise in sequence.
  document.querySelectorAll("[data-split]").forEach((el) => {
    const html = el.innerHTML.trim().split(/(\s+|<em>.*?<\/em>)/).filter((s) => s.trim());
    el.innerHTML = html.map((w, i) => `<span class="word"><span style="animation-delay:${0.9 + i * 0.08}s">${w}</span></span>`).join(" ");
  });

  // Hero slideshow with Ken Burns zoom.
  const slides = [...document.querySelectorAll(".hero-slide")];
  const dots = [...document.querySelectorAll(".hero-dots i")];
  const capName = document.querySelector("[data-cap-name]");
  const capCity = document.querySelector("[data-cap-city]");
  if (slides.length) {
    let i = 0;
    const show = (n) => {
      slides.forEach((s, k) => s.classList.toggle("active", k === n));
      dots.forEach((d, k) => d.classList.toggle("active", k === n));
      if (capName) capName.textContent = slides[n].dataset.zh || "";
      if (capCity) capCity.textContent = slides[n].dataset.name || "";
    };
    show(0);
    if (slides.length > 1 && !reduce) setInterval(() => show((i = (i + 1) % slides.length)), 6000);
  }

  // Animated counters.
  const fmt = new Intl.NumberFormat("en-US");
  const cio = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      const el = e.target, end = +el.dataset.count, t0 = performance.now(), dur = 2000;
      const tick = (t) => {
        const p = Math.min(1, (t - t0) / dur), eased = 1 - Math.pow(1 - p, 4);
        el.textContent = fmt.format(Math.round(end * eased)) + (el.dataset.suffix || "");
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      cio.unobserve(el);
    });
  }, { threshold: 0.6 });
  document.querySelectorAll("[data-count]").forEach((el) => cio.observe(el));

  if (reduce) return;

  // Cursor glow.
  const glow = document.querySelector(".cursor-glow");
  if (glow && matchMedia("(pointer: fine)").matches) {
    addEventListener("pointermove", (e) => { glow.style.left = e.clientX + "px"; glow.style.top = e.clientY + "px"; }, { passive: true });
  }

  // Subtle 3D tilt on market cards.
  document.querySelectorAll("[data-tilt]").forEach((card) => {
    card.addEventListener("pointermove", (e) => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      card.style.transform = `perspective(1100px) rotateY(${x * 5}deg) rotateX(${-y * 5}deg)`;
    });
    card.addEventListener("pointerleave", () => { card.style.transform = ""; });
    card.style.transition = "transform .6s cubic-bezier(.2,.7,.1,1), opacity 1.1s cubic-bezier(.2,.7,.1,1)";
  });

  // Parallax for elements marked data-parallax.
  const par = [...document.querySelectorAll("[data-parallax]")];
  if (par.length) {
    const run = () => {
      par.forEach((el) => {
        const speed = +el.dataset.parallax || 0.15;
        const r = el.parentElement.getBoundingClientRect();
        el.style.transform = `translateY(${-r.top * speed}px)`;
      });
    };
    addEventListener("scroll", () => requestAnimationFrame(run), { passive: true });
    run();
  }
})();
