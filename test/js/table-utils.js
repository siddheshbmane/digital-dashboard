/**
 * Table Utilities
 * Provides sorting and search functionality for tables
 */

class TableUtils {
  constructor(tableId) {
    this.table = document.getElementById(tableId) || document.querySelector('table');
    this.sortDirection = {};
    this.originalData = [];
  }

  /**
   * Initialize table functionality
   */
  init() {
    if (!this.table) {
      console.warn('Table not found');
      return;
    }

    this.setupSorting();
    this.storeOriginalData();
  }

  /**
   * Setup sorting on table headers
   */
  setupSorting() {
    const headers = this.table.querySelectorAll('thead th');

    headers.forEach((header, index) => {
      // Skip headers that shouldn't be sortable (like action buttons)
      if (header.classList.contains('no-sort')) {
        return;
      }

      // Add sorting indicator
      header.style.cursor = 'pointer';
      header.style.userSelect = 'none';
      header.title = 'Click to sort';

      // Add sort icon
      const sortIcon = document.createElement('i');
      sortIcon.className = 'fas fa-sort ml-2 text-gray-400';
      sortIcon.style.fontSize = '0.75rem';
      header.appendChild(sortIcon);

      // Add click handler
      header.addEventListener('click', () => {
        this.sortTable(index, header);
      });
    });
  }

  /**
   * Sort table by column
   */
  sortTable(columnIndex, header) {
    const tbody = this.table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    // Determine sort direction
    const currentDirection = this.sortDirection[columnIndex] || 'asc';
    const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
    this.sortDirection[columnIndex] = newDirection;

    // Update all header icons
    const allHeaders = this.table.querySelectorAll('thead th');
    allHeaders.forEach(h => {
      const icon = h.querySelector('i.fa-sort, i.fa-sort-up, i.fa-sort-down');
      if (icon) {
        icon.className = 'fas fa-sort ml-2 text-gray-400';
        icon.style.fontSize = '0.75rem';
      }
    });

    // Update current header icon
    const icon = header.querySelector('i');
    if (icon) {
      icon.className = `fas fa-sort-${newDirection === 'asc' ? 'up' : 'down'} ml-2 text-purple-600`;
    }

    // Sort rows
    rows.sort((a, b) => {
      const cellA = a.cells[columnIndex];
      const cellB = b.cells[columnIndex];

      if (!cellA || !cellB) return 0;

      let valueA = cellA.textContent.trim();
      let valueB = cellB.textContent.trim();

      // Try to parse as number (remove currency symbols and commas)
      const numA = this.parseValue(valueA);
      const numB = this.parseValue(valueB);

      // If both are numbers, compare numerically
      if (!isNaN(numA) && !isNaN(numB)) {
        return newDirection === 'asc' ? numA - numB : numB - numA;
      }

      // Otherwise, compare as strings
      return newDirection === 'asc'
        ? valueA.localeCompare(valueB)
        : valueB.localeCompare(valueA);
    });

    // Clear tbody and append sorted rows
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));

    // Add animation
    rows.forEach((row, index) => {
      row.style.animation = `fadeIn 0.3s ease-in ${index * 0.02}s`;
    });
  }

  /**
   * Parse value (handle currency, percentages, etc.)
   */
  parseValue(value) {
    // Remove currency symbols, commas, percentage signs
    const cleaned = value.replace(/[₹$,% ]/g, '');

    // Try to parse as float
    const num = parseFloat(cleaned);

    return num;
  }

  /**
   * Store original table data
   */
  storeOriginalData() {
    const tbody = this.table.querySelector('tbody');
    if (tbody) {
      this.originalData = tbody.innerHTML;
    }
  }

  /**
   * Reset table to original state
   */
  reset() {
    const tbody = this.table.querySelector('tbody');
    if (tbody && this.originalData) {
      tbody.innerHTML = this.originalData;
    }

    // Reset sort directions
    this.sortDirection = {};

    // Reset header icons
    const headers = this.table.querySelectorAll('thead th i');
    headers.forEach(icon => {
      icon.className = 'fas fa-sort ml-2 text-gray-400';
    });
  }
}

/**
 * Table Search
 */
class TableSearch {
  constructor(tableId, searchInputId) {
    this.table = document.getElementById(tableId) || document.querySelector('table');
    this.searchInput = document.getElementById(searchInputId);
    this.rows = [];
  }

  /**
   * Initialize search
   */
  init() {
    if (!this.table) {
      console.warn('Table not found for search');
      return;
    }

    if (!this.searchInput) {
      // Create search input if it doesn't exist
      this.createSearchInput();
    }

    this.setupSearch();
  }

  /**
   * Create search input
   */
  createSearchInput() {
    const tableParent = this.table.parentElement;

    const searchContainer = document.createElement('div');
    searchContainer.className = 'mb-4 flex items-center gap-2';

    searchContainer.innerHTML = `
      <div class="relative flex-1 max-w-md">
        <input
          type="search"
          id="tableSearch"
          placeholder="Search table..."
          class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        />
        <i class="fas fa-search absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"></i>
      </div>
      <span id="searchResults" class="text-sm text-gray-600"></span>
    `;

    tableParent.insertBefore(searchContainer, this.table);
    this.searchInput = document.getElementById('tableSearch');
    this.resultsSpan = document.getElementById('searchResults');
  }

  /**
   * Setup search functionality
   */
  setupSearch() {
    const tbody = this.table.querySelector('tbody');
    this.rows = Array.from(tbody.querySelectorAll('tr'));

    this.searchInput.addEventListener('input', (e) => {
      this.performSearch(e.target.value);
    });
  }

  /**
   * Perform search
   */
  performSearch(query) {
    const searchTerm = query.toLowerCase().trim();

    if (!searchTerm) {
      // Show all rows
      this.rows.forEach(row => {
        row.style.display = '';
        row.classList.remove('highlight');
      });
      this.updateResults(this.rows.length, this.rows.length);
      return;
    }

    let visibleCount = 0;

    this.rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      const matches = text.includes(searchTerm);

      if (matches) {
        row.style.display = '';
        row.classList.add('highlight');
        visibleCount++;
      } else {
        row.style.display = 'none';
        row.classList.remove('highlight');
      }
    });

    this.updateResults(visibleCount, this.rows.length);
  }

  /**
   * Update search results count
   */
  updateResults(visible, total) {
    if (this.resultsSpan) {
      if (visible === total) {
        this.resultsSpan.textContent = `Showing all ${total} results`;
      } else {
        this.resultsSpan.textContent = `Showing ${visible} of ${total} results`;
      }
    }
  }
}

/**
 * Initialize table utils on all tables
 */
function initializeTables() {
  const tables = document.querySelectorAll('table');

  tables.forEach((table, index) => {
    if (table.id || index === 0) {
      const utils = new TableUtils(table.id);
      utils.init();

      // Only add search to main data tables (not summary tables)
      if (table.querySelector('tbody tr').length > 5) {
        const search = new TableSearch(table.id);
        search.init();
      }
    }
  });
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeTables);
} else {
  initializeTables();
}

// Export for manual use
if (typeof window !== 'undefined') {
  window.TableUtils = TableUtils;
  window.TableSearch = TableSearch;
  window.initializeTables = initializeTables;
}
