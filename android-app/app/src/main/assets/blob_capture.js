/**
 * Blob Capture JavaScript
 * This script is injected into the WebView to capture blob URLs
 * and send them to the Android app via JavaScript Bridge
 */

(function() {
    'use strict';

    // Check if Android bridge is available
    if (typeof Android === 'undefined') {
        console.error('[BlobCapture] Android interface not found!');
        return;
    }

    console.log('[BlobCapture] Initializing blob capture...');

    // Track processed blob URLs to avoid duplicates
    const processedBlobs = new Set();

    /**
     * Process a blob URL and send it to Android
     */
    async function processBlobUrl(blobUrl) {
        // Avoid processing the same blob twice
        if (processedBlobs.has(blobUrl)) {
            return;
        }

        processedBlobs.add(blobUrl);

        try {
            Android.logMessage('[BLOB] Detected: ' + blobUrl);

            // Fetch the blob
            const response = await fetch(blobUrl);
            const blob = await response.blob();

            // Convert blob to base64
            const reader = new FileReader();

            reader.onloadend = function() {
                try {
                    // Extract base64 data (remove data:mime;base64, prefix)
                    const base64Data = reader.result.split(',')[1];

                    // Send to Android
                    Android.downloadBlob(blobUrl, base64Data, blob.type);

                    Android.logMessage('[BLOB] Sent to Android: ' + blobUrl + ' (' + blob.size + ' bytes, ' + blob.type + ')');
                } catch (error) {
                    Android.logMessage('[BLOB] Error processing: ' + error.message);
                }
            };

            reader.onerror = function() {
                Android.logMessage('[BLOB] FileReader error for: ' + blobUrl);
            };

            reader.readAsDataURL(blob);

        } catch (error) {
            Android.logMessage('[BLOB] Fetch error: ' + error.message);
        }
    }

    /**
     * Override fetch() to intercept blob URLs
     */
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];

        // Check if it's a blob URL
        if (typeof url === 'string' && url.startsWith('blob:')) {
            // Process blob asynchronously
            setTimeout(() => processBlobUrl(url), 100);
        }

        // Call original fetch
        return originalFetch.apply(this, args);
    };

    /**
     * Monitor DOM for blob URLs in media elements
     */
    const observer = new MutationObserver((mutations) => {
        mutations.forEach(mutation => {
            mutation.addedNodes.forEach(node => {
                // Check for blob URLs in images and videos
                if (node.nodeType === Node.ELEMENT_NODE) {
                    // Check IMG elements
                    if (node.tagName === 'IMG' && node.src && node.src.startsWith('blob:')) {
                        processBlobUrl(node.src);
                    }

                    // Check VIDEO elements
                    if (node.tagName === 'VIDEO' && node.src && node.src.startsWith('blob:')) {
                        processBlobUrl(node.src);
                    }

                    // Check SOURCE elements within VIDEO
                    if (node.tagName === 'SOURCE' && node.src && node.src.startsWith('blob:')) {
                        processBlobUrl(node.src);
                    }

                    // Also check child elements
                    const imgElements = node.querySelectorAll ? node.querySelectorAll('img[src^="blob:"]') : [];
                    imgElements.forEach(img => {
                        if (img.src) {
                            processBlobUrl(img.src);
                        }
                    });

                    const videoElements = node.querySelectorAll ? node.querySelectorAll('video[src^="blob:"]') : [];
                    videoElements.forEach(video => {
                        if (video.src) {
                            processBlobUrl(video.src);
                        }
                    });

                    const sourceElements = node.querySelectorAll ? node.querySelectorAll('source[src^="blob:"]') : [];
                    sourceElements.forEach(source => {
                        if (source.src) {
                            processBlobUrl(source.src);
                        }
                    });
                }
            });

            // Also check for attribute changes (src being set)
            if (mutation.type === 'attributes' && mutation.attributeName === 'src') {
                const element = mutation.target;
                if (element.src && element.src.startsWith('blob:')) {
                    processBlobUrl(element.src);
                }
            }
        });
    });

    // Start observing the document
    observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['src']
    });

    /**
     * Also intercept URL.createObjectURL
     */
    const originalCreateObjectURL = URL.createObjectURL;
    URL.createObjectURL = function(blob) {
        const blobUrl = originalCreateObjectURL.call(this, blob);

        // Process the blob after a short delay to ensure it's fully created
        setTimeout(() => processBlobUrl(blobUrl), 200);

        return blobUrl;
    };

    /**
     * Check existing blob URLs on page
     */
    function scanExistingBlobs() {
        // Scan for existing IMG elements with blob URLs
        document.querySelectorAll('img[src^="blob:"]').forEach(img => {
            if (img.src) {
                processBlobUrl(img.src);
            }
        });

        // Scan for existing VIDEO elements with blob URLs
        document.querySelectorAll('video[src^="blob:"]').forEach(video => {
            if (video.src) {
                processBlobUrl(video.src);
            }
        });

        // Scan for existing SOURCE elements with blob URLs
        document.querySelectorAll('source[src^="blob:"]').forEach(source => {
            if (source.src) {
                processBlobUrl(source.src);
            }
        });
    }

    // Scan for existing blobs after DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scanExistingBlobs);
    } else {
        scanExistingBlobs();
    }

    // Also scan periodically (in case blobs are added dynamically)
    setInterval(scanExistingBlobs, 2000);

    Android.logMessage('[BlobCapture] Blob capture initialized successfully');

    console.log('[BlobCapture] Blob capture active!');
})();
