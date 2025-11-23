/**
 * Filter System
 * Handles date range and customer filtering
 */

class FilterManager {
  constructor() {
    this.callbacks = [];
  }

  /**
   * Initialize filters
   */
  init() {
    this.setupCustomerFilter();
    this.setupDateFilters();
    this.setupRefreshButton();
  }

  /**
   * Setup customer dropdown filter
   */
  setupCustomerFilter() {
    const selects = document.querySelectorAll('select[aria-label="Customer filter"], label:contains("Customer") + select');

    selects.forEach(select => {
      select.addEventListener('change', (e) => {
        this.onFilterChange();
      });
    });
  }

  /**
   * Setup date range filters
   */
  setupDateFilters() {
    // From date
    const fromInputs = document.querySelectorAll('input[type="date"]');
    fromInputs.forEach(input => {
      const label = input.previousElementSibling;
      if (label && label.textContent.includes('From')) {
        input.addEventListener('change', () => this.onFilterChange());
      }
    });

    // To date
    fromInputs.forEach(input => {
      const label = input.previousElementSibling;
      if (label && label.textContent.includes('To')) {
        input.addEventListener('change', () => this.onFilterChange());
      }
    });
  }

  /**
   * Setup refresh button
   */
  setupRefreshButton() {
    const refreshButtons = document.querySelectorAll('button[onclick*="refresh"], button:has(i.fa-refresh), button:has(i.fa-sync)');

    refreshButtons.forEach(btn => {
      // Remove inline onclick if exists
      btn.removeAttribute('onclick');

      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.onRefresh();
      });
    });
  }

  /**
   * Get current filter values
   */
  getFilterValues() {
    const filters = {
      customer: 'All',
      dateFrom: null,
      dateTo: null
    };

    // Get customer
    const customerSelect = document.querySelector('select option[selected]')?.parentElement ||
                          document.querySelector('select');
    if (customerSelect) {
      filters.customer = customerSelect.value;
    }

    // Get dates
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach((input, index) => {
      if (index === 0) filters.dateFrom = input.value;
      if (index === 1) filters.dateTo = input.value;
    });

    return filters;
  }

  /**
   * Handle filter change
   */
  onFilterChange() {
    const filters = this.getFilterValues();
    console.log('Filters changed:', filters);

    // Notify all callbacks
    this.callbacks.forEach(callback => {
      try {
        callback(filters);
      } catch (error) {
        console.error('Error in filter callback:', error);
      }
    });
  }

  /**
   * Handle refresh button
   */
  async onRefresh() {
    console.log('Refreshing data...');

    // Show loading state
    this.showLoading();

    // Get current filters
    const filters = this.getFilterValues();

    try {
      // Apply filters to data
      if (window.dataLoader) {
        await window.dataLoader.applyFilters(filters);
      }

      // Notify callbacks
      this.callbacks.forEach(callback => {
        try {
          callback(filters);
        } catch (error) {
          console.error('Error in refresh callback:', error);
        }
      });

      // Show success message
      if (window.showToast) {
        window.showToast('Data refreshed successfully!', 'success');
      }
    } catch (error) {
      console.error('Error refreshing data:', error);

      // Show error message
      if (window.showToast) {
        window.showToast('Failed to refresh data', 'error');
      }
    } finally {
      this.hideLoading();
    }
  }

  /**
   * Register callback for filter changes
   */
  onChange(callback) {
    if (typeof callback === 'function') {
      this.callbacks.push(callback);
    }
  }

  /**
   * Show loading state
   */
  showLoading() {
    const refreshButtons = document.querySelectorAll('button:has(i.fa-refresh), button:has(i.fa-sync)');
    refreshButtons.forEach(btn => {
      const icon = btn.querySelector('i');
      if (icon) {
        icon.classList.add('fa-spin');
      }
      btn.disabled = true;
    });
  }

  /**
   * Hide loading state
   */
  hideLoading() {
    setTimeout(() => {
      const refreshButtons = document.querySelectorAll('button:has(i.fa-refresh), button:has(i.fa-sync)');
      refreshButtons.forEach(btn => {
        const icon = btn.querySelector('i');
        if (icon) {
          icon.classList.remove('fa-spin');
        }
        btn.disabled = false;
      });
    }, 500);
  }

  /**
   * Set filter values programmatically
   */
  setFilters(filters) {
    if (filters.customer) {
      const customerSelect = document.querySelector('select');
      if (customerSelect) {
        customerSelect.value = filters.customer;
      }
    }

    if (filters.dateFrom) {
      const fromInput = document.querySelector('input[type="date"]');
      if (fromInput) {
        fromInput.value = filters.dateFrom;
      }
    }

    if (filters.dateTo) {
      const toInput = document.querySelectorAll('input[type="date"]')[1];
      if (toInput) {
        toInput.value = filters.dateTo;
      }
    }
  }
}

// Create global instance
const filterManager = new FilterManager();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => filterManager.init());
} else {
  filterManager.init();
}

// Export for use in other scripts
if (typeof window !== 'undefined') {
  window.filterManager = filterManager;
}
