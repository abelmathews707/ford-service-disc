/*
 * Copyright (c) 2026 Alexander Hill. SPDX-License-Identifier: MIT
 */
package com.fordservicedisc.viewer;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.Closeable;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketException;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** A minimal static-file HTTP server reachable only through IPv4 loopback. */
public final class LoopbackHttpServer implements Closeable {
    private static final int MAX_LINE_LENGTH = 8192;
    private static final int MAX_HEADER_LINES = 100;
    private static final int SOCKET_TIMEOUT_MS = 5000;

    private final File root;
    private final String rootPath;
    private final Set<Socket> clients = Collections.synchronizedSet(new HashSet<Socket>());

    private volatile boolean running;
    private volatile int port;
    private ServerSocket listener;
    private ExecutorService workers;
    private Thread acceptThread;

    public LoopbackHttpServer(File root) throws IOException {
        if (root == null) {
            throw new NullPointerException("root");
        }
        this.root = root.getCanonicalFile();
        if (!this.root.isDirectory()) {
            throw new IOException("Not a directory: " + root);
        }
        this.rootPath = this.root.getPath();
    }

    /** Starts the server on 127.0.0.1 and lets the OS select an unused port. */
    public synchronized void start() throws IOException {
        if (running) {
            return;
        }

        ServerSocket newListener = new ServerSocket();
        try {
            newListener.setReuseAddress(true);
            newListener.bind(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0));
        } catch (IOException e) {
            closeQuietly(newListener);
            throw e;
        }

