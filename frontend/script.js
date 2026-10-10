// ===========================
//  Aurix AI — script.js
//  Landing page + Google Auth
// ===========================

// --- API Base URL ---
const API_BASE = window.location.origin;

// --- Global Google Sign-In callback ---
function handleGoogleSignIn(response) {
  const credential = response.credential;

  fetch(`${API_BASE}/api/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ credential }),
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        // Store user info
        localStorage.setItem('aurix-user', JSON.stringify(data.user));
        localStorage.setItem('aurix-session', data.session_id);
        // Redirect to dashboard
        window.location.href = 'dashboard.html';
      } else {
        alert('Sign-in failed: ' + (data.error || 'Unknown error'));
      }
    })
    .catch(err => {
      console.error('Auth error:', err);
      alert('Sign-in failed. Please try again.');
    });
}

(() => {
  'use strict';

  // --- Theme Toggle (Day / Night) ---
  const themeToggle = document.getElementById('theme-toggle');
  const htmlEl = document.documentElement;

  // Restore saved theme or default to dark
  const savedTheme = localStorage.getItem('aurix-theme') || 'dark';
  if (savedTheme === 'light') {
    htmlEl.setAttribute('data-theme', 'light');
  }

  themeToggle && themeToggle.addEventListener('click', () => {
    const currentTheme = htmlEl.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';

    if (newTheme === 'light') {
      htmlEl.setAttribute('data-theme', 'light');
    } else {
      htmlEl.removeAttribute('data-theme');
    }

    localStorage.setItem('aurix-theme', newTheme);
  });

  // --- Navbar scroll effect ---
  const navbar = document.getElementById('navbar');
  let lastScroll = 0;

  const handleScroll = () => {
    const current = window.scrollY;
    if (current > 20) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
    lastScroll = current;
  };

  window.addEventListener('scroll', handleScroll, { passive: true });

  // --- Hamburger menu ---
  const hamburger = document.getElementById('hamburger');
  const navLinks  = document.getElementById('nav-links');
  const navActions = document.querySelector('.nav-actions');

  hamburger && hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('active');
    navLinks && navLinks.classList.toggle('open');
    navActions && navActions.classList.toggle('open');
  });

  // --- Ripple click effect ---
  document.querySelectorAll('.btn-primary, .btn-cta-nav').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const ripple = document.createElement('span');
      const rect = btn.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      ripple.style.cssText = `
        position:absolute;width:${size}px;height:${size}px;
        left:${e.clientX - rect.left - size / 2}px;
        top:${e.clientY - rect.top - size / 2}px;
        border-radius:50%;background:rgba(255,255,255,0.25);
        transform:scale(0);pointer-events:none;
        animation:ripple-effect 0.5s ease forwards;
      `;
      btn.style.position = 'relative';
      btn.style.overflow = 'hidden';
      btn.appendChild(ripple);
      setTimeout(() => ripple.remove(), 500);
    });
  });

  // --- Intersection Observer for fade-in animations ---
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'translateY(0)';
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1, rootMargin: '0px 0px -60px 0px' }
  );

  document.querySelectorAll('.trust-item, .hero-left, .hero-right').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
  });

  // --- Gradient text shimmer ---
  const gradText = document.querySelector('.gradient-text');
  if (gradText) {
    gradText.style.backgroundSize = '200% auto';
  }

  // --- Google Sign-In Modal ---
  const signinModal = document.getElementById('google-signin-modal');
  const signinOverlay = document.getElementById('signin-overlay');
  const signinClose = document.getElementById('signin-close');
  const signinDemoBtn = document.getElementById('signin-demo-btn');
  const btnSignin = document.getElementById('btn-signin');
  const btnCtaNav = document.getElementById('btn-cta-nav');
  const btnGetStarted = document.getElementById('btn-get-started');

  function openSigninModal() {
    // Check if user is already signed in
    const existingUser = localStorage.getItem('aurix-user');
    if (existingUser) {
      window.location.href = 'dashboard.html';
      return;
    }
    signinModal && signinModal.classList.add('visible');
  }

  function closeSigninModal() {
    signinModal && signinModal.classList.remove('visible');
  }

  btnSignin && btnSignin.addEventListener('click', openSigninModal);
  btnCtaNav && btnCtaNav.addEventListener('click', openSigninModal);
  btnGetStarted && btnGetStarted.addEventListener('click', openSigninModal);
  signinOverlay && signinOverlay.addEventListener('click', closeSigninModal);
  signinClose && signinClose.addEventListener('click', closeSigninModal);

  // Escape key closes modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSigninModal();
  });

  // "Continue as Guest" — skip Google auth, go to dashboard in demo mode
  signinDemoBtn && signinDemoBtn.addEventListener('click', () => {
    const guestUser = {
      id: 'guest',
      email: 'guest@demo.aurix.ai',
      name: 'Guest User',
      picture: '',
    };
    localStorage.setItem('aurix-user', JSON.stringify(guestUser));
    localStorage.setItem('aurix-session', 'demo-' + Date.now());
    window.location.href = 'dashboard.html';
  });

  // --- Log welcome ---
  console.log('%c Aurix AI ', 'background:#00d4ff;color:#000;font-weight:700;font-size:14px;padding:4px 8px;border-radius:4px;', '— Frontend loaded ✓');

})();
