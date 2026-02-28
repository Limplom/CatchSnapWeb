/**
 * CatchSnap - Media Detector
 * MutationObserver-based detection of media elements in Snapchat Web
 * Only detects actual Snap content (stories, chat media) - not UI elements
 */

const CatchSnapMediaDetector = {
  observer: null,
  processedElements: new WeakSet(),
  processedSrcs: new Set(),
  processingQueue: [],
  isProcessing: false,
  debounceTimer: null,

  // Callbacks
  onImageDetected: null,
  onVideoDetected: null,

  /**
   * Initialize the media detector
   * @param {Object} callbacks - {onImageDetected, onVideoDetected}
   */
  init(callbacks) {
    this.onImageDetected = callbacks.onImageDetected;
    this.onVideoDetected = callbacks.onVideoDetected;

    console.log('[CatchSnap] Media detector initializing...');

    // Start observing for new media
    this.startObserver();

    console.log('[CatchSnap] Media detector initialized');
  },

  /**
   * Check if element is inside a Snap viewer (story or chat media)
   * @param {HTMLElement} element
   * @returns {boolean}
   */
  isInSnapViewer(element) {
    // Walk up the DOM tree to check if we're in a snap viewer
    let current = element;
    for (let i = 0; i < 20; i++) {
      if (!current || !current.parentElement) break;
      current = current.parentElement;

      // Check for snap viewer indicators
      const className = (current.className || '').toLowerCase();
      const role = current.getAttribute('role') || '';
      const ariaLabel = (current.getAttribute('aria-label') || '').toLowerCase();
      const dataTestId = (current.getAttribute('data-testid') || '').toLowerCase();

      // Snap viewer / Story viewer indicators - check various patterns
      if (
        className.includes('media') ||
        className.includes('snap') ||
        className.includes('story') ||
        className.includes('viewer') ||
        className.includes('modal') ||
        className.includes('spotlight') ||
        className.includes('player') ||
        className.includes('fullscreen') ||
        className.includes('preview') ||
        className.includes('chat') ||
        className.includes('message') ||
        dataTestId.includes('snap') ||
        dataTestId.includes('media') ||
        dataTestId.includes('story') ||
        dataTestId.includes('player') ||
        role === 'dialog' ||
        ariaLabel.includes('snap') ||
        ariaLabel.includes('story')
      ) {
        console.log('[CatchSnap] Found viewer context:', className.substring(0, 50) || dataTestId || role);
        return true;
      }

      // Check for full-screen or large media containers
      const rect = current.getBoundingClientRect();
      if (rect.width > 300 && rect.height > 300) {
        // Large container - likely a media viewer
        if (className.includes('container') || className.includes('content') || className.includes('wrapper')) {
          console.log('[CatchSnap] Found large container:', rect.width, 'x', rect.height);
          return true;
        }
      }
    }

    return false;
  },

  /**
   * Check if an image is actual Snap content (not UI)
   * @param {HTMLImageElement} img
   * @returns {boolean}
   */
  isSnapContent(img) {
    const src = (img.src || '');

    // Debug: Log all images being checked with MORE detail
    console.log('[CatchSnap DEBUG] Checking image:', {
      src: src.substring(0, 80),
      naturalWidth: img.naturalWidth,
      naturalHeight: img.naturalHeight,
      complete: img.complete,
      className: img.className,
      parentClassName: img.parentElement?.className,
      inViewport: img.getBoundingClientRect().width > 0
    });

    // Must be reasonably large (not icons/avatars)
    if (img.naturalWidth < 200 || img.naturalHeight < 200) {
      console.log('[CatchSnap DEBUG] ❌ Rejected: too small', {
        width: img.naturalWidth,
        height: img.naturalHeight
      });
      return false;
    }

    // Check aspect ratio - snaps are usually portrait or square
    const aspectRatio = img.naturalWidth / img.naturalHeight;
    // Allow portrait (0.4-0.8), square (0.8-1.2), and some landscape
    if (aspectRatio < 0.3 || aspectRatio > 2.5) {
      console.log('[CatchSnap DEBUG] ❌ Rejected: bad aspect ratio', {
        aspectRatio,
        width: img.naturalWidth,
        height: img.naturalHeight
      });
      return false;
    }

    const srcLower = src.toLowerCase();

    // Skip known UI elements
    const skipPatterns = [
      'emoji', 'avatar', 'icon', 'logo', 'badge', 'bitmoji',
      'sticker', 'sprite', 'placeholder', 'profile', 'thumbnail',
      'button', 'arrow', 'chevron', 'search', 'notification'
    ];

    for (const pattern of skipPatterns) {
      if (srcLower.includes(pattern)) {
        console.log('[CatchSnap DEBUG] ❌ Rejected: matches skip pattern', {
          pattern,
          src: src.substring(0, 100)
        });
        return false;
      }
    }

    // Blob URLs are almost always actual snap content if they're large enough
    if (src.startsWith('blob:')) {
      console.log('[CatchSnap DEBUG] ✅ ACCEPTED: Large blob URL image (likely snap content)', {
        width: img.naturalWidth,
        height: img.naturalHeight,
        src: src.substring(0, 80)
      });
      return true;
    }

    // For non-blob URLs, must be in a snap viewer context
    const inViewer = this.isInSnapViewer(img);
    if (!inViewer) {
      console.log('[CatchSnap DEBUG] ❌ Rejected: not in snap viewer context', {
        src: src.substring(0, 100)
      });
      return false;
    }

    console.log('[CatchSnap DEBUG] ✅ ACCEPTED as snap content!', {
      src: src.substring(0, 80),
      width: img.naturalWidth,
      height: img.naturalHeight
    });
    return true;
  },

  /**
   * Check if video is actual Snap content
   * @param {HTMLVideoElement} video
   * @returns {boolean}
   */
  isSnapVideoContent(video) {
    // Must have a source
    const src = video.src || video.currentSrc;

    console.log('[CatchSnap] Checking video:', {
      src: src ? src.substring(0, 80) : 'no src',
      readyState: video.readyState,
      duration: video.duration,
      videoWidth: video.videoWidth,
      videoHeight: video.videoHeight
    });

    if (!src) {
      console.log('[CatchSnap] Video rejected: no source');
      return false;
    }

    // Must be blob URL (Snapchat uses blob URLs for video)
    if (!src.startsWith('blob:')) {
      console.log('[CatchSnap] Video rejected: not a blob URL');
      return false;
    }

    // Skip very small videos (likely UI elements or loading spinners)
    if (video.videoWidth > 0 && video.videoHeight > 0) {
      if (video.videoWidth < 100 || video.videoHeight < 100) {
        console.log('[CatchSnap] Video rejected: too small dimensions');
        return false;
      }
    }

    // For blob URLs, accept them - they're likely snap content
    console.log('[CatchSnap] Video ACCEPTED as snap content!');
    return true;
  },

  /**
   * Start the MutationObserver
   */
  startObserver() {
    if (this.observer) {
      this.observer.disconnect();
    }

    this.observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        // Check added nodes
        for (const node of mutation.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) {
            this.processNode(node);
          }
        }

        // Check attribute changes (src changes on existing elements)
        if (mutation.type === 'attributes' && mutation.attributeName === 'src') {
          const target = mutation.target;
          if (target.tagName === 'IMG') {
            // Small delay to let image load
            setTimeout(() => {
              if (this.isSnapContent(target)) {
                console.log('[CatchSnap] Snap image detected (src change)');
                this.queueElement(target, 'image');
              }
            }, 100);
          } else if (target.tagName === 'VIDEO') {
            if (this.isSnapVideoContent(target)) {
              console.log('[CatchSnap] Snap video detected (src change)');
              this.queueElement(target, 'video');
            }
          }
        }
      }
    });

    this.observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['src']
    });
  },

  /**
   * Process a DOM node and its children for media elements
   * @param {Element} node
   */
  processNode(node) {
    // Check if node itself is media
    if (node.tagName === 'IMG') {
      // Delay check to allow image to load
      setTimeout(() => {
        if (this.isSnapContent(node)) {
          console.log('[CatchSnap] Snap image detected');
          this.queueElement(node, 'image');
        }
      }, 200);
    } else if (node.tagName === 'VIDEO') {
      if (this.isSnapVideoContent(node)) {
        console.log('[CatchSnap] Snap video detected');
        this.queueElement(node, 'video');
      }
    }

    // Check children
    if (node.querySelectorAll) {
      const images = node.querySelectorAll('img');
      images.forEach(img => {
        setTimeout(() => {
          if (this.isSnapContent(img)) {
            this.queueElement(img, 'image');
          }
        }, 200);
      });

      const videos = node.querySelectorAll('video');
      videos.forEach(video => {
        if (this.isSnapVideoContent(video)) {
          this.queueElement(video, 'video');
        }
      });
    }
  },

  /**
   * Queue an element for processing
   * @param {HTMLElement} element
   * @param {string} type - 'image' or 'video'
   */
  queueElement(element, type) {
    // Skip if already processed
    if (this.processedElements.has(element)) {
      return;
    }

    // Check by src to avoid duplicates
    const src = element.src || element.currentSrc;
    if (src && this.processedSrcs.has(src)) {
      return;
    }

    // Mark as processed
    this.processedElements.add(element);
    if (src) {
      this.processedSrcs.add(src);
    }

    console.log(`[CatchSnap] Queuing ${type} for processing`);

    // Add to queue
    this.processingQueue.push({ element, type });

    // Debounce processing
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = setTimeout(() => {
      this.processQueue();
    }, 100);
  },

  /**
   * Process the queued elements
   */
  async processQueue() {
    if (this.isProcessing || this.processingQueue.length === 0) {
      return;
    }

    this.isProcessing = true;
    console.log(`[CatchSnap] Processing queue: ${this.processingQueue.length} items`);

    while (this.processingQueue.length > 0) {
      const { element, type } = this.processingQueue.shift();

      try {
        if (type === 'image' && this.onImageDetected) {
          await this.onImageDetected(element);
        } else if (type === 'video' && this.onVideoDetected) {
          await this.onVideoDetected(element);
        }
      } catch (error) {
        console.error(`[CatchSnap] Error processing ${type}:`, error);
      }

      await new Promise(resolve => setTimeout(resolve, 50));
    }

    this.isProcessing = false;
  },

  /**
   * Stop the observer
   */
  stop() {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    console.log('[CatchSnap] Media detector stopped');
  },

  /**
   * Reset
   */
  reset() {
    this.processedElements = new WeakSet();
    this.processedSrcs = new Set();
    this.processingQueue = [];
    console.log('[CatchSnap] Media detector reset');
  }
};

// Make available globally
window.CatchSnapMediaDetector = CatchSnapMediaDetector;
