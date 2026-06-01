/* ═══════════════════════════════════════════════════════════════
   PRITECH ICT SOLUTIONS — Main JavaScript (Final with Animations)
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ── DOM ready helper ──────────────────────────────────────────
const ready = (fn) => {
  if (document.readyState !== 'loading') fn();
  else document.addEventListener('DOMContentLoaded', fn);
};

ready(() => {

  // ═══════════════════════════════════
  // THEME TOGGLE (Dark / Light)
  // ═══════════════════════════════════
  const html = document.documentElement;
  const themeBtn = document.getElementById('themeToggle');

  const applyTheme = (theme) => {
    html.setAttribute('data-theme', theme);
    localStorage.setItem('pritech-theme', theme);
  };

  const savedTheme = localStorage.getItem('pritech-theme');
  if (savedTheme) applyTheme(savedTheme);

  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const current = html.getAttribute('data-theme');
      applyTheme(current === 'dark' ? 'light' : 'dark');
    });
  }

  // ═══════════════════════════════════
  // STICKY NAVBAR + SCROLL PROGRESS
  // ═══════════════════════════════════
  const header = document.getElementById('site-header');
  const progress = document.getElementById('scrollProgress');
  const backTop = document.getElementById('backToTop');

  const updateScroll = () => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const pct = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;

    if (header) header.classList.toggle('scrolled', scrollTop > 40);
    if (progress) {
      progress.style.width = pct + '%';
      progress.setAttribute('aria-valuenow', Math.round(pct));
    }
    if (backTop) backTop.classList.toggle('visible', scrollTop > 400);
  };

  window.addEventListener('scroll', updateScroll, { passive: true });
  updateScroll();

  if (backTop) {
    backTop.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // ═══════════════════════════════════
  // MOBILE HAMBURGER MENU + FOCUS TRAP
  // ═══════════════════════════════════
  const hamburger = document.getElementById('hamburger');
  const mobileMenu = document.getElementById('mobile-menu');
  const mobileCloseBtn = document.querySelector('.mobile-close-btn');

  if (hamburger && mobileMenu) {
    let focusableElements = null;
    let previouslyFocused = null;

    const trapFocus = (e) => {
      if (!mobileMenu.classList.contains('open')) return;
      const focusable = focusableElements || Array.from(mobileMenu.querySelectorAll('a, button, [tabindex="0"]'));
      focusableElements = focusable;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.key === 'Tab') {
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    const openMenu = () => {
      hamburger.classList.add('open');
      mobileMenu.classList.add('open');
      hamburger.setAttribute('aria-expanded', 'true');
      mobileMenu.setAttribute('aria-hidden', 'false');
      previouslyFocused = document.activeElement;
      const firstLink = mobileMenu.querySelector('.mobile-link');
      if (firstLink) firstLink.focus();
      document.addEventListener('keydown', trapFocus);
    };

    const closeMenu = () => {
      hamburger.classList.remove('open');
      mobileMenu.classList.remove('open');
      hamburger.setAttribute('aria-expanded', 'false');
      mobileMenu.setAttribute('aria-hidden', 'true');
      if (previouslyFocused) previouslyFocused.focus();
      document.removeEventListener('keydown', trapFocus);
    };

    hamburger.addEventListener('click', () => {
      if (mobileMenu.classList.contains('open')) closeMenu();
      else openMenu();
    });

    if (mobileCloseBtn) {
      mobileCloseBtn.addEventListener('click', closeMenu);
    }

    mobileMenu.querySelectorAll('.mobile-link').forEach(link => {
      link.addEventListener('click', closeMenu);
    });

    document.addEventListener('click', (e) => {
      if (!header.contains(e.target)) closeMenu();
    });

    mobileMenu.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeMenu();
    });
  }

  // ═══════════════════════════════════
  // SCROLL REVEAL ANIMATIONS
  // ═══════════════════════════════════
  if ('IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('revealed');
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -20px 0px' });

    document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));
    window.revealObserver = revealObserver; // store for dynamic content
  } else {
    document.querySelectorAll('.reveal').forEach(el => el.classList.add('revealed'));
  }

  // ═══════════════════════════════════
  // ACTIVE NAV LINK (section highlighting)
  // ═══════════════════════════════════
  const sections = document.querySelectorAll('section[id]');
  const navLinks = document.querySelectorAll('.nav-link[href*="#"]');

  if (sections.length && navLinks.length) {
    const sectionObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          navLinks.forEach(link => {
            link.classList.toggle('active', link.getAttribute('href').includes(`#${id}`));
          });
        }
      });
    }, { rootMargin: '-30% 0px -40% 0px' });

    sections.forEach(sec => sectionObserver.observe(sec));
  }

  // ═══════════════════════════════════
  // TOAST AUTO-DISMISS
  // ═══════════════════════════════════
  const dismissToast = (toast) => {
    toast.style.animation = 'toastSlide 300ms ease reverse forwards';
    setTimeout(() => toast.remove(), 300);
  };

  document.querySelectorAll('.toast').forEach(toast => {
    setTimeout(() => { if (toast.isConnected) dismissToast(toast); }, 5000);
    const closeBtn = toast.querySelector('.toast-close');
    if (closeBtn) closeBtn.addEventListener('click', () => dismissToast(toast));
  });

  // ═══════════════════════════════════
  // SERVICE CATEGORY TABS (Improved)
  // ═══════════════════════════════════
  const serviceTabs = document.querySelectorAll('.service-tab');
  const serviceCards = document.querySelectorAll('.service-card[data-category]');

  if (serviceTabs.length) {
    serviceTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        serviceTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const filter = tab.dataset.category;
        serviceCards.forEach(card => {
          const show = filter === 'all' || card.dataset.category === filter;
          if (show) {
            card.style.display = '';
            card.style.opacity = '1';
            card.style.transform = 'scale(1)';
          } else {
            card.style.opacity = '0';
            card.style.transform = 'scale(0.95)';
            setTimeout(() => {
              if (card.dataset.category !== filter && filter !== 'all') {
                card.style.display = 'none';
              }
            }, 150);
          }
        });
      });
    });
  }

  // ═══════════════════════════════════
  // ANIMATED COUNTERS (smooth)
  // ═══════════════════════════════════
  const animateCounter = (el, target, duration = 1800) => {
    const start = performance.now();
    const update = (now) => {
      const elapsed = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - elapsed, 3);
      el.textContent = Math.round(eased * target);
      if (elapsed < 1) requestAnimationFrame(update);
    };
    requestAnimationFrame(update);
  };

  if ('IntersectionObserver' in window) {
    const counterObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const target = parseInt(el.dataset.count, 10);
          if (!isNaN(target)) animateCounter(el, target);
          counterObserver.unobserve(el);
        }
      });
    }, { threshold: 0.5 });
    document.querySelectorAll('[data-count]').forEach(el => counterObserver.observe(el));
  }

  // ═══════════════════════════════════
  // FORM REAL-TIME HINTS (non-destructive)
  // ═══════════════════════════════════
  const validateEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const validatePhone = (phone) => !phone || /^[\d\s\+\-\(\)]{7,}$/.test(phone.trim());

  document.querySelectorAll('.inquiry-form, form').forEach(form => {
    const inputs = form.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
      let hintEl = input.parentElement.querySelector('.form-hint');
      if (!hintEl) {
        hintEl = document.createElement('span');
        hintEl.className = 'form-hint';
        hintEl.setAttribute('aria-live', 'polite');
        input.parentElement.appendChild(hintEl);
      }
      const validate = () => {
        let msg = '';
        if (input.required && !input.value.trim()) {
          msg = 'This field is required.';
        } else if (input.type === 'email' && input.value && !validateEmail(input.value)) {
          msg = 'Please enter a valid email address.';
        } else if (input.name === 'phone' && input.value && !validatePhone(input.value)) {
          msg = 'Please enter a valid phone number.';
        }
        hintEl.textContent = msg;
        input.style.borderColor = msg ? 'var(--error)' : (input.value ? 'var(--success)' : '');
        return !msg;
      };
      input.addEventListener('blur', validate);
      input.addEventListener('input', () => {
        if (hintEl.textContent) validate();
        if (!input.value) input.style.borderColor = '';
      });
    });
  });

  // ═══════════════════════════════════
  // SMOOTH ANCHOR SCROLLING
  // ═══════════════════════════════════
  document.querySelectorAll('a[href*="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      const url = new URL(anchor.href);
      if (url.pathname === window.location.pathname && url.hash) {
        const target = document.querySelector(url.hash);
        if (target) {
          e.preventDefault();
          const offset = 80;
          const top = target.getBoundingClientRect().top + window.scrollY - offset;
          window.scrollTo({ top, behavior: 'smooth' });
          target.focus({ preventScroll: true });
        }
      }
    });
  });

  // ═══════════════════════════════════
  // HERO BARS animation (fixed)
  // ═══════════════════════════════════
  const heroBars = document.querySelectorAll('.hero-bar-fill');
  heroBars.forEach(bar => {
    const targetWidth = bar.style.width;
    if (targetWidth) {
      bar.style.width = '0';
      requestAnimationFrame(() => {
        bar.style.width = targetWidth;
      });
    }
  });

  // ═══════════════════════════════════
  // BUTTON RIPPLE EFFECT
  // ═══════════════════════════════════
  const buttons = document.querySelectorAll('.btn');
  const createRipple = (e) => {
    const btn = e.currentTarget;
    const rect = btn.getBoundingClientRect();
    const ripple = document.createElement('span');
    ripple.className = 'ripple';
    const size = Math.max(rect.width, rect.height);
    ripple.style.width = ripple.style.height = `${size}px`;
    ripple.style.left = `${e.clientX - rect.left - size/2}px`;
    ripple.style.top = `${e.clientY - rect.top - size/2}px`;
    btn.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove());
  };
  buttons.forEach(btn => btn.addEventListener('click', createRipple));

  // ═══════════════════════════════════
  // TYPING ANIMATION FOR HERO TITLE (optional, once per user)
  // ═══════════════════════════════════
  const heroTitle = document.querySelector('.hero-title');
  if (heroTitle && !heroTitle.classList.contains('typing')) {
    if (window.innerWidth > 768 && !localStorage.getItem('heroTyped')) {
      const originalText = heroTitle.innerText;
      heroTitle.style.width = '0';
      heroTitle.classList.add('typing');
      heroTitle.innerText = originalText;
      setTimeout(() => {
        heroTitle.style.width = '';
        heroTitle.classList.remove('typing');
        localStorage.setItem('heroTyped', 'true');
      }, 2500);
    }
  }

  // ═══════════════════════════════════
  // PARALLAX HERO ON SCROLL (subtle, disabled on touch)
  // ═══════════════════════════════════
  const hero = document.querySelector('.hero');
  if (hero && 'ontouchstart' in window === false) {
    window.addEventListener('scroll', () => {
      const scrollY = window.scrollY;
      hero.style.backgroundPositionY = `${scrollY * 0.2}px`;
    });
  }

  // ═══════════════════════════════════
  // IMAGE LAZY LOAD – REMOVE SKELETON ONCE LOADED
  // ═══════════════════════════════════
  const lazyImages = document.querySelectorAll('img[loading="lazy"]');
  lazyImages.forEach(img => {
    if (img.complete) {
      img.classList.add('loaded');
    } else {
      img.addEventListener('load', () => img.classList.add('loaded'));
      img.addEventListener('error', () => img.classList.add('loaded'));
    }
  });

  // ═══════════════════════════════════
  // DYNAMIC CONTENT OBSERVER (for future HTMX or AJAX)
  // ═══════════════════════════════════
  const dynamicObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === 1 && node.matches && node.matches('.reveal:not(.revealed)')) {
          if (window.revealObserver) {
            window.revealObserver.observe(node);
          } else {
            node.classList.add('revealed');
          }
        }
        // Also re-run counters on new elements
        if (node.nodeType === 1 && node.querySelectorAll) {
          node.querySelectorAll('[data-count]').forEach(el => {
            if (!el.classList.contains('counted')) {
              const target = parseInt(el.dataset.count, 10);
              if (!isNaN(target)) {
                animateCounter(el, target);
                el.classList.add('counted');
              }
            }
          });
        }
      });
    });
  });
  dynamicObserver.observe(document.body, { childList: true, subtree: true });

  // ═══════════════════════════════════
  // RESPONSIVE ENHANCEMENTS
  // ═══════════════════════════════════
  const mobileMedia = window.matchMedia('(max-width: 767px)');
  const updateMobileMenuHeight = () => {
    const mobileMenuDiv = document.getElementById('mobile-menu');
    if (mobileMenuDiv && mobileMenuDiv.classList.contains('open')) {
      mobileMenuDiv.style.maxHeight = `calc(100dvh - 72px)`;
    }
  };
  if (mobileMedia.addEventListener) {
    mobileMedia.addEventListener('change', updateMobileMenuHeight);
  } else {
    mobileMedia.addListener(updateMobileMenuHeight);
  }

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (window.innerWidth > 767) {
        const hamburgerBtn = document.getElementById('hamburger');
        const mobileMenuDiv = document.getElementById('mobile-menu');
        if (hamburgerBtn && hamburgerBtn.classList.contains('open')) {
          hamburgerBtn.classList.remove('open');
          mobileMenuDiv?.classList.remove('open');
          hamburgerBtn.setAttribute('aria-expanded', 'false');
          mobileMenuDiv?.setAttribute('aria-hidden', 'true');
        }
      }
    }, 150);
  });

  // Larger touch targets for service tabs on mobile
  const serviceTabButtons = document.querySelectorAll('.service-tab');
  if (serviceTabButtons.length && 'ontouchstart' in window) {
    serviceTabButtons.forEach(tab => {
      tab.style.padding = '10px 16px';
    });
  }

  console.log('%c🚀 Pritech ICT Solutions (Final with Modern Animations)', 'color:#0ea5e9;font-weight:800;font-size:16px;');
});