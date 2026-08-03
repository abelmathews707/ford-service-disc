/*
 * Copyright (c) 2026 Alexander Hill. SPDX-License-Identifier: MIT
 *
 * Offline wrapper for the ford-service-disc viewer. Loads the built static
 * site from /sdcard/FordManual in a WebView with no network access.
 *
 * The viewer is a fetch-based single-page app. Browsers block fetch() from
 * file:// pages, and current Android WebView ignores the legacy
 * "allow file access from file URLs" switches, so a plain file:// wrapper
 * would stall on the loading screen. This app instead serves the site from
 * a virtual http://127.0.0.1 origin: every request is intercepted and
 * answered by reading the matching file off local storage, so same-origin
 * fetch() works exactly as it does on a real server.
 */
package com.fordservicedisc.viewer;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;

public class MainActivity extends Activity {
    private static final int REQ_STORAGE = 1;
    private static final String ORIGIN = "http://127.0.0.1";
    private WebView web;
    private File root;
    private boolean tried;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return serve(request);
            }
        });
        setContentView(web);

        if (Build.VERSION.SDK_INT >= 23
                && checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE)
                   != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.READ_EXTERNAL_STORAGE}, REQ_STORAGE);
        } else {
            load();
        }
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        if (!tried) load();
    }

    private void load() {
        tried = true;
        for (String base : new String[]{"/sdcard/FordManual", "/storage/emulated/0/FordManual"}) {
            if (new File(base, "index.html").exists()) {
                root = new File(base);
                web.loadUrl(ORIGIN + "/index.html");
                return;
            }
        }
        Toast.makeText(this, "Manual not found. Copy the built site to /sdcard/FordManual first.",
                Toast.LENGTH_LONG).show();
        web.loadData("<h2>Ford Service Manual</h2>"
                + "<p>Build the site with <code>python3 -m fsd all DISC -o site</code>, "
                + "copy the <code>site</code> directory to <b>/sdcard/FordManual</b> on "
                + "this device, then reopen this app.</p>", "text/html", "utf-8");
    }

    private WebResourceResponse serve(WebResourceRequest request) {
        Uri uri = request.getUrl();
        if (root == null || !ORIGIN.equals(uri.getScheme() + "://" + uri.getHost())) {
            return null; // not ours; let the WebView handle it
        }
        String path = uri.getPath(); // query string already stripped
        if (path == null || path.contains("..")) {
            return error404();
        }
        File f = new File(root, path.startsWith("/") ? path.substring(1) : path);
        if (!f.exists() || !f.isFile()) {
            return error404();
        }
        try {
            String mime = mimeOf(path);
            String enc = (mime.startsWith("text/") || mime.contains("json")
                    || mime.contains("javascript") || mime.contains("svg")) ? "utf-8" : null;
            return new WebResourceResponse(mime, enc, new FileInputStream(f));
        } catch (FileNotFoundException e) {
            return error404();
        }
    }

    private static WebResourceResponse error404() {
        return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", null, null);
    }

    private static String mimeOf(String path) {
        String ext = path.contains(".")
                ? path.substring(path.lastIndexOf('.') + 1).toLowerCase() : "";
        switch (ext) {
            case "html": case "htm": return "text/html";
            case "js": return "application/javascript";
            case "css": return "text/css";
            case "json": return "application/json";
            case "jpg": case "jpeg": return "image/jpeg";
            case "png": return "image/png";
            case "gif": return "image/gif";
            case "svg": return "image/svg+xml";
            case "webp": return "image/webp";
            case "pdf": return "application/pdf";
            case "txt": return "text/plain";
            default: return "application/octet-stream";
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
