package com.catchsnap

import android.net.Uri
import android.util.Log
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import com.catchsnap.models.RequestData
import com.catchsnap.models.ResponseData
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Logs HTTP requests and responses from WebView traffic
 */
class TrafficLogger(private val storageManager: StorageManager) {

    private val requests = mutableListOf<RequestData>()
    private val responses = mutableListOf<ResponseData>()
    private val domains = mutableSetOf<String>()

    companion object {
        private const val TAG = "TrafficLogger"
    }

    /**
     * Log an outgoing request
     */
    fun logRequest(request: WebResourceRequest?) {
        if (request == null) return

        try {
            val timestamp = getCurrentTimestamp()
            val url = request.url.toString()
            val domain = request.url.host ?: ""

            if (domain.isNotEmpty()) {
                domains.add(domain)
            }

            // Extract headers
            val headers = request.requestHeaders.mapValues { it.value }

            // Determine resource type (approximation)
            val resourceType = determineResourceType(url, headers)

            val requestData = RequestData(
                timestamp = timestamp,
                method = request.method,
                url = url,
                headers = headers,
                postData = null, // WebView doesn't expose POST data easily
                resourceType = resourceType
            )

            requests.add(requestData)
            Log.d(TAG, "[REQUEST] ${request.method} $url")

        } catch (e: Exception) {
            Log.e(TAG, "Error logging request: ${e.message}")
        }
    }

    /**
     * Log an incoming response
     */
    fun logResponse(response: WebResourceResponse?, url: Uri?) {
        if (response == null || url == null) return

        try {
            val timestamp = getCurrentTimestamp()
            val urlString = url.toString()

            // Extract headers
            val headers = response.responseHeaders?.mapValues { it.value } ?: emptyMap()

            val contentType = response.mimeType ?: headers["content-type"] ?: ""

            // Try to read body for JSON/text responses
            var body: String? = null
            var bodyError: String? = null

            try {
                if (contentType.contains("application/json") ||
                    contentType.startsWith("text/")) {
                    // Note: response.data can only be read once, so we skip body capture
                    // to avoid breaking the WebView rendering
                    // body = response.data?.bufferedReader()?.use { it.readText() }
                }
            } catch (e: Exception) {
                bodyError = e.message
            }

            val responseData = ResponseData(
                timestamp = timestamp,
                url = urlString,
                status = response.statusCode,
                statusText = response.reasonPhrase ?: "",
                headers = headers,
                contentType = contentType,
                body = body,
                bodyError = bodyError
            )

            responses.add(responseData)

            val statusColor = if (response.statusCode in 200..299) "OK" else "ERROR"
            Log.d(TAG, "[RESPONSE] ${response.statusCode} $urlString [$statusColor]")

        } catch (e: Exception) {
            Log.e(TAG, "Error logging response: ${e.message}")
        }
    }

    /**
     * Get current timestamp in ISO format
     */
    private fun getCurrentTimestamp(): String {
        return SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).format(Date())
    }

    /**
     * Determine resource type based on URL and headers
     */
    private fun determineResourceType(url: String, headers: Map<String, String>): String {
        // Check content type header if available
        val contentType = headers["content-type"] ?: headers["Content-Type"]
        contentType?.let {
            return when {
                it.contains("image") -> "image"
                it.contains("video") -> "media"
                it.contains("audio") -> "media"
                it.contains("javascript") || it.contains("script") -> "script"
                it.contains("css") -> "stylesheet"
                it.contains("font") -> "font"
                it.contains("json") -> "xhr"
                else -> "other"
            }
        }

        // Fallback to URL-based detection
        return when {
            url.contains(Regex("\\.(?:jpg|jpeg|png|gif|webp|svg)(?:\\?|$)", RegexOption.IGNORE_CASE)) -> "image"
            url.contains(Regex("\\.(?:mp4|webm|ogg|mov)(?:\\?|$)", RegexOption.IGNORE_CASE)) -> "media"
            url.contains(Regex("\\.(?:mp3|wav|m4a)(?:\\?|$)", RegexOption.IGNORE_CASE)) -> "media"
            url.contains(Regex("\\.(?:js)(?:\\?|$)", RegexOption.IGNORE_CASE)) -> "script"
            url.contains(Regex("\\.(?:css)(?:\\?|$)", RegexOption.IGNORE_CASE)) -> "stylesheet"
            url.contains(Regex("\\.(?:woff|woff2|ttf|otf)(?:\\?|$)", RegexOption.IGNORE_CASE)) -> "font"
            url.startsWith("blob:") -> "blob"
            else -> "other"
        }
    }

    /**
     * Get all logged requests
     */
    fun getRequests(): List<RequestData> = requests.toList()

    /**
     * Get all logged responses
     */
    fun getResponses(): List<ResponseData> = responses.toList()

    /**
     * Get all unique domains
     */
    fun getDomains(): Set<String> = domains.toSet()

    /**
     * Save all traffic logs to files
     */
    fun saveToFile() {
        try {
            storageManager.saveTrafficLogs(requests, responses)
            Log.i(TAG, "Traffic logs saved successfully")
        } catch (e: Exception) {
            Log.e(TAG, "Error saving traffic logs: ${e.message}")
        }
    }

    /**
     * Clear all logged data
     */
    fun clear() {
        requests.clear()
        responses.clear()
        domains.clear()
        Log.i(TAG, "Traffic logs cleared")
    }

    /**
     * Get statistics
     */
    fun getStats(): Map<String, Int> {
        return mapOf(
            "requests" to requests.size,
            "responses" to responses.size,
            "domains" to domains.size
        )
    }
}
