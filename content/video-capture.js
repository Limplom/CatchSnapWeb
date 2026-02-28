/**
 * CatchSnap - Video Capture
 * Video blob extraction for complete video capture
 */

const CatchSnapVideoCapture = {
  /**
   * Wait for video metadata to load
   * @param {HTMLVideoElement} video
   * @returns {Promise<void>}
   */
  waitForMetadata(video) {
    return new Promise((resolve, reject) => {
      if (video.readyState >= 1) { // HAVE_METADATA
        resolve();
        return;
      }

      const timeout = setTimeout(() => {
        reject(new Error('Video metadata timeout'));
      }, 30000);

      video.addEventListener('loadedmetadata', () => {
        clearTimeout(timeout);
        resolve();
      }, { once: true });

      video.addEventListener('error', () => {
        clearTimeout(timeout);
        reject(new Error('Video load error'));
      }, { once: true });
    });
  },

  /**
   * Wait for video to be fully loaded (can play through)
   * @param {HTMLVideoElement} video
   * @returns {Promise<void>}
   */
  waitForFullLoad(video) {
    return new Promise((resolve, reject) => {
      if (video.readyState >= 4) { // HAVE_ENOUGH_DATA
        resolve();
        return;
      }

      const timeout = setTimeout(() => {
        // Resolve anyway after timeout - we'll try to capture what we have
        resolve();
      }, 60000);

      video.addEventListener('canplaythrough', () => {
        clearTimeout(timeout);
        resolve();
      }, { once: true });

      video.addEventListener('error', () => {
        clearTimeout(timeout);
        reject(new Error('Video load error'));
      }, { once: true });
    });
  },

  /**
   * Capture a video by fetching its blob URL
   * @param {HTMLVideoElement} video
   * @returns {Promise<{blob: Blob, hash: string, duration: number, type: string} | null>}
   */
  async captureVideo(video) {
    try {
      // Wait for metadata at minimum
      await this.waitForMetadata(video);

      // Skip very short videos (likely loading indicators)
      if (video.duration < 0.5) {
        return null;
      }

      // Get the video source
      let src = video.src;

      // Check for source element if no direct src
      if (!src) {
        const sourceEl = video.querySelector('source');
        if (sourceEl) {
          src = sourceEl.src;
        }
      }

      // Check for currentSrc
      if (!src && video.currentSrc) {
        src = video.currentSrc;
      }

      if (!src) {
        console.warn('[CatchSnap] No video source found');
        return null;
      }

      // Only handle blob URLs
      if (!src.startsWith('blob:')) {
        console.warn('[CatchSnap] Non-blob video source:', src.substring(0, 50));
        return null;
      }

      // Wait for video to be more fully loaded
      await this.waitForFullLoad(video);

      // Fetch the blob
      const response = await fetch(src);
      if (!response.ok) {
        throw new Error(`Fetch failed: ${response.status}`);
      }

      const blob = await response.blob();

      // Verify it's a video
      if (!blob.type.startsWith('video/') && !blob.type.includes('mp4') && !blob.type.includes('webm')) {
        console.warn('[CatchSnap] Unexpected blob type:', blob.type);
        // Still try to save it
      }

      // Skip tiny blobs (likely incomplete)
      if (blob.size < 10000) { // Less than 10KB is suspicious
        console.warn('[CatchSnap] Video blob too small:', blob.size);
        return null;
      }

      const hash = await window.CatchSnapHash.computeHash(blob);

      return {
        blob,
        hash,
        duration: video.duration,
        type: 'video',
        mimeType: blob.type || 'video/mp4'
      };
    } catch (error) {
      console.error('[CatchSnap] Video capture error:', error);
      return null;
    }
  },

  /**
   * Determine file extension from MIME type
   * @param {string} mimeType
   * @returns {string}
   */
  getExtension(mimeType) {
    if (mimeType.includes('webm')) return 'webm';
    if (mimeType.includes('mp4')) return 'mp4';
    if (mimeType.includes('ogg')) return 'ogg';
    return 'mp4'; // Default
  }
};

// Make available globally
window.CatchSnapVideoCapture = CatchSnapVideoCapture;
