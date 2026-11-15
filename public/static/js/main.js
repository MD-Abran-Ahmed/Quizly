/**
 * QUIZLY – CORE INTERACTIONS & LIQUID GLASS ENGINE
 * Apple-inspired cursor tracking, card 3D tilt, magnetic hover, and toast engine.
 */

window.Quizly = (function() {
  'use strict';

  // State
  const state = {
    isTouch: ('ontouchstart' in window) || (navigator.maxTouchPoints > 0),
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
  };

  /**
   * Adds subtle 3D tilt effect to glass cards
   */
  function initTiltCards() {
    if (state.isTouch || state.reducedMotion) return;

    const cards = document.querySelectorAll('.tilt-card, .stat-card, .action-card');

    cards.forEach(card => {
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const rotateX = ((y - centerY) / centerY) * -6; // max 6deg
        const rotateY = ((x - centerX) / centerX) * 6;

        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-3px)`;
      });

      card.addEventListener('mouseleave', () => {
        card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)';
      });
    });
  }

  /**
   * Magnetic Button Effect
   */
  function initMagneticButtons() {
    if (state.isTouch || state.reducedMotion) return;

    const buttons = document.querySelectorAll('.btn-primary, .btn-glass');

    buttons.forEach(btn => {
      btn.addEventListener('mousemove', (e) => {
        const rect = btn.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;

        btn.style.transform = `translate(${x * 0.18}px, ${y * 0.18}px)`;
      });

      btn.addEventListener('mouseleave', () => {
        btn.style.transform = 'translate(0px, 0px)';
      });
    });
  }

  /**
   * Shows an Apple-style floating toast notification
   */
  function showToast(message, type = 'info', duration = 4000) {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="20" height="20" fill="none" stroke="#6AC388" stroke-width="2" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg width="20" height="20" fill="none" stroke="#E57373" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
    } else {
      iconSvg = '<svg width="20" height="20" fill="none" stroke="#D6BC83" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `
      <div style="flex-shrink:0;">${iconSvg}</div>
      <div style="font-size: 0.9rem; line-height: 1.4;">${message}</div>
      <button class="toast-close" aria-label="Close">&times;</button>
    `;

    toast.querySelector('.toast-close').addEventListener('click', () => {
      toast.remove();
    });

    container.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(50px)';
        setTimeout(() => toast.remove(), 300);
      }, duration);
    }
  }

  /**
   * Mobile Sidebar Toggle & Touch-friendly Backdrop Handling
   */
  function initMobileMenu() {
    const toggleBtns = document.querySelectorAll('.mobile-menu-btn');
    const sidebar = document.querySelector('.dashboard-sidebar');
    let backdrop = document.querySelector('.sidebar-backdrop');

    // Create backdrop element automatically if not in template
    if (sidebar && !backdrop) {
      backdrop = document.createElement('div');
      backdrop.className = 'sidebar-backdrop';
      document.body.appendChild(backdrop);
    }

    const closeSidebar = () => {
      if (sidebar) sidebar.classList.remove('open');
      if (backdrop) backdrop.classList.remove('open');
      document.body.classList.remove('sidebar-locked');
    };

    const openSidebar = () => {
      if (sidebar) sidebar.classList.add('open');
      if (backdrop) backdrop.classList.add('open');
      document.body.classList.add('sidebar-locked');
    };

    toggleBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (sidebar && sidebar.classList.contains('open')) {
          closeSidebar();
        } else {
          openSidebar();
        }
      });
    });

    if (backdrop) {
      backdrop.addEventListener('click', closeSidebar);
      backdrop.addEventListener('touchstart', (e) => {
        e.preventDefault();
        closeSidebar();
      }, { passive: false });
    }

    // Close button inside sidebar
    const closeBtns = document.querySelectorAll('.sidebar-close-btn');
    closeBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeSidebar();
      });
    });

    // Close on any link click inside sidebar on mobile
    if (sidebar) {
      const links = sidebar.querySelectorAll('.sidebar-link');
      links.forEach(link => {
        link.addEventListener('click', () => {
          if (window.innerWidth <= 860) {
            closeSidebar();
          }
        });
      });
    }

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
        closeSidebar();
      }
    });
  }

  // Auto-init on DOMContentLoaded
  document.addEventListener('DOMContentLoaded', () => {
    initTiltCards();
    initMagneticButtons();
    initMobileMenu();
  });

  return {
    showToast
  };
})();

