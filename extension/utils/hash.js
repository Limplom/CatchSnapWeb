/**
 * CatchSnap - Hash Utilities
 * SHA256 hashing for media deduplication
 */

const CatchSnapHash = {
  /**
   * Compute SHA256 hash of a Blob
   * @param {Blob} blob - The blob to hash
   * @returns {Promise<string>} - Hex string of the hash
   */
  async computeHash(blob) {
    const arrayBuffer = await blob.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return hashHex;
  },

  /**
   * Compute a quick hash from blob size and first bytes (for fast dedup check)
   * @param {Blob} blob - The blob to hash
   * @returns {Promise<string>} - Quick hash string
   */
  async computeQuickHash(blob) {
    const size = blob.size;
    const slice = blob.slice(0, Math.min(1024, size));
    const arrayBuffer = await slice.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.slice(0, 8).map(b => b.toString(16).padStart(2, '0')).join('');
    return `${size}-${hashHex}`;
  }
};

// Make available globally for content scripts
window.CatchSnapHash = CatchSnapHash;
