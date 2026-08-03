/*
 * Copyright (c) 2026 Alexander Hill. SPDX-License-Identifier: MIT
 *
 * Offline wrapper for the ford-service-disc viewer. Loads the built static
 * site from /sdcard/FordManual with a WebView, with no network access.
 *
 * The viewer is a fetch-based single-page app, so a browser opening
 * index.html from file:// would block its content requests. This app turns
 * on WebView's file access (including fetch across local file URLs) and
 * points it at the local copy.
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

public class MainActivity extends Activity {
    private static final int REQ_STORAGE = 1;
    private WebView web;
    private boolean tried;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        // The viewer loads its content with fetch(); from a file:// origin
        // that only works if the WebView permits local file access.
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
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
            if (new File(base, "index.html").exists()) {
                web.loadUrl("file://" + base + "/index.html");
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

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
