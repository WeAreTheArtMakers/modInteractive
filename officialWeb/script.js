(() => {
  const doc = document;
  const navLinks = doc.getElementById('navLinks');
  const menuButton = doc.getElementById('mobileMenu');
  const video = doc.getElementById('heroVideo');
  const muteButton = doc.getElementById('muteToggle');
  const stage = doc.getElementById('heroStage');
  const panel = doc.getElementById('videoPanel');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  function setMenu(open) {
    if (!navLinks || !menuButton) return;
    navLinks.classList.toggle('active', open);
    menuButton.classList.toggle('active', open);
    menuButton.setAttribute('aria-expanded', String(open));
    menuButton.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  }

  menuButton?.addEventListener('click', () => setMenu(!navLinks.classList.contains('active')));
  navLinks?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setMenu(false)));

  muteButton?.addEventListener('click', () => {
    if (!video) return;
    video.muted = !video.muted;
    muteButton.textContent = video.muted ? '🔇' : '🔊';
    muteButton.setAttribute('aria-label', video.muted ? 'Unmute video' : 'Mute video');
  });

  doc.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', event => {
      const selector = anchor.getAttribute('href');
      if (!selector || selector === '#') return;
      const target = doc.querySelector(selector);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    });
  });

  const reveals = [...doc.querySelectorAll('[data-reveal]')];
  if (reduceMotion || !('IntersectionObserver' in window)) {
    reveals.forEach(el => el.classList.add('is-visible'));
  } else {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    reveals.forEach(el => observer.observe(el));
  }

  const progress = doc.querySelector('.page-progress span');
  const updateProgress = () => {
    if (!progress) return;
    const scrollable = doc.documentElement.scrollHeight - window.innerHeight;
    const value = scrollable > 0 ? (window.scrollY / scrollable) * 100 : 0;
    progress.style.width = `${Math.min(100, Math.max(0, value))}%`;
  };
  updateProgress();
  window.addEventListener('scroll', updateProgress, { passive: true });
  window.addEventListener('resize', updateProgress);

  if (stage && panel && finePointer && !reduceMotion) {
    const caps = [...stage.querySelectorAll('.capability')];
    let raf = 0;

    const resetStage = () => {
      panel.style.setProperty('--stage-rx', '0deg');
      panel.style.setProperty('--stage-ry', '0deg');
      panel.style.setProperty('--stage-x', '0px');
      panel.style.setProperty('--stage-y', '0px');
      caps.forEach(cap => {
        cap.style.setProperty('--cap-x', '0px');
        cap.style.setProperty('--cap-y', '0px');
      });
    };

    stage.addEventListener('pointermove', event => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const rect = stage.getBoundingClientRect();
        const nx = (event.clientX - rect.left) / rect.width - 0.5;
        const ny = (event.clientY - rect.top) / rect.height - 0.5;
        panel.style.setProperty('--stage-ry', `${nx * 7}deg`);
        panel.style.setProperty('--stage-rx', `${ny * -6}deg`);
        panel.style.setProperty('--stage-x', `${nx * 8}px`);
        panel.style.setProperty('--stage-y', `${ny * 7}px`);
        caps.forEach(cap => {
          const depth = Number(cap.dataset.depth || 1);
          cap.style.setProperty('--cap-x', `${nx * 18 * depth}px`);
          cap.style.setProperty('--cap-y', `${ny * 16 * depth}px`);
        });
      });
    });
    stage.addEventListener('pointerleave', resetStage);
  }

  if (finePointer && !reduceMotion) {
    doc.querySelectorAll('.magnetic').forEach(button => {
      button.addEventListener('pointermove', event => {
        const rect = button.getBoundingClientRect();
        const x = event.clientX - rect.left - rect.width / 2;
        const y = event.clientY - rect.top - rect.height / 2;
        button.style.transform = `translate(${x * 0.08}px, ${y * 0.08}px)`;
      });
      button.addEventListener('pointerleave', () => { button.style.transform = ''; });
    });
  }

  console.log('%c◆ modInteractive', 'font-size:22px;font-weight:700;color:#7fc9ff');
  console.log('%cPrivate interactive display software by WATAM', 'color:#8f9bb2');
})();
