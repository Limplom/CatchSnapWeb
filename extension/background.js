/**
 * CatchSnap - Background Service Worker
 * Handles downloads and cross-script communication
 */

// Default settings
const DEFAULT_SETTINGS = {
  enabled: true,
  downloadMode: 'auto',
  autoImages: true,
  autoVideos: true,
  showOverlay: true,
  downloadedHashes: [],
  stats: {
    totalDownloads: 0,
    todayDownloads: 0,
    lastDownloadDate: null
  }
};

// Initialize default settings on install
chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === 'install') {
    await chrome.storage.local.set(DEFAULT_SETTINGS);
    console.log('[CatchSnap] Extension installed, defaults set');
  }
});

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[CatchSnap BG] Received message:', message.type);

  if (message.type === 'download') {
    // Support both old format (message.data) and new format (message.dataUrl, message.filename)
    const downloadData = message.data || {
      blob: message.dataUrl,
      filename: message.filename,
      subfolder: null,
      mimeType: null
    };

    handleDownload(downloadData)
      .then((result) => {
        console.log('[CatchSnap BG] Download success:', result);
        sendResponse({ success: true, downloadId: result });
      })
      .catch((error) => {
        console.error('[CatchSnap BG] Download failed:', error);
        sendResponse({ success: false, error: error.message });
      });
    return true; // Keep channel open for async response
  }

  if (message.type === 'getStats') {
    getStats().then(sendResponse);
    return true;
  }

  if (message.type === 'openDownloadsFolder') {
    chrome.downloads.showDefaultFolder();
    sendResponse({ success: true });
  }
});

/**
 * Handle download request from content script
 * @param {Object} data - Download data
 * @param {string} data.blob - Base64 encoded blob data (data URL)
 * @param {string} data.filename - Filename (may include subfolder info)
 * @param {string} data.subfolder - Subfolder name (user) - optional
 * @param {string} data.mimeType - MIME type - optional
 */
async function handleDownload(data) {
  console.log('[CatchSnap BG] handleDownload called with:', {
    filename: data.filename,
    subfolder: data.subfolder,
    mimeType: data.mimeType,
    blobLength: data.blob?.length
  });

  try {
    const { blob: base64Data, filename, subfolder } = data;

    if (!base64Data) {
      throw new Error('No blob data received');
    }

    if (!base64Data.startsWith('data:')) {
      throw new Error('Invalid data URL format');
    }

    // Build download path - sanitize for filesystem
    let downloadPath;
    if (subfolder) {
      // Old format with separate subfolder
      const safeSubfolder = subfolder.replace(/[<>:"/\\|?*]/g, '_');
      const safeFilename = (filename || 'media').replace(/[<>:"/\\|?*]/g, '_');
      downloadPath = `CatchSnap/${safeSubfolder}/${safeFilename}`;
    } else {
      // New format - filename already contains user info (CatchSnap_username_hash.ext)
      const safeFilename = (filename || 'media').replace(/[<>:"/\\|?*]/g, '_');
      // Extract username from filename pattern: CatchSnap_username_hash.ext
      const match = safeFilename.match(/^CatchSnap_(.+?)_[a-f0-9]+\.\w+$/i);
      if (match) {
        const username = match[1];
        downloadPath = `CatchSnap/${username}/${safeFilename}`;
      } else {
        downloadPath = `CatchSnap/${safeFilename}`;
      }
    }

    console.log('[CatchSnap BG] Download path:', downloadPath);

    // Start download directly from data URL
    const downloadId = await chrome.downloads.download({
      url: base64Data,
      filename: downloadPath,
      saveAs: false,
      conflictAction: 'uniquify'
    });

    console.log(`[CatchSnap BG] Download started: ${downloadPath} (ID: ${downloadId})`);

    return downloadId;

  } catch (error) {
    console.error('[CatchSnap BG] Download error:', error);
    throw error;
  }
}

/**
 * Get download statistics
 * @returns {Promise<Object>}
 */
async function getStats() {
  const result = await chrome.storage.local.get(['stats']);
  const stats = result.stats || DEFAULT_SETTINGS.stats;

  const today = new Date().toDateString();
  if (stats.lastDownloadDate !== today) {
    stats.todayDownloads = 0;
  }

  return stats;
}

/**
 * Update badge with download count
 * @param {number} count
 */
function updateBadge(count) {
  if (count > 0) {
    chrome.action.setBadgeText({ text: count.toString() });
    chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
  } else {
    chrome.action.setBadgeText({ text: '' });
  }
}

// Listen for storage changes to update badge
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'local' && changes.stats) {
    const newStats = changes.stats.newValue;
    if (newStats && newStats.todayDownloads > 0) {
      updateBadge(newStats.todayDownloads);
    }
  }
});

// Listen for download completion events
chrome.downloads.onChanged.addListener((delta) => {
  if (delta.state && delta.state.current === 'complete') {
    console.log(`[CatchSnap BG] Download completed: ${delta.id}`);
  } else if (delta.error) {
    console.error(`[CatchSnap BG] Download error: ${delta.error.current}`);
  }
});

console.log('[CatchSnap] Background service worker loaded');
