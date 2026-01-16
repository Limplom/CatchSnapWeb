/**
 * CatchSnap - Storage Utilities
 * Chrome Storage API wrapper for settings and history
 */

const CatchSnapStorage = {
  // Default settings
  defaults: {
    enabled: true,
    downloadMode: 'auto', // 'auto', 'manual', 'hybrid'
    autoImages: true,
    autoVideos: true,
    showOverlay: true,
    downloadedHashes: [],
    stats: {
      totalDownloads: 0,
      todayDownloads: 0,
      lastDownloadDate: null
    }
  },

  /**
   * Get all settings
   * @returns {Promise<Object>}
   */
  async getSettings() {
    return new Promise((resolve) => {
      chrome.storage.local.get(this.defaults, (result) => {
        resolve(result);
      });
    });
  },

  /**
   * Get a specific setting
   * @param {string} key
   * @returns {Promise<any>}
   */
  async get(key) {
    const settings = await this.getSettings();
    return settings[key];
  },

  /**
   * Set a specific setting
   * @param {string} key
   * @param {any} value
   * @returns {Promise<void>}
   */
  async set(key, value) {
    return new Promise((resolve) => {
      chrome.storage.local.set({ [key]: value }, resolve);
    });
  },

  /**
   * Check if a hash has been downloaded before
   * @param {string} hash
   * @returns {Promise<boolean>}
   */
  async isDownloaded(hash) {
    const hashes = await this.get('downloadedHashes') || [];
    return hashes.includes(hash);
  },

  /**
   * Mark a hash as downloaded
   * @param {string} hash
   * @returns {Promise<void>}
   */
  async markDownloaded(hash) {
    const hashes = await this.get('downloadedHashes') || [];
    if (!hashes.includes(hash)) {
      hashes.push(hash);
      // Keep only last 10000 hashes to prevent storage bloat
      if (hashes.length > 10000) {
        hashes.shift();
      }
      await this.set('downloadedHashes', hashes);
    }
  },

  /**
   * Increment download statistics
   * @returns {Promise<void>}
   */
  async incrementStats() {
    const stats = await this.get('stats') || this.defaults.stats;
    const today = new Date().toDateString();

    if (stats.lastDownloadDate !== today) {
      stats.todayDownloads = 0;
      stats.lastDownloadDate = today;
    }

    stats.totalDownloads++;
    stats.todayDownloads++;

    await this.set('stats', stats);
  },

  /**
   * Get download statistics
   * @returns {Promise<Object>}
   */
  async getStats() {
    const stats = await this.get('stats') || this.defaults.stats;
    const today = new Date().toDateString();

    // Reset today count if it's a new day
    if (stats.lastDownloadDate !== today) {
      stats.todayDownloads = 0;
    }

    return stats;
  },

  /**
   * Clear download history (hashes)
   * @returns {Promise<void>}
   */
  async clearHistory() {
    await this.set('downloadedHashes', []);
  },

  /**
   * Reset all settings to defaults
   * @returns {Promise<void>}
   */
  async resetAll() {
    return new Promise((resolve) => {
      chrome.storage.local.clear(resolve);
    });
  }
};

// Make available globally for content scripts
window.CatchSnapStorage = CatchSnapStorage;
