// PRITECH 2.0 — Glassmorphism + Mobile Interactions (Tailwind Compatible)
(function() {
  "use strict";

  // Wait for DOM to be ready
  document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initActiveNavLinks();
    initScrollReveal();
    initAutoDismissAlerts();
    initSwipeGestures();
    initButtonFeedback();
    initParallaxEffect();
  });

  // ========== SIDEBAR TOGGLE (MOBILE) ==========
  function initSidebar() {
    const toggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (!toggle || !sidebar) return;

    const openSidebar = () => {
      sidebar.classList.remove('-translate-x-full');
      overlay?.classList.add('show');
      document.body.style.overflow = 'hidden';
    };

    const closeSidebar = () => {
      sidebar.classList.add('-translate-x-full');
      overlay?.classList.remove('show');
      document.body.style.overflow = '';
    };

    toggle.addEventListener('click', openSidebar);
    overlay?.addEventListener('click', closeSidebar);

    // Close on window resize if desktop
    window.addEventListener('resize', () => {
      if (window.innerWidth >= 768) {
        closeSidebar();
      }
    });
  }

  // ========== ACTIVE NAVIGATION LINK ==========
  function initActiveNavLinks() {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-item, .bottom-nav-item').forEach(el => {
      const href = el.getAttribute('href');
      if (href && path.startsWith(href) && href !== '/') {
        el.classList.add('active');
      }
    });
  }

  // ========== SCROLL REVEAL (INTERSECTION OBSERVER) ==========
  function initScrollReveal() {
    // Add .reveal class to common animated elements if not already present
    const revealSelectors = '.card, .stat-card, .service-card, .hero h1, .hero p, .hero-btns, .section-title, .glass-card';
    document.querySelectorAll(revealSelectors).forEach(el => {
      if (!el.classList.contains('reveal')) {
        el.classList.add('reveal');
      }
    });

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -20px 0px' });

    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

    // Force check for any elements already visible on load
    setTimeout(() => {
      document.querySelectorAll('.reveal:not(.visible)').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight - 100) {
          el.classList.add('visible');
          observer.unobserve(el);
        }
      });
    }, 200);
  }

  // ========== AUTO-DISMISS ALERTS ==========
  function initAutoDismissAlerts() {
    document.querySelectorAll('.alert').forEach(el => {
      setTimeout(() => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(-10px)';
        el.style.transition = 'all 0.4s ease';
        setTimeout(() => el.remove(), 400);
      }, 5000);
    });
  }

  // ========== TOUCH SWIPE GESTURES FOR SIDEBAR ==========
  function initSwipeGestures() {
    let touchStartX = 0;
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (!sidebar) return;

    document.addEventListener('touchstart', (e) => {
      touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
      const touchEndX = e.changedTouches[0].screenX;
      const diff = touchStartX - touchEndX;

      // Swipe left (>50px) to open sidebar
      if (diff > 50 && sidebar.classList.contains('-translate-x-full')) {
        sidebar.classList.remove('-translate-x-full');
        overlay?.classList.add('show');
        document.body.style.overflow = 'hidden';
      }
      // Swipe right (>50px) to close sidebar
      if (diff < -50 && !sidebar.classList.contains('-translate-x-full')) {
        sidebar.classList.add('-translate-x-full');
        overlay?.classList.remove('show');
        document.body.style.overflow = '';
      }
    }, { passive: true });
  }

  // ========== BUTTON PRESS FEEDBACK ==========
  function initButtonFeedback() {
    document.querySelectorAll('.btn, button[type="submit"]').forEach(btn => {
      btn.addEventListener('mousedown', () => {
        btn.style.transform = 'scale(0.97)';
      });
      btn.addEventListener('mouseup', () => {
        btn.style.transform = '';
      });
      btn.addEventListener('mouseleave', () => {
        btn.style.transform = '';
      });
    });
  }

  // ========== PARALLAX / SCROLL EFFECTS ==========
  function initParallaxEffect() {
    window.addEventListener('scroll', () => {
      const scrolled = window.scrollY;
      const hero = document.querySelector('.hero');
      if (hero && scrolled < 600) {
        hero.style.backgroundPosition = `0% ${50 + scrolled * 0.05}%`;
      }

      // Slight topbar transparency change on scroll
      const topbar = document.querySelector('.topbar, .glass-topbar');
      if (topbar) {
        if (scrolled > 20) {
          topbar.style.background = 'rgba(255, 255, 255, 0.95)';
        } else {
          topbar.style.background = 'rgba(255, 255, 255, 0.8)';
        }
      }
    });
  }

  // ========== DYNAMIC BACKDROP SUPPORT DETECTION ==========
  if (!CSS.supports('backdrop-filter', 'blur(8px)')) {
    document.body.classList.add('no-backdrop');
    // Fallback: make glass elements opaque
    document.querySelectorAll('.glass-card, .glass-sidebar, .glass-topbar').forEach(el => {
      if (el.classList.contains('glass-sidebar')) {
        el.style.backgroundColor = '#111827';
      } else {
        el.style.backgroundColor = '#ffffff';
      }
    });
  }

})();