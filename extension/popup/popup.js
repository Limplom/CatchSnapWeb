/**
 * CatchSnap - Popup Script
 * UI logic for the extension popup
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Elements
  const enableToggle = document.getElementById('enableToggle');
  const statusDot = document.querySelector('.status-dot');
  const statusText = document.querySelector('.status-text');
  const todayCount = document.getElementById('todayCount');
  const totalCount = document.getElementById('totalCount');
  const autoImages = document.getElementById('autoImages');
  const autoVideos = document.getElementById('autoVideos');
  const allowRedownload = document.getElementById('allowRedownload');
  const openFolderBtn = document.getElementById('openFolder');
  const clearHistoryBtn = document.getElementById('clearHistory');

  // Load current settings
  async function loadSettings() {
    // Use the SAME defaults as in storage.js to ensure consistency
    const settings = await chrome.storage.local.get({
      enabled: true,
      autoImages: true,  // Changed from false to true to match storage.js defaults
      autoVideos: true,  // Changed from false to true to match storage.js defaults
      showOverlay: true,
      allowRedownload: false,
      stats: { totalDownloads: 0, todayDownloads: 0 }
    });

    console.log('[CatchSnap DEBUG] Popup loaded settings:', settings);

    // Update toggle
    enableToggle.checked = settings.enabled;
    updateStatus(settings.enabled);

    // Update auto-download checkboxes
    autoImages.checked = settings.autoImages;
    autoVideos.checked = settings.autoVideos;
    allowRedownload.checked = settings.allowRedownload;

    // Update stats
    updateStats(settings.stats);
  }

  // Update status display
  function updateStatus(enabled) {
    if (enabled) {
      document.body.classList.remove('disabled');
      statusDot.classList.add('active');
      statusDot.classList.remove('inactive');
      statusText.textContent = 'Active on Snapchat Web';
    } else {
      document.body.classList.add('disabled');
      statusDot.classList.remove('active');
      statusDot.classList.add('inactive');
      statusText.textContent = 'Disabled';
    }
  }

  // Update stats display
  function updateStats(stats) {
    const today = new Date().toDateString();
    const todayDownloads = stats.lastDownloadDate === today ? stats.todayDownloads : 0;

    todayCount.textContent = todayDownloads;
    totalCount.textContent = stats.totalDownloads;
  }

  // Save setting
  async function saveSetting(key, value) {
    await chrome.storage.local.set({ [key]: value });

    // Notify content scripts (all URL patterns)
    try {
      const tabs1 = await chrome.tabs.query({ url: '*://web.snapchat.com/*' });
      const tabs2 = await chrome.tabs.query({ url: '*://snapchat.com/web/*' });
      const tabs3 = await chrome.tabs.query({ url: '*://*.snapchat.com/web/*' });
      const allTabs = [...tabs1, ...tabs2, ...tabs3];

      console.log('[CatchSnap DEBUG] Notifying', allTabs.length, 'tabs about settings update');

      for (const tab of allTabs) {
        try {
          await chrome.tabs.sendMessage(tab.id, { type: 'settingsUpdated' });
        } catch (e) {
          // Tab might not have content script - silently ignore
          console.log('[CatchSnap DEBUG] Could not notify tab', tab.id, '(no content script)');
        }
      }
    } catch (e) {
      console.log('[CatchSnap DEBUG] Error querying tabs:', e.message);
    }
  }

  // Toggle handler
  enableToggle.addEventListener('change', async () => {
    const enabled = enableToggle.checked;
    await saveSetting('enabled', enabled);
    updateStatus(enabled);

    // Notify content scripts directly about toggle (all URL patterns)
    try {
      const tabs1 = await chrome.tabs.query({ url: '*://web.snapchat.com/*' });
      const tabs2 = await chrome.tabs.query({ url: '*://snapchat.com/web/*' });
      const tabs3 = await chrome.tabs.query({ url: '*://*.snapchat.com/web/*' });
      const allTabs = [...tabs1, ...tabs2, ...tabs3];

      for (const tab of allTabs) {
        try {
          await chrome.tabs.sendMessage(tab.id, { type: 'toggle', enabled });
        } catch (e) {
          // Tab might not have content script - silently ignore
        }
      }
    } catch (e) {
      console.log('[CatchSnap DEBUG] Error notifying tabs about toggle:', e.message);
    }
  });

  // Auto-download checkbox handlers
  autoImages.addEventListener('change', async () => {
    console.log('[CatchSnap DEBUG] autoImages changed to:', autoImages.checked);
    await saveSetting('autoImages', autoImages.checked);
  });

  autoVideos.addEventListener('change', async () => {
    console.log('[CatchSnap DEBUG] autoVideos changed to:', autoVideos.checked);
    await saveSetting('autoVideos', autoVideos.checked);
  });

  allowRedownload.addEventListener('change', async () => {
    console.log('[CatchSnap DEBUG] allowRedownload changed to:', allowRedownload.checked);
    await saveSetting('allowRedownload', allowRedownload.checked);
  });

  // Open downloads folder
  openFolderBtn.addEventListener('click', async () => {
    try {
      await chrome.runtime.sendMessage({ type: 'openDownloadsFolder' });
    } catch (e) {
      console.log('[CatchSnap DEBUG] Error opening downloads folder:', e.message);
    }
  });

  // Clear history
  clearHistoryBtn.addEventListener('click', async () => {
    if (confirm('Clear download history? This will allow re-downloading of previously downloaded media.')) {
      await chrome.storage.local.set({ downloadedHashes: [] });
      alert('History cleared!');
    }
  });

  // Listen for stats updates
  chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'local' && changes.stats) {
      updateStats(changes.stats.newValue);
    }
  });

  // Initial load
  await loadSettings();

  // Check if on Snapchat Web
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const isSnapchatWeb = tab?.url?.includes('web.snapchat.com') || tab?.url?.includes('snapchat.com/web');
  if (!isSnapchatWeb) {
    statusText.textContent = 'Not on Snapchat Web';
    statusDot.classList.remove('active');
    statusDot.classList.add('inactive');
  }
});
