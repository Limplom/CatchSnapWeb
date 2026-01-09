package com.catchsnap

import android.os.Bundle
import android.util.Log
import android.view.KeyEvent
import android.webkit.CookieManager
import android.webkit.WebSettings
import android.webkit.WebView
import android.widget.ProgressBar
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import java.util.Date

/**
 * Main Activity that hosts the WebView for Snapchat Web
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var storageManager: StorageManager
    private lateinit var trafficLogger: TrafficLogger
    private lateinit var blobDownloader: BlobDownloader
    private var sessionStartTime: Date? = null

    companion object {
        private const val TAG = "MainActivity"
        private const val SNAPCHAT_WEB_URL = "https://www.snapchat.com/web"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Initialize components
        initializeComponents()

        // Setup WebView
        setupWebView()

        // Load Snapchat Web
        loadSnapchatWeb()
    }

    /**
     * Initialize storage, logger, and downloader
     */
    private fun initializeComponents() {
        sessionStartTime = Date()

        storageManager = StorageManager(this)
        trafficLogger = TrafficLogger(storageManager)
        blobDownloader = BlobDownloader(this, storageManager, lifecycleScope)

        Log.i(TAG, "Components initialized")
        Log.i(TAG, "Session directory: ${storageManager.getSessionDir().absolutePath}")
    }

    /**
     * Setup WebView with all necessary configurations
     */
    private fun setupWebView() {
        webView = findViewById(R.id.webView)
        progressBar = findViewById(R.id.progressBar)

        // Enable JavaScript (required for Snapchat Web)
        webView.settings.javaScriptEnabled = true

        // Enable DOM storage
        webView.settings.domStorageEnabled = true

        // Enable database storage
        webView.settings.databaseEnabled = true

        // Enable caching
        webView.settings.cacheMode = WebSettings.LOAD_DEFAULT

        // Allow file access (needed for blob URLs)
        webView.settings.allowFileAccess = true
        webView.settings.allowContentAccess = true

        // Enable mixed content (HTTPS + HTTP)
        webView.settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW

        // Set User-Agent to Chrome Mobile to avoid WebView detection
        webView.settings.userAgentString =
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 " +
            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

        // Enable debugging (for development)
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)

        // Enable cookies
        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(webView, true)

        // Add JavaScript Interface for Blob downloading
        webView.addJavascriptInterface(blobDownloader, "Android")

        // Set custom WebViewClient for traffic interception
        webView.webViewClient = SnapWebViewClient(this, trafficLogger)

        // Set WebChromeClient for progress tracking
        webView.webChromeClient = object : android.webkit.WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                progressBar.progress = newProgress

                if (newProgress >= 100) {
                    progressBar.visibility = ProgressBar.GONE
                } else {
                    progressBar.visibility = ProgressBar.VISIBLE
                }
            }

            override fun onConsoleMessage(consoleMessage: android.webkit.ConsoleMessage?): Boolean {
                consoleMessage?.let {
                    Log.d(TAG, "[JS Console] ${it.message()} (${it.sourceId()}:${it.lineNumber()})")
                }
                return super.onConsoleMessage(consoleMessage)
            }
        }

        // Enable zoom controls
        webView.settings.setSupportZoom(true)
        webView.settings.builtInZoomControls = true
        webView.settings.displayZoomControls = false

        // Set viewport
        webView.settings.useWideViewPort = true
        webView.settings.loadWithOverviewMode = true

        Log.i(TAG, "WebView configured")
    }

    /**
     * Load Snapchat Web
     */
    private fun loadSnapchatWeb() {
        Log.i(TAG, "Loading $SNAPCHAT_WEB_URL...")

        Toast.makeText(
            this,
            "Loading Snapchat Web...\nTraffic recording active",
            Toast.LENGTH_LONG
        ).show()

        webView.loadUrl(SNAPCHAT_WEB_URL)
    }

    /**
     * Handle back button to navigate WebView history
     */
    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    /**
     * Save logs when app is paused
     */
    override fun onPause() {
        super.onPause()
        saveLogs()
    }

    /**
     * Save logs when app is destroyed
     */
    override fun onDestroy() {
        super.onDestroy()
        saveLogs()
        Log.i(TAG, "App destroyed, session ended")
    }

    /**
     * Save all traffic logs and blob metadata
     */
    private fun saveLogs() {
        try {
            Log.i(TAG, "Saving traffic logs...")

            // Save traffic logs
            trafficLogger.saveToFile()

            // Save blob metadata
            blobDownloader.saveMetadata()

            // Save summary
            val blobStats = blobDownloader.getStats()
            val trafficStats = trafficLogger.getStats()

            sessionStartTime?.let { startTime ->
                storageManager.saveSummary(
                    sessionStart = startTime,
                    requestCount = trafficStats["requests"] ?: 0,
                    responseCount = trafficStats["responses"] ?: 0,
                    blobCount = blobStats["total_blobs"] ?: 0,
                    uniqueBlobCount = blobStats["unique_blobs"] ?: 0,
                    domains = trafficLogger.getDomains()
                )
            }

            // Show stats
            val statsMessage = """
                Traffic Logs Saved!
                Requests: ${trafficStats["requests"]}
                Responses: ${trafficStats["responses"]}
                Blobs: ${blobStats["unique_blobs"]} unique, ${blobStats["duplicate_blobs"]} duplicates
                Location: ${storageManager.getSessionDir().absolutePath}
            """.trimIndent()

            Log.i(TAG, statsMessage)
            Toast.makeText(this, "Logs saved!", Toast.LENGTH_SHORT).show()

        } catch (e: Exception) {
            Log.e(TAG, "Error saving logs: ${e.message}")
            Toast.makeText(this, "Error saving logs: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }
}
