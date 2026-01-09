package com.catchsnap

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * Custom WebViewClient for intercepting traffic and injecting JavaScript
 */
class SnapWebViewClient(
    private val context: Context,
    private val trafficLogger: TrafficLogger
) : WebViewClient() {

    companion object {
        private const val TAG = "SnapWebViewClient"
    }

    /**
     * Called when a page starts loading
     * This is where we inject our blob capture JavaScript
     */
    override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
        super.onPageStarted(view, url, favicon)

        Log.d(TAG, "Page started: $url")

        // Inject blob capture JavaScript as early as possible
        view?.let {
            try {
                val blobCaptureJs = loadJsFromAssets("blob_capture.js")
                it.evaluateJavascript(blobCaptureJs, null)
                Log.i(TAG, "Blob capture JavaScript injected")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to inject JavaScript: ${e.message}")
            }
        }
    }

    /**
     * Called when a page finishes loading
     */
    override fun onPageFinished(view: WebView?, url: String?) {
        super.onPageFinished(view, url)
        Log.d(TAG, "Page finished: $url")
    }

    /**
     * Intercept all resource requests
     * This allows us to log traffic
     */
    override fun shouldInterceptRequest(
        view: WebView?,
        request: WebResourceRequest?
    ): WebResourceResponse? {
        request?.let {
            // Log the request
            trafficLogger.logRequest(it)

            // Note: We can't easily intercept responses here without breaking functionality
            // The response logging happens via JavaScript bridge for blobs
            // and via TrafficLogger.logResponse for other resources
        }

        // Let the request proceed normally
        return super.shouldInterceptRequest(view, request)
    }

    /**
     * Handle loading errors
     */
    override fun onReceivedError(
        view: WebView?,
        errorCode: Int,
        description: String?,
        failingUrl: String?
    ) {
        super.onReceivedError(view, errorCode, description, failingUrl)
        Log.e(TAG, "WebView error: $description (code: $errorCode) at $failingUrl")
    }

    /**
     * Load JavaScript file from assets
     */
    private fun loadJsFromAssets(filename: String): String {
        return try {
            val inputStream = context.assets.open(filename)
            val reader = BufferedReader(InputStreamReader(inputStream))
            val stringBuilder = StringBuilder()
            var line: String?

            while (reader.readLine().also { line = it } != null) {
                stringBuilder.append(line)
                stringBuilder.append('\n')
            }

            reader.close()
            stringBuilder.toString()
        } catch (e: Exception) {
            Log.e(TAG, "Error loading JS from assets: ${e.message}")
            ""
        }
    }

    /**
     * Override URL loading behavior
     * Return false to let WebView handle the URL
     */
    override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
        // Let WebView handle all URLs
        return false
    }
}