        final ExecutorService newWorkers = Executors.newFixedThreadPool(
                4, new NamedThreadFactory("ford-http-worker"));
        workers = newWorkers;
        listener = newListener;
        port = newListener.getLocalPort();
        running = true;
        acceptThread = new Thread(new Runnable() {
            @Override
            public void run() {
                acceptConnections(newListener, newWorkers);
            }
        }, "ford-http-accept");
        acceptThread.setDaemon(true);
        acceptThread.start();
    }

    public String getBaseUrl() {
        if (!running || port == 0) {
            throw new IllegalStateException("Server is not running");
        }
        return "http://127.0.0.1:" + port;
    }

    private void acceptConnections(ServerSocket serverSocket, ExecutorService workerPool) {
        while (running) {
            Socket client = null;
            try {
                client = serverSocket.accept();
                if (!running) {
                    closeQuietly(client);
                    break;
                }
                client.setSoTimeout(SOCKET_TIMEOUT_MS);
                client.setTcpNoDelay(true);
                clients.add(client);
                final Socket accepted = client;
                workerPool.execute(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            handle(accepted);
                        } finally {
                            clients.remove(accepted);
                            closeQuietly(accepted);
                        }
                    }
                });
            } catch (RejectedExecutionException e) {
                clients.remove(client);
                closeQuietly(client);
            } catch (SocketException e) {
                closeQuietly(client);
                if (running) {
                    running = false;
                }
            } catch (IOException e) {
                closeQuietly(client);
                if (running) {
                    running = false;
                }
            }
        }
    }

    private void handle(Socket socket) {
        try {
            InputStream in = new BufferedInputStream(socket.getInputStream());
            OutputStream out = new BufferedOutputStream(socket.getOutputStream());
            String requestLine = readLine(in);
            if (requestLine == null || requestLine.length() == 0) {
                return;
            }

            String[] request = requestLine.split(" ", -1);
            if (request.length != 3 || !request[2].startsWith("HTTP/")) {
                sendText(out, 400, "Bad Request", "Bad Request\n", false, null);
                return;
            }

            for (int i = 0; i < MAX_HEADER_LINES; i++) {
                String header = readLine(in);
                if (header == null || header.length() == 0) {
                    break;
                }
                if (i == MAX_HEADER_LINES - 1) {
                    sendText(out, 400, "Bad Request", "Bad Request\n", false, null);
                    return;
                }
            }

            boolean head = "HEAD".equals(request[0]);
            if (!head && !"GET".equals(request[0])) {
                sendText(out, 405, "Method Not Allowed", "Method Not Allowed\n", false,
                        "Allow: GET, HEAD\r\n");
                return;
            }

            File file = resolve(request[1]);
            if (file == null || !file.isFile()) {
                sendText(out, 404, "Not Found", "Not Found\n", head, null);
                return;
            }
            sendFile(out, file, head);
        } catch (IOException ignored) {
            // A WebView navigation can close a request at any point. The next
            // connection remains independent, so there is nothing to recover.
        }
    }

    private File resolve(String target) throws IOException {
        int query = target.indexOf('?');
        String rawPath = query >= 0 ? target.substring(0, query) : target;
        if (!rawPath.startsWith("/")) {
            return null;
        }

        final String path;
        try {
            path = new URI(rawPath).getPath();
        } catch (URISyntaxException e) {
            return null;
        }
        if (path == null || path.indexOf('\0') >= 0 || path.indexOf('\\') >= 0) {
            return null;
        }
        for (String segment : path.split("/", -1)) {
            if ("..".equals(segment)) {
                return null;
            }
        }

        String relative = path.length() == 1 ? "index.html" : path.substring(1);
        File file = new File(root, relative).getCanonicalFile();
        String filePath = file.getPath();
        if (!filePath.equals(rootPath) && !filePath.startsWith(rootPath + File.separator)) {
            return null;
        }
        return file;
    }

    private static void sendFile(OutputStream out, File file, boolean head) throws IOException {
        String contentType = mimeOf(file.getName());
        writeHeaders(out, 200, "OK", contentType, file.length(), null);
        if (!head) {
            try (InputStream fileIn = new FileInputStream(file)) {
                byte[] buffer = new byte[16384];
                int count;
                while ((count = fileIn.read(buffer)) != -1) {
                    out.write(buffer, 0, count);
                }
            }
        }
        out.flush();
    }

    private static void sendText(OutputStream out, int status, String reason, String body,
                                 boolean head, String extraHeaders) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        writeHeaders(out, status, reason, "text/plain; charset=utf-8", bytes.length,
                extraHeaders);
        if (!head) {
            out.write(bytes);
        }
        out.flush();
    }

    private static void writeHeaders(OutputStream out, int status, String reason,
                                     String contentType, long contentLength,
                                     String extraHeaders) throws IOException {
        StringBuilder headers = new StringBuilder();
        headers.append("HTTP/1.1 ").append(status).append(' ').append(reason).append("\r\n")
                .append("Content-Type: ").append(contentType).append("\r\n")
                .append("Content-Length: ").append(contentLength).append("\r\n")
                .append("Connection: close\r\n");
        if (extraHeaders != null) {
            headers.append(extraHeaders);
        }
        headers.append("\r\n");
        out.write(headers.toString().getBytes(StandardCharsets.US_ASCII));
    }

    private static String readLine(InputStream in) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        boolean carriageReturn = false;
        while (bytes.size() <= MAX_LINE_LENGTH) {
            int value = in.read();
            if (value == -1) {
                return bytes.size() == 0 ? null
                        : new String(bytes.toByteArray(), StandardCharsets.US_ASCII);
            }
            if (carriageReturn) {
                if (value == '\n') {
                    return new String(bytes.toByteArray(), StandardCharsets.US_ASCII);
                }
                bytes.write('\r');
                carriageReturn = false;
            }
            if (value == '\r') {
                carriageReturn = true;
            } else if (value == '\n') {
                return new String(bytes.toByteArray(), StandardCharsets.US_ASCII);
            } else {
                bytes.write(value);
            }
        }
        throw new IOException("HTTP line too long");
    }

    private static String mimeOf(String name) {
        int dot = name.lastIndexOf('.');
        String extension = dot >= 0 ? name.substring(dot + 1).toLowerCase(Locale.US) : "";
        switch (extension) {
            case "html":
            case "htm":
                return "text/html; charset=utf-8";
            case "css":
                return "text/css; charset=utf-8";
            case "js":
            case "mjs":
                return "application/javascript; charset=utf-8";
            case "json":
                return "application/json; charset=utf-8";
            case "xml":
                return "application/xml; charset=utf-8";
            case "txt":
                return "text/plain; charset=utf-8";
            case "csv":
                return "text/csv; charset=utf-8";
            case "jpg":
            case "jpeg":
                return "image/jpeg";
            case "png":
                return "image/png";
            case "gif":
                return "image/gif";
            case "svg":
                return "image/svg+xml; charset=utf-8";
            case "webp":
                return "image/webp";
            case "ico":
                return "image/x-icon";
            case "pdf":
                return "application/pdf";
            case "woff":
                return "font/woff";
            case "woff2":
                return "font/woff2";
            case "ttf":
                return "font/ttf";
            case "otf":
                return "font/otf";
            default:
                return "application/octet-stream";
        }
    }

    @Override
    public void close() {
        final ServerSocket oldListener;
        final ExecutorService oldWorkers;
        final Thread oldAcceptThread;
        synchronized (this) {
            if (!running && listener == null) {
                return;
            }
            running = false;
            oldListener = listener;
            oldWorkers = workers;
            oldAcceptThread = acceptThread;
            listener = null;
            workers = null;
            acceptThread = null;
        }

        closeQuietly(oldListener);
        synchronized (clients) {
            for (Socket client : clients) {
                closeQuietly(client);
            }
            clients.clear();
        }

        if (oldWorkers != null) {
            oldWorkers.shutdownNow();
        }
        if (oldAcceptThread != null && oldAcceptThread != Thread.currentThread()) {
            try {
                oldAcceptThread.join(2000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        if (oldWorkers != null) {
            try {
                oldWorkers.awaitTermination(2, TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    private static void closeQuietly(Closeable closeable) {
        if (closeable != null) {
            try {
                closeable.close();
            } catch (IOException ignored) {
                // Closing is best-effort during shutdown.
            }
        }
    }

    private static final class NamedThreadFactory implements ThreadFactory {
        private final String name;
        private final AtomicInteger sequence = new AtomicInteger();

        NamedThreadFactory(String name) {
            this.name = name;
        }

        @Override
        public Thread newThread(Runnable runnable) {
            Thread thread = new Thread(runnable, name + '-' + sequence.incrementAndGet());
            thread.setDaemon(true);
            return thread;
        }
    }
}
