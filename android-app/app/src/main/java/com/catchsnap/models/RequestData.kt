package com.catchsnap.models

data class RequestData(
    val timestamp: String,
    val method: String,
    val url: String,
    val headers: Map<String, String>,
    val postData: String?,
    val resourceType: String
)
