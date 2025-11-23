/**
 * Data Loader and Filter System
 * Loads data from JSON and provides filtering capabilities
 */

class DataLoader {
  constructor() {
    this.data = null;
    this.filteredData = null;
    this.filters = {
      customer: 'All',
      dateFrom: null,
      dateTo: null,
      platform: 'All'
    };
  }

  /**
   * Load data from JSON file
   */
  async loadData() {
    try {
      const response = await fetch('data/analytics-data.json');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      this.data = await response.json();
      this.filteredData = this.data;
      return this.data;
    } catch (error) {
      console.error('Error loading data:', error);
      // Return sample data if file not found (for development)
      return this.getSampleData();
    }
  }

  /**
   * Apply filters to data
   */
  applyFilters(filters = {}) {
    // Update filter state
    this.filters = { ...this.filters, ...filters };

    if (!this.data) {
      console.warn('No data loaded yet');
      return null;
    }

    // Start with full dataset
    let filtered = JSON.parse(JSON.stringify(this.data));

    // Filter by customer
    if (this.filters.customer && this.filters.customer !== 'All') {
      const client = filtered.clients.find(c => c.name === this.filters.customer);
      if (client) {
        // Filter campaigns by client
        filtered.campaigns = filtered.campaigns.filter(campaign => {
          return campaign.name.includes(client.name.split(' ')[0]);
        });
      }
    }

    // Filter by date range
    if (this.filters.dateFrom && this.filters.dateTo) {
      const from = new Date(this.filters.dateFrom);
      const to = new Date(this.filters.dateTo);

      filtered.dailyMetrics = filtered.dailyMetrics.filter(day => {
        const date = new Date(day.date);
        return date >= from && date <= to;
      });

      filtered.campaigns = filtered.campaigns.filter(campaign => {
        const startDate = new Date(campaign.startDate);
        return startDate >= from && startDate <= to;
      });
    }

    // Filter by platform
    if (this.filters.platform && this.filters.platform !== 'All') {
      filtered.campaigns = filtered.campaigns.filter(campaign => {
        return campaign.platform === this.filters.platform;
      });
    }

    // Recalculate summary based on filtered data
    filtered.summary = this.calculateSummary(filtered);

    this.filteredData = filtered;
    return filtered;
  }

  /**
   * Calculate summary metrics from filtered data
   */
  calculateSummary(data) {
    const campaigns = data.campaigns || [];

    const totalSpend = campaigns.reduce((sum, c) => sum + c.spend, 0);
    const totalImpressions = campaigns.reduce((sum, c) => sum + c.impressions, 0);
    const totalClicks = campaigns.reduce((sum, c) => sum + c.clicks, 0);
    const totalLeads = campaigns.reduce((sum, c) => sum + c.leads, 0);
    const qualifiedLeads = campaigns.reduce((sum, c) => sum + c.qualified, 0);
    const totalRevenue = campaigns.reduce((sum, c) => sum + c.revenue, 0);

    return {
      totalSpend,
      totalImpressions,
      totalClicks,
      ctr: totalImpressions > 0 ? (totalClicks / totalImpressions * 100).toFixed(2) : 0,
      totalLeads,
      qualifiedLeads,
      qualificationRate: totalLeads > 0 ? (qualifiedLeads / totalLeads * 100).toFixed(1) : 0,
      cpl: totalLeads > 0 ? Math.round(totalSpend / totalLeads) : 0,
      cpql: qualifiedLeads > 0 ? Math.round(totalSpend / qualifiedLeads) : 0,
      revenue: totalRevenue,
      roi: totalSpend > 0 ? Math.round((totalRevenue / totalSpend - 1) * 100) : 0
    };
  }

  /**
   * Get filtered data
   */
  getData() {
    return this.filteredData || this.data;
  }

  /**
   * Get summary metrics
   */
  getSummary() {
    const data = this.getData();
    return data ? data.summary : null;
  }

  /**
   * Get campaigns
   */
  getCampaigns() {
    const data = this.getData();
    return data ? data.campaigns : [];
  }

  /**
   * Get clients
   */
  getClients() {
    const data = this.getData();
    return data ? data.clients : [];
  }

  /**
   * Get keywords
   */
  getKeywords() {
    const data = this.getData();
    return data ? data.keywords : [];
  }

  /**
   * Get leads by source
   */
  getLeadsBySource() {
    const data = this.getData();
    return data ? data.leadsBySource : [];
  }

  /**
   * Get daily metrics
   */
  getDailyMetrics() {
    const data = this.getData();
    return data ? data.dailyMetrics : [];
  }

  /**
   * Get services
   */
  getServices() {
    const data = this.getData();
    return data ? data.services : [];
  }

  /**
   * Format currency
   */
  formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  }

  /**
   * Format number with commas
   */
  formatNumber(num) {
    return new Intl.NumberFormat('en-IN').format(num);
  }

  /**
   * Sample data for development
   */
  getSampleData() {
    return {
      summary: {
        totalSpend: 662500,
        totalImpressions: 1245680,
        totalClicks: 55420,
        ctr: 4.45,
        totalLeads: 465,
        qualifiedLeads: 342,
        qualificationRate: 73.5,
        cpl: 1425,
        cpql: 1937,
        revenue: 26500000,
        roi: 300
      },
      campaigns: [],
      clients: [],
      keywords: [],
      leadsBySource: [],
      dailyMetrics: [],
      services: []
    };
  }
}

// Create global instance
const dataLoader = new DataLoader();

// Export for use in other scripts
if (typeof window !== 'undefined') {
  window.dataLoader = dataLoader;
}
