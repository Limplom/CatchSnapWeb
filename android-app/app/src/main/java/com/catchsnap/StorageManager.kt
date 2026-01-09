package com.catchsnap

import android.content.Context
import android.util.Log
import com.catchsnap.models.BlobData
import com.catchsnap.models.RequestData
import com.catchsnap.models.ResponseData
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Manages file storage for traffic logs and blob downloads
 */
class StorageManager(private val context: Context) {

    private val gson: Gson = GsonBuilder().setPrettyPrinting().create()
    private val sessionTimestamp: String
    private val sessionDir: File
    private val blobsDir: File

    companion object {
        private const val TAG = "StorageManager"
        private const val BASE_DIR = "traffic_logs"
    }

    init {
        // Create timestamp for this session
        sessionTimestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())

        // Create session directory: /Android/data/com.catchsnap/files/traffic_logs/android_{timestamp}/
        val baseDir = File(context.getExternalFilesDir(null), BASE_DIR)
        sessionDir = File(baseDir, "android_$sessionTimestamp")

        if (!sessionDir.exists()) {
            sessionDir.mkdirs()
            Log.i(TAG, "Session directory created: ${sessionDir.absolutePath}")
        }

        // Create blobs subdirectory
        blobsDir = File(sessionDir, "blobs")
        if (!blobsDir.exists()) {
            blobsDir.mkdirs()
            Log.i(TAG, "Blobs directory created: ${blobsDir.absolutePath}")
        }
    }

    /**
     * Get the file extension based on content type
     */
    private fun getFileExtension(contentType: String): String {
        val extensions = mapOf(
            "image/jpeg" to ".jpg",
            "image/jpg" to ".jpg",
            "image/png" to ".png",
            "image/gif" to ".gif",
            "image/webp" to ".webp",
            "image/svg+xml" to ".svg",
            "video/mp4" to ".mp4",
            "video/webm" to ".webm",
            "video/ogg" to ".ogg",
            "audio/mpeg" to ".mp3",
            "audio/ogg" to ".ogg",
            "audio/wav" to ".wav",
            "application/javascript" to ".js",
            "application/json" to ".json",
            "text/html" to ".html",
            "text/css" to ".css",
            "text/plain" to ".txt"
        )
        return extensions[contentType.split(';')[0].trim()] ?: ".bin"
    }

    /**
     * Save a blob file with hash-based filename
     * @return BlobData object with file information
     */
    fun saveBlobFile(
        data: ByteArray,
        hash: String,
        contentType: String,
        blobUrl: String
    ): BlobData {
        val extension = getFileExtension(contentType)
        val filename = "$hash$extension"
        val file = File(blobsDir, filename)

        // Check if file already exists (duplicate detection)
        val isDuplicate = file.exists()

        // Write file (overwrite if duplicate)
        file.writeBytes(data)

        val timestamp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).format(Date())

        return BlobData(
            blobUrl = blobUrl,
            filename = filename,
            filepath = file.absolutePath,
            contentType = contentType,
            size = data.size,
            hash = hash,
            duplicate = isDuplicate,
            timestamp = timestamp
        )
    }

    /**
     * Save traffic logs (requests and responses) to JSON files
     */
    fun saveTrafficLogs(
        requests: List<RequestData>,
        responses: List<ResponseData>
    ): Pair<File, File> {
        // Save requests
        val requestsFile = File(sessionDir, "requests_$sessionTimestamp.json")
        requestsFile.writeText(gson.toJson(requests))
        Log.i(TAG, "Requests saved: ${requestsFile.absolutePath} (${requests.size} requests)")

        // Save responses
        val responsesFile = File(sessionDir, "responses_$sessionTimestamp.json")
        responsesFile.writeText(gson.toJson(responses))
        Log.i(TAG, "Responses saved: ${responsesFile.absolutePath} (${responses.size} responses)")

        return Pair(requestsFile, responsesFile)
    }

    /**
     * Save blob metadata to JSON file
     */
    fun saveBlobMetadata(blobs: List<BlobData>): File {
        val blobsFile = File(sessionDir, "downloaded_blobs_$sessionTimestamp.json")
        blobsFile.writeText(gson.toJson(blobs))

        val uniqueBlobs = blobs.count { !it.duplicate }
        val duplicates = blobs.size - uniqueBlobs

        Log.i(TAG, "Blob metadata saved: ${blobsFile.absolutePath}")
        Log.i(TAG, "  - $uniqueBlobs unique blob(s)")
        if (duplicates > 0) {
            Log.i(TAG, "  - $duplicates duplicate(s) skipped")
        }

        return blobsFile
    }

    /**
     * Save summary information about the session
     */
    fun saveSummary(
        sessionStart: Date,
        requestCount: Int,
        responseCount: Int,
        blobCount: Int,
        uniqueBlobCount: Int,
        domains: Set<String>
    ): File {
        val sessionEnd = Date()
        val dateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)

        val summary = mapOf(
            "session_start" to dateFormat.format(sessionStart),
            "session_end" to dateFormat.format(sessionEnd),
            "total_requests" to requestCount,
            "total_responses" to responseCount,
            "total_blobs_processed" to blobCount,
            "unique_blobs_saved" to uniqueBlobCount,
            "duplicate_blobs_skipped" to (blobCount - uniqueBlobCount),
            "unique_domains" to domains.toList()
        )

        val summaryFile = File(sessionDir, "summary_$sessionTimestamp.json")
        summaryFile.writeText(gson.toJson(summary))
        Log.i(TAG, "Summary saved: ${summaryFile.absolutePath}")

        return summaryFile
    }

    /**
     * Get the session directory path
     */
    fun getSessionDir(): File = sessionDir

    /**
     * Get the blobs directory path
     */
    fun getBlobsDir(): File = blobsDir
}
