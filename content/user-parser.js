/**
 * CatchSnap - User Parser
 * Extract username and UUID from Snapchat Web DOM/URL
 */

const CatchSnapUserParser = {
  // Cache for user info to avoid repeated DOM queries
  cache: new Map(),
  cacheTimeout: 5000, // 5 seconds

  /**
   * Extract UUID from current page URL
   * URL format: https://web.snapchat.com/web/{UUID}
   * @returns {string | null}
   */
  extractUUID() {
    const url = window.location.href;
    const match = url.match(/\/web\/([a-f0-9-]+)/i);
    return match ? match[1] : null;
  },

  /**
   * Extract username from the Snap Viewer header (above the snap image)
   * This is more reliable than URL-based extraction when viewing snaps
   * @param {HTMLElement} mediaElement - The image or video element
   * @returns {string | null}
   */
  extractUsernameFromSnapViewer(mediaElement) {
    if (!mediaElement) return null;

    // Walk up the DOM to find the snap viewer container
    let current = mediaElement;
    for (let i = 0; i < 25; i++) {
      if (!current || !current.parentElement) break;
      current = current.parentElement;

      // Strategy 1: Look for Snapchat's specific username class (ROW7N)
      // This is the most reliable method
      const usernameElement = current.querySelector('.ROW7N');
      if (usernameElement) {
        const text = usernameElement.textContent?.trim();
        if (text && text.length >= 2 && text.length <= 30) {
          console.log('[CatchSnap] Found username from ROW7N class:', text);
          return text;
        }
      }

      // Strategy 2: Look for other common header selectors as fallback
      const headerSelectors = [
        '[class*="header"] span',
        '[class*="Header"] span',
        '[class*="title"] span',
        '[class*="name"]',
        '[class*="Name"]',
        '[class*="user"] span',
        '[class*="User"] span',
      ];

      for (const selector of headerSelectors) {
        try {
          const elements = current.querySelectorAll(selector);
          for (const el of elements) {
            // Check if this looks like a username
            const text = el.textContent?.trim();
            if (text &&
                text.length >= 2 &&
                text.length <= 30 &&
                !text.includes(':') && // Not a timestamp
                !text.match(/^\d+$/) && // Not just numbers
                !text.match(/^vor\s/i) && // Not "vor X Min." (German time)
                !text.match(/^\d+\s*(min|sec|h|m|s)/i) && // Not time ago
                !text.includes('Download') &&
                !text.includes('Snap') &&
                el.closest('button') === null // Not inside a button
            ) {
              // Check if element is positioned at the top (header area)
              const rect = el.getBoundingClientRect();
              const parentRect = current.getBoundingClientRect();

              // Username should be in top portion of the container
              if (rect.top < parentRect.top + 100) {
                console.log('[CatchSnap] Found username from header selector:', text);
                return text;
              }
            }
          }
        } catch (e) {
          continue;
        }
      }
    }

    return null;
  },

  /**
   * Extract username from DOM
   * Based on Snapchat Web DOM structure
   * @param {string | null} uuid - Optional UUID for more specific selector
   * @returns {string | null}
   */
  extractUsername(uuid = null) {
    // Strategy 1: UUID-based selector (most reliable)
    if (uuid) {
      try {
        const titleId = `title-${uuid}`;
        const titleElement = document.getElementById(titleId);
        if (titleElement) {
          const nonIntlSpan = titleElement.querySelector('.nonIntl');
          if (nonIntlSpan && nonIntlSpan.textContent) {
            const username = nonIntlSpan.textContent.trim();
            if (username) {
              return username;
            }
          }
        }
      } catch (e) {
        console.debug('[CatchSnap] UUID-based selector failed:', e);
      }
    }

    // Strategy 2: Fallback selectors
    const selectors = [
      '.nonIntl',
      '[data-testid="chat-header-name"]',
      '.chat-header__name',
      '[aria-label*="conversation"]',
      'header [class*="name"]',
      '[class*="ChatHeader"] [class*="Name"]'
    ];

    for (const selector of selectors) {
      try {
        const element = document.querySelector(selector);
        if (element && element.textContent) {
          const username = element.textContent.trim();
          if (username && username.length > 0 && username.length < 50) {
            return username;
          }
        }
      } catch (e) {
        continue;
      }
    }

    return null;
  },

  /**
   * Get current user info (UUID + username)
   * Uses caching to avoid repeated DOM queries
   * @returns {{uuid: string | null, username: string | null, subfolder: string}}
   */
  getCurrentUser() {
    const uuid = this.extractUUID();
    const cacheKey = uuid || 'no-uuid';

    // Check cache
    const cached = this.cache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp) < this.cacheTimeout) {
      return cached.data;
    }

    // Extract fresh data
    const username = this.extractUsername(uuid);

    const data = {
      uuid,
      username,
      subfolder: this.buildSubfolder(username, uuid)
    };

    // Update cache
    this.cache.set(cacheKey, {
      data,
      timestamp: Date.now()
    });

    return data;
  },

  /**
   * Get user info for a specific media element
   * Extracts username from the snap viewer header above the media
   * @param {HTMLElement} mediaElement - The image or video element
   * @returns {{uuid: string | null, username: string | null, subfolder: string}}
   */
  getUserForMedia(mediaElement) {
    // Extract username from the snap viewer header near the media element
    const usernameFromViewer = this.extractUsernameFromSnapViewer(mediaElement);
    const uuid = this.extractUUID();

    if (usernameFromViewer) {
      return {
        uuid,
        username: usernameFromViewer,
        subfolder: this.buildSubfolder(usernameFromViewer, null)
      };
    }

    // Don't fall back to chat header — it shows the wrong user when viewing
    // someone else's snap while having a different chat open
    console.log('[CatchSnap] Could not extract username from snap viewer, using unknown');
    return {
      uuid,
      username: null,
      subfolder: uuid ? `user_${uuid.substring(0, 8)}` : 'unknown'
    };
  },

  /**
   * Build subfolder name from username and UUID
   * Format: "Username_UUID" or "unknown" as fallback
   * @param {string | null} username
   * @param {string | null} uuid
   * @returns {string}
   */
  buildSubfolder(username, uuid) {
    // Sanitize for filesystem
    const sanitize = (str) => {
      if (!str) return null;
      return str.replace(/[<>:"/\\|?*]/g, '_').trim();
    };

    const cleanUsername = sanitize(username);
    const cleanUuid = sanitize(uuid);

    if (cleanUsername && cleanUuid) {
      // Short UUID (first 8 chars) for cleaner folder names
      const shortUuid = cleanUuid.substring(0, 8);
      return `${cleanUsername}_${shortUuid}`;
    } else if (cleanUsername) {
      return cleanUsername;
    } else if (cleanUuid) {
      return `user_${cleanUuid.substring(0, 8)}`;
    } else {
      return 'unknown';
    }
  },

  /**
   * Clear the cache (useful when navigating between chats)
   */
  clearCache() {
    this.cache.clear();
  }
};

// Clear cache on URL changes (navigation between chats)
let lastUrl = window.location.href;
const urlObserver = new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    CatchSnapUserParser.clearCache();
  }
});

// Start observing for SPA navigation
if (document.body) {
  urlObserver.observe(document.body, { childList: true, subtree: true });
}

// Make available globally
window.CatchSnapUserParser = CatchSnapUserParser;
