/**
 * CatchSnap - Content Script Entry Point
 * Main controller for media capture on Snapchat Web
 */

(async function() {
  'use strict';

  console.log('[CatchSnap] Content script loaded on', window.location.href);

  // State
  let isEnabled = true;
  let settings = null;

  /**
   * Load settings from storage
   */
  async function loadSettings() {
    settings = await window.CatchSnapStorage.getSettings();
    isEnabled = settings.enabled;
    console.log('[CatchSnap DEBUG] ⚙️ Settings loaded:', {
      enabled: isEnabled,
      autoImages: settings.autoImages,
      autoVideos: settings.autoVideos,
      showOverlay: settings.showOverlay,
      downloadMode: settings.downloadMode
    });
  }

  /**
   * Handle detected image
   * @param {HTMLImageElement} img
   */
  async function handleImage(img) {
    console.log('[CatchSnap DEBUG] handleImage called', {
      isEnabled,
      autoImages: settings.autoImages,
      showOverlay: settings.showOverlay,
      imgSrc: img.src?.substring(0, 80)
    });

    if (!isEnabled) {
      console.log('[CatchSnap DEBUG] ❌ Extension disabled, skipping');
      return;
    }

    // Check if auto-download is enabled for images
    if (!settings.autoImages) {
      console.log('[CatchSnap DEBUG] 🔘 Manual mode - calling addDownloadOverlay');
      // Show manual download button
      addDownloadOverlay(img, 'image');
      return;
    }

    console.log('[CatchSnap DEBUG] ⬇️ Auto mode - downloading directly');
    // Auto download
    await downloadImage(img);
  }

  /**
   * Handle detected video
   * @param {HTMLVideoElement} video
   */
  async function handleVideo(video) {
    if (!isEnabled) return;

    // Check if auto-download is enabled for videos
    if (!settings.autoVideos) {
      // Show manual download button
      addDownloadOverlay(video, 'video');
      return;
    }

    // Auto download
    await downloadVideo(video);
  }

  /**
   * Download an image
   * @param {HTMLImageElement} img
   * @param {boolean} allowRedownload - Allow re-downloading with suffix
   */
  async function downloadImage(img, allowRedownload = false) {
    try {
      console.log('[CatchSnap] Starting image capture...');

      const result = await window.CatchSnapImageCapture.captureImage(img);
      if (!result) {
        console.log('[CatchSnap] Image capture returned null');
        return false;
      }

      console.log('[CatchSnap] Image captured:', {
        hash: result.hash?.substring(0, 8),
        size: result.blob?.size,
        type: result.mimeType
      });

      // Check if already downloaded
      const isDownloaded = await window.CatchSnapStorage.isDownloaded(result.hash);
      if (isDownloaded && !allowRedownload) {
        console.log('[CatchSnap] Image already downloaded (duplicate), re-download disabled');
        return false;
      }

      // Get user info for folder structure - use the media element for accurate username
      const user = window.CatchSnapUserParser.getUserForMedia(img);
      console.log('[CatchSnap] User info:', user);

      // Determine file extension
      const ext = result.mimeType.includes('png') ? 'png' : 'jpg';
      let filename = `CatchSnap_${user.subfolder}_${result.hash.substring(0, 12)}.${ext}`;

      // Add suffix for re-downloads
      if (isDownloaded && allowRedownload) {
        const downloadCount = await getDownloadCount(result.hash);
        const baseName = `CatchSnap_${user.subfolder}_${result.hash.substring(0, 12)}`;
        filename = `${baseName}_${downloadCount}.${ext}`;
        console.log('[CatchSnap DEBUG] Re-download with suffix:', filename);
      }

      // Convert blob to data URL for background script
      const dataUrl = await blobToBase64(result.blob);
      console.log('[CatchSnap] Data URL created, length:', dataUrl.length);

      // Use chrome.downloads API via background script
      try {
        const response = await chrome.runtime.sendMessage({
          type: 'download',
          dataUrl: dataUrl,
          filename: filename
        });
        console.log('[CatchSnap] Background response:', response);

        if (!response || !response.success) {
          throw new Error(response?.error || 'Download failed');
        }
      } catch (msgError) {
        console.log('[CatchSnap] Background download failed, trying direct method:', msgError);

        // Fallback: Direct download using anchor element
        const url = URL.createObjectURL(result.blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }

      // Mark as downloaded (only first time, not for re-downloads)
      if (!isDownloaded) {
        await window.CatchSnapStorage.markDownloaded(result.hash);
      } else if (allowRedownload) {
        await incrementDownloadCount(result.hash);
      }
      await window.CatchSnapStorage.incrementStats();

      console.log(`[CatchSnap] Image downloaded: ${filename}`);
      return true;

    } catch (error) {
      console.error('[CatchSnap] Image download error:', error);
      return false;
    }
  }

  /**
   * Download a video
   * @param {HTMLVideoElement} video
   * @param {boolean} allowRedownload - Allow re-downloading with suffix
   */
  async function downloadVideo(video, allowRedownload = false) {
    try {
      console.log('[CatchSnap] Starting video capture...');

      const result = await window.CatchSnapVideoCapture.captureVideo(video);
      if (!result) {
        console.log('[CatchSnap] Video capture returned null');
        return false;
      }

      console.log('[CatchSnap] Video captured:', {
        hash: result.hash?.substring(0, 8),
        size: result.blob?.size,
        type: result.mimeType
      });

      // Check if already downloaded
      const isDownloaded = await window.CatchSnapStorage.isDownloaded(result.hash);
      if (isDownloaded && !allowRedownload) {
        console.log('[CatchSnap] Video already downloaded (duplicate), re-download disabled');
        return false;
      }

      // Get user info for folder structure - use the media element for accurate username
      const user = window.CatchSnapUserParser.getUserForMedia(video);

      // Determine file extension
      const ext = window.CatchSnapVideoCapture.getExtension(result.mimeType);
      let filename = `CatchSnap_${user.subfolder}_${result.hash.substring(0, 12)}.${ext}`;

      // Add suffix for re-downloads
      if (isDownloaded && allowRedownload) {
        const downloadCount = await getDownloadCount(result.hash);
        const baseName = `CatchSnap_${user.subfolder}_${result.hash.substring(0, 12)}`;
        filename = `${baseName}_${downloadCount}.${ext}`;
        console.log('[CatchSnap DEBUG] Re-download video with suffix:', filename);
      }

      // Convert blob to data URL for background script
      const dataUrl = await blobToBase64(result.blob);
      console.log('[CatchSnap] Video Data URL created, length:', dataUrl.length);

      // Use chrome.downloads API via background script
      try {
        const response = await chrome.runtime.sendMessage({
          type: 'download',
          dataUrl: dataUrl,
          filename: filename
        });
        console.log('[CatchSnap] Background response:', response);

        if (!response || !response.success) {
          throw new Error(response?.error || 'Download failed');
        }
      } catch (msgError) {
        console.log('[CatchSnap] Background download failed, trying direct method:', msgError);

        // Fallback: Direct download using anchor element
        const url = URL.createObjectURL(result.blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }

      // Mark as downloaded (only first time, not for re-downloads)
      if (!isDownloaded) {
        await window.CatchSnapStorage.markDownloaded(result.hash);
      } else if (allowRedownload) {
        await incrementDownloadCount(result.hash);
      }
      await window.CatchSnapStorage.incrementStats();

      console.log(`[CatchSnap] Video downloaded: ${filename}`);
      return true;

    } catch (error) {
      console.error('[CatchSnap] Video download error:', error);
      return false;
    }
  }

  /**
   * Get download count for a hash (for re-download suffix)
   * @param {string} hash
   * @returns {Promise<number>}
   */
  async function getDownloadCount(hash) {
    const key = `downloadCount_${hash}`;
    const result = await chrome.storage.local.get(key);
    return result[key] || 0;
  }

  /**
   * Increment download count for a hash
   * @param {string} hash
   * @returns {Promise<void>}
   */
  async function incrementDownloadCount(hash) {
    const key = `downloadCount_${hash}`;
    const count = await getDownloadCount(hash);
    await chrome.storage.local.set({ [key]: count + 1 });
  }

  /**
   * Add download overlay button to media element (for manual mode)
   * @param {HTMLElement} element
   * @param {string} type - 'image' or 'video'
   */
  async function addDownloadOverlay(element, type) {
    console.log('[CatchSnap DEBUG] addDownloadOverlay called', {
      type,
      showOverlay: settings.showOverlay,
      hasOverlay: element.dataset.catchsnapOverlay,
      elementTag: element.tagName
    });

    if (!settings.showOverlay) {
      console.log('[CatchSnap DEBUG] ❌ showOverlay is false, aborting');
      return;
    }

    // Check if overlay already exists
    if (element.dataset.catchsnapOverlay === 'true') {
      console.log('[CatchSnap DEBUG] ❌ Overlay already exists, skipping');
      return;
    }
    element.dataset.catchsnapOverlay = 'true';

    console.log('[CatchSnap DEBUG] ✅ Adding download overlay to', type);

    // Check if already downloaded (compute hash first)
    let isAlreadyDownloaded = false;
    let mediaHash = null;
    try {
      if (type === 'image') {
        const result = await window.CatchSnapImageCapture.captureImage(element);
        if (result && result.hash) {
          mediaHash = result.hash;
          isAlreadyDownloaded = await window.CatchSnapStorage.isDownloaded(mediaHash);
        }
      } else if (type === 'video') {
        const result = await window.CatchSnapVideoCapture.captureVideo(element);
        if (result && result.hash) {
          mediaHash = result.hash;
          isAlreadyDownloaded = await window.CatchSnapStorage.isDownloaded(mediaHash);
        }
      }
      console.log('[CatchSnap DEBUG] Hash check:', { mediaHash: mediaHash?.substring(0, 12), isAlreadyDownloaded });
    } catch (e) {
      console.log('[CatchSnap DEBUG] Hash check failed:', e.message);
    }

    // Find the best container - look for Snapchat's media container
    let container = element.parentElement;

    // Try to find a better positioned container
    let searchElement = element;
    for (let i = 0; i < 5; i++) {
      if (!searchElement.parentElement) break;
      searchElement = searchElement.parentElement;
      const style = window.getComputedStyle(searchElement);
      if (style.position === 'relative' || style.position === 'absolute') {
        container = searchElement;
        break;
      }
    }

    // Create overlay container
    const overlay = document.createElement('div');
    overlay.className = 'catchsnap-overlay';

    // Button text and color based on download status
    const buttonText = isAlreadyDownloaded ? '✓ Downloaded' : 'Download';
    const buttonColor = isAlreadyDownloaded ? '#34c759' : '#ff3b30';

    overlay.innerHTML = `
      <button class="catchsnap-download-btn" title="Download with CatchSnap">
        ${buttonText}
      </button>
    `;

    // Style the overlay - always visible, red button like reference image
    overlay.style.cssText = `
      position: absolute;
      top: 12px;
      right: 12px;
      z-index: 999999;
      pointer-events: auto;
    `;

    const btn = overlay.querySelector('.catchsnap-download-btn');
    btn.style.cssText = `
      background: ${buttonColor};
      border: none;
      border-radius: 8px;
      padding: 8px 16px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      font-weight: 600;
      transition: all 0.2s;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    `;

    // Store initial state
    btn.dataset.initialColor = buttonColor;
    btn.dataset.initialText = buttonText;
    btn.dataset.isDownloaded = isAlreadyDownloaded;
    btn.dataset.mediaHash = mediaHash || '';

    // Hover effect - only for non-downloaded items
    btn.addEventListener('mouseenter', () => {
      if (btn.dataset.isDownloaded === 'false') {
        btn.style.background = '#ff5544';
        btn.style.transform = 'scale(1.05)';
      }
    });
    btn.addEventListener('mouseleave', () => {
      if (btn.dataset.isDownloaded === 'false') {
        btn.style.background = btn.dataset.initialColor;
        btn.style.transform = 'scale(1)';
      }
    });

    // Click handler
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();

      // Check if already downloaded and re-download not allowed
      const currentlyDownloaded = btn.dataset.isDownloaded === 'true';
      const allowRedownload = settings.allowRedownload;

      if (currentlyDownloaded && !allowRedownload) {
        console.log('[CatchSnap DEBUG] Already downloaded, re-download disabled');
        // Flash the button
        const originalBg = btn.style.background;
        btn.style.background = '#ffcc00';
        setTimeout(() => {
          btn.style.background = originalBg;
        }, 300);
        return;
      }

      // Show downloading state
      btn.textContent = 'Downloading...';
      btn.style.background = '#ff9500';

      try {
        let success = false;
        if (type === 'image') {
          success = await downloadImage(element, allowRedownload);
        } else {
          success = await downloadVideo(element, allowRedownload);
        }

        if (success) {
          // Success state
          btn.textContent = '✓ Downloaded';
          btn.style.background = '#34c759';
          btn.dataset.isDownloaded = 'true';
          btn.dataset.initialColor = '#34c759';
          btn.dataset.initialText = '✓ Downloaded';

          console.log('[CatchSnap DEBUG] Download successful, button stays green');
        } else {
          // Failed or duplicate
          btn.textContent = btn.dataset.initialText;
          btn.style.background = btn.dataset.initialColor;
        }

      } catch (error) {
        console.error('[CatchSnap DEBUG] Download error:', error);
        // Error state
        btn.textContent = 'Error';
        btn.style.background = '#ff3b30';

        setTimeout(() => {
          btn.textContent = btn.dataset.initialText;
          btn.style.background = btn.dataset.initialColor;
        }, 2000);
      }
    });

    // Add to container
    if (container) {
      console.log('[CatchSnap DEBUG] 📍 Found container, appending overlay', {
        containerTag: container.tagName,
        containerClass: container.className?.substring(0, 80),
        containerPosition: window.getComputedStyle(container).position
      });
      container.style.position = 'relative';
      container.appendChild(overlay);
      console.log('[CatchSnap DEBUG] ✅ Overlay added successfully!');
    } else {
      console.error('[CatchSnap DEBUG] ❌ Could not find container for overlay!');
    }
  }

  /**
   * Convert Blob to base64 string for message passing
   * @param {Blob} blob
   * @returns {Promise<string>}
   */
  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  /**
   * Listen for messages from popup/background
   */
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('[CatchSnap DEBUG] 📨 Message received:', message);

    if (message.type === 'toggle') {
      isEnabled = message.enabled;
      console.log('[CatchSnap DEBUG] ⏯️ Extension toggled:', isEnabled);
    } else if (message.type === 'settingsUpdated') {
      console.log('[CatchSnap DEBUG] 🔄 Settings updated, reloading...');
      loadSettings();
    } else if (message.type === 'getStatus') {
      sendResponse({ enabled: isEnabled, url: window.location.href });
    }
  });

  // Initialize
  console.log('[CatchSnap DEBUG] 🚀 Initializing CatchSnap...');
  await loadSettings();

  // Start media detection
  console.log('[CatchSnap DEBUG] 👁️ Starting media detector...');
  window.CatchSnapMediaDetector.init({
    onImageDetected: handleImage,
    onVideoDetected: handleVideo
  });

  console.log('[CatchSnap DEBUG] ✅ CatchSnap initialized successfully!');

})();
