/**
 * Dark Mode Theme Switcher
 * Handles theme toggling with smooth transitions and localStorage persistence
 */

class DarkMode {
  constructor() {
    this.theme = this.getStoredTheme();
    this.init();
  }

  /**
   * Initialize dark mode
   */
  init() {
    // Apply stored theme immediately (before page render)
    this.applyTheme(this.theme);

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.setupToggle());
    } else {
      this.setupToggle();
    }
  }

  /**
   * Get stored theme from localStorage
   */
  getStoredTheme() {
    const stored = localStorage.getItem('theme');
    if (stored) {
      return stored;
    }

    // Check system preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }

    return 'light';
  }

  /**
   * Apply theme to document
   */
  applyTheme(theme) {
    this.theme = theme;

    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }

    // Store preference
    localStorage.setItem('theme', theme);

    // Update toggle button if it exists
    this.updateToggleButton();
  }

  /**
   * Toggle between light and dark themes
   */
  toggle() {
    const newTheme = this.theme === 'light' ? 'dark' : 'light';
    this.applyTheme(newTheme);

    // Dispatch custom event for other components to react
    window.dispatchEvent(new CustomEvent('themechange', {
      detail: { theme: newTheme }
    }));
  }

  /**
   * Setup toggle button functionality
   */
  setupToggle() {
    const toggleBtn = document.getElementById('darkModeToggle');

    if (!toggleBtn) {
      console.warn('Dark mode toggle button not found. Add id="darkModeToggle" to your theme toggle button.');
      return;
    }

    // Add click handler
    toggleBtn.addEventListener('click', () => this.toggle());

    // Update button state
    this.updateToggleButton();
  }

  /**
   * Update toggle button appearance
   */
  updateToggleButton() {
    const toggleBtn = document.getElementById('darkModeToggle');

    if (!toggleBtn) return;

    const icon = toggleBtn.querySelector('i');

    if (this.theme === 'dark') {
      // Show sun icon (to switch to light)
      if (icon) {
        icon.className = 'fas fa-sun';
      }
      toggleBtn.setAttribute('aria-label', 'Switch to light mode');
      toggleBtn.setAttribute('title', 'Switch to light mode');
    } else {
      // Show moon icon (to switch to dark)
      if (icon) {
        icon.className = 'fas fa-moon';
      }
      toggleBtn.setAttribute('aria-label', 'Switch to dark mode');
      toggleBtn.setAttribute('title', 'Switch to dark mode');
    }
  }

  /**
   * Get current theme
   */
  getCurrentTheme() {
    return this.theme;
  }

  /**
   * Set theme programmatically
   */
  setTheme(theme) {
    if (theme === 'light' || theme === 'dark') {
      this.applyTheme(theme);
    }
  }
}

// Initialize dark mode immediately
const darkMode = new DarkMode();

// Export for use in other scripts
if (typeof window !== 'undefined') {
  window.darkMode = darkMode;
}
