/*
 * Copyright (c) 2026 Alexander Hill. SPDX-License-Identifier: MIT
 */
package com.fordservicedisc.viewer;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ConnectException;
import java.net.Socket;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.LinkedHashMap;
import java.util.Map;

/** Pure-Java regression harness for the Android wrapper's loopback HTTP server. */
public final class LoopbackHttpServerTest {
    private static int assertions;

    private LoopbackHttpServerTest() {
    }

    public static void main(String[] args) throws Exception {
        File parent = Files.createTempDirectory("ford-manual-http-test").toFile();
        File root = new File(parent, "site");
        if (!root.mkdir()) {
            throw new IOException("Could not create test site");
        }
        write(new File(root, "index.html"), "<h1>Manual</h1>");
        write(new File(root, "app.js"), "const ready = true;\n");
        write(new File(root, "manual.json"), "{\"model\":\"Ford\"}");
        write(new File(parent, "secret.txt"), "must not escape");

        LoopbackHttpServer server = new LoopbackHttpServer(root);
        server.start();
        URI base = URI.create(server.getBaseUrl());
        equal("127.0.0.1", base.getHost(), "server binds to IPv4 loopback");
        check(base.getPort() > 0, "server selects an ephemeral port");

        try {
            Response get = request(base, "GET /index.html?cache=bust HTTP/1.1\r\n");
            equal(200, get.status, "GET status");
            equal("<h1>Manual</h1>", get.body, "GET body and query stripping");
            startsWith("text/html", get.headers.get("content-type"), "HTML MIME type");
            equal(Integer.toString(get.body.getBytes(StandardCharsets.UTF_8).length),
                    get.headers.get("content-length"), "GET content length");

            Response javascript = request(base, "GET /app.js HTTP/1.1\r\n");
            startsWith("application/javascript", javascript.headers.get("content-type"),
                    "JavaScript MIME type");

            Response head = request(base, "HEAD /manual.json?ignored=yes HTTP/1.1\r\n");
            equal(200, head.status, "HEAD status");
            equal("", head.body, "HEAD has no body");
            startsWith("application/json", head.headers.get("content-type"), "JSON MIME type");
            equal(Long.toString(new File(root, "manual.json").length()),
                    head.headers.get("content-length"), "HEAD reports file length");

            equal(404, request(base, "GET /missing.html HTTP/1.1\r\n").status,
                    "missing file status");
            equal(404, request(base, "GET /../secret.txt HTTP/1.1\r\n").status,
                    "plain traversal status");
            equal(404, request(base, "GET /%2e%2e/secret.txt HTTP/1.1\r\n").status,
                    "encoded traversal status");

            Response method = request(base, "POST /index.html HTTP/1.1\r\n");
            equal(405, method.status, "unsupported method status");
            equal("GET, HEAD", method.headers.get("allow"), "unsupported method Allow header");
        } finally {
            server.close();
            server.close();
        }

        try {
            new Socket(base.getHost(), base.getPort()).close();
            throw new AssertionError("closed server still accepts connections");
        } catch (ConnectException expected) {
            assertions++;
        }

        System.out.println("LoopbackHttpServerTest: " + assertions + " assertions passed");
    }

    private static Response request(URI base, String requestLine) throws IOException {
        try (Socket socket = new Socket(base.getHost(), base.getPort())) {
            socket.setSoTimeout(5000);
            OutputStream out = socket.getOutputStream();
            out.write((requestLine + "Host: 127.0.0.1\r\nConnection: close\r\n\r\n")
                    .getBytes(StandardCharsets.US_ASCII));
            out.flush();

            byte[] raw = readAll(socket.getInputStream());
            int split = indexOf(raw, new byte[]{'\r', '\n', '\r', '\n'});
            if (split < 0) {
                throw new AssertionError("response has no header terminator");
            }
            String headerText = new String(raw, 0, split, StandardCharsets.US_ASCII);
            String[] lines = headerText.split("\\r\\n");
            String[] statusParts = lines[0].split(" ", 3);
            Map<String, String> headers = new LinkedHashMap<>();
            for (int i = 1; i < lines.length; i++) {
                int colon = lines[i].indexOf(':');
                if (colon > 0) {
                    headers.put(lines[i].substring(0, colon).trim().toLowerCase(),
                            lines[i].substring(colon + 1).trim());
                }
            }
            String body = new String(raw, split + 4, raw.length - split - 4,
                    StandardCharsets.UTF_8);
            return new Response(Integer.parseInt(statusParts[1]), headers, body);
        }
    }

    private static byte[] readAll(InputStream in) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        int count;
        while ((count = in.read(buffer)) != -1) {
            bytes.write(buffer, 0, count);
        }
        return bytes.toByteArray();
    }

    private static int indexOf(byte[] haystack, byte[] needle) {
        outer:
        for (int i = 0; i <= haystack.length - needle.length; i++) {
            for (int j = 0; j < needle.length; j++) {
                if (haystack[i + j] != needle[j]) {
                    continue outer;
                }
            }
            return i;
        }
        return -1;
    }

    private static void write(File file, String contents) throws IOException {
        try (FileOutputStream out = new FileOutputStream(file)) {
            out.write(contents.getBytes(StandardCharsets.UTF_8));
        }
    }

    private static void check(boolean condition, String message) {
        assertions++;
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private static void equal(Object expected, Object actual, String message) {
        assertions++;
        if (!expected.equals(actual)) {
            throw new AssertionError(message + ": expected " + expected + ", got " + actual);
        }
    }

    private static void startsWith(String expected, String actual, String message) {
        assertions++;
        if (actual == null || !actual.startsWith(expected)) {
            throw new AssertionError(message + ": expected prefix " + expected + ", got " + actual);
        }
    }

    private static final class Response {
        final int status;
        final Map<String, String> headers;
        final String body;

        Response(int status, Map<String, String> headers, String body) {
            this.status = status;
            this.headers = headers;
            this.body = body;
        }
    }
}
