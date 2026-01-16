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
  const openFolderBtn = document.getElementById('openFolder');
  const clearHistoryBtn = document.getElementById('clearHistory');

  // Load current settings
  async function loadSettings() {
    const settings = await chrome.storage.local.get({
      enabled: true,
      autoImages: false,
      autoVideos: false,
      stats: { totalDownloads: 0, todayDownloads: 0 }
    });

    // Update toggle
    enableToggle.checked = settings.enabled;
    updateStatus(settings.enabled);

    // Update auto-download checkboxes
    autoImages.checked = settings.autoImages;
    autoVideos.checked = settings.autoVideos;

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
    const tabs1 = await chrome.tabs.query({ url: '*://web.snapchat.com/*' });
    const tabs2 = await chrome.tabs.query({ url: '*://snapchat.com/web/*' });
    const tabs3 = await chrome.tabs.query({ url: '*://*.snapchat.com/web/*' });
    const allTabs = [...tabs1, ...tabs2, ...tabs3];
    for (const tab of allTabs) {
      try {
        chrome.tabs.sendMessage(tab.id, { type: 'settingsUpdated' });
      } catch (e) {
        // Tab might not have content script
      }
    }
  }

  // Toggle handler
  enableToggle.addEventListener('change', async () => {
    const enabled = enableToggle.checked;
    await saveSetting('enabled', enabled);
    updateStatus(enabled);

    // Notify content scripts directly about toggle (all URL patterns)
    const tabs1 = await chrome.tabs.query({ url: '*://web.snapchat.com/*' });
    const tabs2 = await chrome.tabs.query({ url: '*://snapchat.com/web/*' });
    const tabs3 = await chrome.tabs.query({ url: '*://*.snapchat.com/web/*' });
    const allTabs = [...tabs1, ...tabs2, ...tabs3];
    for (const tab of allTabs) {
      try {
        chrome.tabs.sendMessage(tab.id, { type: 'toggle', enabled });
      } catch (e) {
        // Tab might not have content script
      }
    }
  });

  // Auto-download checkbox handlers
  autoImages.addEventListener('change', async () => {
    await saveSetting('autoImages', autoImages.checked);
  });

  autoVideos.addEventListener('change', async () => {
    await saveSetting('autoVideos', autoVideos.checked);
  });

  // Open downloads folder
  openFolderBtn.addEventListener('click', () => {
    chrome.runtime.sendMessage({ type: 'openDownloadsFolder' });
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
