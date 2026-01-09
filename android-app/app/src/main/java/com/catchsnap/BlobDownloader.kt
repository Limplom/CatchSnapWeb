package com.catchsnap

import android.content.Context
import android.util.Base64
import android.util.Log
import android.webkit.JavascriptInterface
import com.catchsnap.models.BlobData
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.security.MessageDigest

/**
 * JavaScript Bridge for downloading blob URLs
 * This class is exposed to JavaScript via @JavascriptInterface
 */
class BlobDownloader(
    private val context: Context,
    private val storageManager: StorageManager,
    private val coroutineScope: CoroutineScope
) {

    private val downloadedBlobs = mutableListOf<BlobData>()
    private val processedBlobUrls = mutableSetOf<String>()

    companion object {
        private const val TAG = "BlobDownloader"
    }

    /**
     * Called from JavaScript when a blob is detected
     * @param blobUrl The blob:// URL
     * @param base64Data The blob data encoded in base64
     * @param contentType The MIME type of the blob
     */
    @JavascriptInterface
    fun downloadBlob(blobUrl: String, base64Data: String, contentType: String) {
        // Prevent duplicate downloads
        if (processedBlobUrls.contains(blobUrl)) {
            logMessage("[BLOB] Already processed: $blobUrl")
            return
        }

        processedBlobUrls.add(blobUrl)

        // Process blob download in background
        coroutineScope.launch {
            try {
                processBlobDownload(blobUrl, base64Data, contentType)
            } catch (e: Exception) {
                Log.e(TAG, "[BLOB] Error processing blob: ${e.message}")
                withContext(Dispatchers.Main) {
                    logMessage("[BLOB] Error: ${e.message}")
                }
            }
        }
    }

    /**
     * Process blob download in background thread
     */
    private suspend fun processBlobDownload(
        blobUrl: String,
        base64Data: String,
        contentType: String
    ) = withContext(Dispatchers.IO) {
        try {
            // Decode base64 data
            val fileData = Base64.decode(base64Data, Base64.DEFAULT)

            // Validate blob data
            val validation = BlobValidator.validate(fileData, contentType)

            if (!validation.isValid) {
                Log.w(TAG, "[BLOB] Validation failed: ${validation.message}")
                withContext(Dispatchers.Main) {
                    logMessage("[BLOB] Validation failed: ${validation.message}")
                }
                return@withContext
            }

            // Calculate SHA-256 hash
            val hash = calculateSHA256(fileData)

            // Save blob file
            val blobData = storageManager.saveBlobFile(
                data = fileData,
                hash = hash,
                contentType = contentType,
                blobUrl = blobUrl
            )

            // Add to downloaded blobs list
            synchronized(downloadedBlobs) {
                downloadedBlobs.add(blobData)
            }

            // Log success
            val statusMsg = if (blobData.duplicate) {
                "[BLOB] OK Updated (Duplicate): ${blobData.filename} (${blobData.size} bytes, $contentType)"
            } else {
                "[BLOB] OK Downloaded: ${blobData.filename} (${blobData.size} bytes, $contentType)"
            }

            Log.i(TAG, statusMsg)
            withContext(Dispatchers.Main) {
                logMessage(statusMsg)
            }

        } catch (e: Exception) {
            Log.e(TAG, "[BLOB] Download error for $blobUrl: ${e.message}")
            withContext(Dispatchers.Main) {
                logMessage("[BLOB] Download error: ${e.message}")
            }
        }
    }

    /**
     * Calculate SHA-256 hash of data
     */
    private fun calculateSHA256(data: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hashBytes = digest.digest(data)
        return hashBytes.joinToString("") { "%02x".format(it) }
    }

    /**
     * Log message from JavaScript to Android Logcat
     */
    @JavascriptInterface
    fun logMessage(message: String) {
        Log.d(TAG, message)
    }

    /**
     * Get all downloaded blobs
     */
    fun getDownloadedBlobs(): List<BlobData> {
        synchronized(downloadedBlobs) {
            return downloadedBlobs.toList()
        }
    }

    /**
     * Save blob metadata to file
     */
    fun saveMetadata() {
        if (downloadedBlobs.isEmpty()) {
            Log.i(TAG, "No blobs to save")
            return
        }

        synchronized(downloadedBlobs) {
            storageManager.saveBlobMetadata(downloadedBlobs)
        }
    }

    /**
     * Get statistics about downloaded blobs
     */
    fun getStats(): Map<String, Int> {
        synchronized(downloadedBlobs) {
            val uniqueBlobs = downloadedBlobs.count { !it.duplicate }
            val duplicates = downloadedBlobs.size - uniqueBlobs

            return mapOf(
                "total_blobs" to downloadedBlobs.size,
                "unique_blobs" to uniqueBlobs,
                "duplicate_blobs" to duplicates
            )
        }
    }

    /**
     * Clear all downloaded blobs
     */
    fun clear() {
        synchronized(downloadedBlobs) {
            downloadedBlobs.clear()
        }
        processedBlobUrls.clear()
        Log.i(TAG, "Blob data cleared")
    }
}
