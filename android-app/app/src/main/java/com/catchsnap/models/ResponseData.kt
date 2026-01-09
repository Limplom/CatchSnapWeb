package com.catchsnap.models

data class ResponseData(
    val timestamp: String,
    val url: String,
    val status: Int,
    val statusText: String,
    val headers: Map<String, String>,
    val contentType: String,
    val body: String? = null,
    val bodyError: String? = null
)
