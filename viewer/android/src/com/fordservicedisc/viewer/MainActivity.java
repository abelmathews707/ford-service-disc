/*
 * Copyright (c) 2026 Alexander Hill. SPDX-License-Identifier: MIT
 *
 * Offline wrapper for the ford-service-disc viewer. Loads the built static
 * site from /sdcard/FordManual in a WebView through a loopback-only server.
 *
 * The viewer is a fetch-based single-page app. Browsers block fetch() from
 * file:// pages, and current Android WebView ignores the legacy
 * "allow file access from file URLs" switches, so a plain file:// wrapper
 * would stall on the loading screen. This app instead serves the site from
 * a real HTTP server bound to 127.0.0.1, so same-origin fetch() works even on
 * WebView versions that do not reliably call shouldInterceptRequest(). The
 * app-level cleartext opt-in is required for this local URL on WebView 91;
 * network isolation comes from the server's loopback-only socket binding.
 */
package com.fordservicedisc.viewer;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.File;
import java.io.IOException;

public class MainActivity extends Activity {
    private static final int REQ_STORAGE = 1;
    private WebView web;
    private LoopbackHttpServer server;
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
        web.setWebViewClient(new WebViewClient());
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
            File root = new File(base);
            if (new File(root, "index.html").isFile()) {
                try {
                    server = new LoopbackHttpServer(root);
                    server.start();
                    web.loadUrl(server.getBaseUrl() + "/index.html");
                    return;
                } catch (IOException e) {
                    showError("Could not start the local manual server.");
                    return;
                }
            }
        }
        showError("Manual not found. Copy the built site to /sdcard/FordManual first.");
    }

    private void showError(String message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
        web.loadData("<h2>Ford Service Manual</h2><p>" + message + "</p>"
                + "<p>Build the site with <code>python3 -m fsd all DISC -o site</code>, "
                + "copy the <code>site</code> directory to <b>/sdcard/FordManual</b> on "
                + "this device, then reopen this app.</p>", "text/html", "utf-8");
    }

    @Override
    protected void onDestroy() {
        if (server != null) {
            server.close();
            server = null;
        }
        if (web != null) {
            web.stopLoading();
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
