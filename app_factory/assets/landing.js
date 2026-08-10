(() => {
  const root = document.documentElement;
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  root.classList.add('is-enhanced');
  if (reducedMotion) {
    root.classList.add('is-reduced-motion');
  }

  const reveal = () => {
    document.querySelectorAll('[data-landing-reveal]').forEach((element) => {
      element.classList.add('is-revealed');
    });
  };

  if (reducedMotion || !('IntersectionObserver' in window)) {
    reveal();
    return;
  }

  const observer = new IntersectionObserver((entries, instance) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-revealed');
      instance.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.01 });

  document.querySelectorAll('[data-landing-reveal]').forEach((element) => {
    observer.observe(element);
  });

  document.querySelectorAll('[data-landing-chapter]').forEach((chapter) => {
    chapter.addEventListener('focusin', () => {
      const id = chapter.id;
      if (!id) return;
      document.querySelectorAll('[data-landing-chapter-link]').forEach((link) => {
        link.toggleAttribute('aria-current', link.getAttribute('href') === `#${id}`);
      });
    });
  });
})();
