/**
 * CatchSnap - Image Capture
 * Canvas-based image extraction for complete image capture
 */

const CatchSnapImageCapture = {
  /**
   * Wait for an image to fully load
   * @param {HTMLImageElement} img
   * @returns {Promise<void>}
   */
  waitForLoad(img) {
    return new Promise((resolve, reject) => {
      if (img.complete && img.naturalWidth > 0) {
        resolve();
        return;
      }

      const timeout = setTimeout(() => {
        // Resolve anyway - try to capture what we have
        resolve();
      }, 30000);

      img.addEventListener('load', () => {
        clearTimeout(timeout);
        resolve();
      }, { once: true });

      img.addEventListener('error', () => {
        clearTimeout(timeout);
        reject(new Error('Image load error'));
      }, { once: true });
    });
  },

  /**
   * Capture an image - tries multiple methods
   * @param {HTMLImageElement} img
   * @returns {Promise<{blob: Blob, hash: string, width: number, height: number, type: string} | null>}
   */
  async captureImage(img) {
    try {
      const src = img.src;
      console.log('[CatchSnap] Capturing image:', src?.substring(0, 100));

      // Wait for image to fully load
      await this.waitForLoad(img);

      // Skip tiny images (likely icons or spacers)
      if (img.naturalWidth < 50 || img.naturalHeight < 50) {
        console.log('[CatchSnap] Skipping small image:', img.naturalWidth, 'x', img.naturalHeight);
        return null;
      }

      // Method 1: Try direct fetch for non-blob URLs (often better quality)
      if (src && !src.startsWith('blob:') && !src.startsWith('data:')) {
        const directResult = await this.captureFromUrl(src);
        if (directResult) {
          return directResult;
        }
        console.log('[CatchSnap] Direct fetch failed, trying canvas...');
      }

      // Method 2: Canvas capture (works for blob URLs and cross-origin)
      return await this.captureFromCanvas(img);

    } catch (error) {
      console.error('[CatchSnap] Image capture error:', error);
      return null;
    }
  },

  /**
   * Capture image by fetching URL directly
   * @param {string} url
   * @returns {Promise<{blob: Blob, hash: string, type: string} | null>}
   */
  async captureFromUrl(url) {
    try {
      console.log('[CatchSnap] Direct fetch:', url.substring(0, 80));

      const response = await fetch(url, {
        credentials: 'include',
        mode: 'cors'
      });

      if (!response.ok) {
        console.log('[CatchSnap] Direct fetch failed:', response.status);
        return null;
      }

      const blob = await response.blob();

      // Verify it's an image
      if (!blob.type.startsWith('image/')) {
        console.log('[CatchSnap] Not an image type:', blob.type);
        return null;
      }

      // Skip tiny blobs
      if (blob.size < 1000) {
        console.log('[CatchSnap] Blob too small:', blob.size);
        return null;
      }

      const hash = await window.CatchSnapHash.computeHash(blob);

      console.log('[CatchSnap] Direct fetch success:', blob.size, 'bytes');

      return {
        blob,
        hash,
        type: 'image',
        mimeType: blob.type
      };
    } catch (error) {
      console.log('[CatchSnap] Direct fetch error:', error.message);
      return null;
    }
  },

  /**
   * Capture image using canvas
   * @param {HTMLImageElement} img
   * @returns {Promise<{blob: Blob, hash: string, width: number, height: number, type: string} | null>}
   */
  async captureFromCanvas(img) {
    try {
      console.log('[CatchSnap] Canvas capture:', img.naturalWidth, 'x', img.naturalHeight);

      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        console.error('[CatchSnap] Failed to get canvas context');
        return null;
      }

      // Draw image to canvas
      ctx.drawImage(img, 0, 0);

      // Determine output format
      let mimeType = 'image/jpeg';
      let quality = 0.95;

      const src = (img.src || '').toLowerCase();
      if (src.includes('png') || this.hasTransparency(ctx, canvas.width, canvas.height)) {
        mimeType = 'image/png';
        quality = undefined;
      }

      // Convert to blob
      const blob = await new Promise((resolve) => {
        canvas.toBlob(resolve, mimeType, quality);
      });

      if (!blob) {
        console.error('[CatchSnap] Failed to create blob from canvas');
        return null;
      }

      // Skip tiny results
      if (blob.size < 1000) {
        console.log('[CatchSnap] Canvas result too small:', blob.size);
        return null;
      }

      const hash = await window.CatchSnapHash.computeHash(blob);

      console.log('[CatchSnap] Canvas capture success:', blob.size, 'bytes');

      return {
        blob,
        hash,
        width: img.naturalWidth,
        height: img.naturalHeight,
        type: 'image',
        mimeType
      };
    } catch (error) {
      console.error('[CatchSnap] Canvas capture error:', error);
      return null;
    }
  },

  /**
   * Check if canvas has transparent pixels
   */
  hasTransparency(ctx, width, height) {
    try {
      const sampleSize = Math.min(100, width * height);
      const imageData = ctx.getImageData(0, 0, width, height);
      const data = imageData.data;

      for (let i = 0; i < sampleSize; i++) {
        const idx = Math.floor(Math.random() * (data.length / 4)) * 4;
        if (data[idx + 3] < 255) {
          return true;
        }
      }
      return false;
    } catch {
      return false;
    }
  }
};

// Make available globally
window.CatchSnapImageCapture = CatchSnapImageCapture;
