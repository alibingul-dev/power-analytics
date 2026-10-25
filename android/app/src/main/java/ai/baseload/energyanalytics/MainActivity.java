package ai.baseload.energyanalytics;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.window.OnBackInvokedDispatcher;

import com.google.android.play.core.review.ReviewInfo;
import com.google.android.play.core.review.ReviewManager;
import com.google.android.play.core.review.ReviewManagerFactory;

/* The app opens the live site, so the daily data arrives without an app update.
   Pages of the site stay inside the app; every other link (LinkedIn, sources, GitHub)
   opens in its own app or the browser. No account, nothing stored by the app itself. */
public class MainActivity extends Activity {

    private static final String HOST = "alibingul-dev.github.io";
    private static final String PATH = "/power-analytics";
    private static final String START = "https://" + HOST + PATH + "/?source=android";
    private static final String OFFLINE = "file:///android_asset/offline.html";
    // back from the background after this long: reload so today's data shows
    private static final long STALE_MS = 30L * 60L * 1000L;

    private WebView web;
    private long pausedAt = 0L;

    @SuppressLint("SetJavaScriptEnabled")
    @SuppressWarnings("deprecation")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Android 15+ always draws edge to edge; do the same on older versions so the insets
        // below mean the same everywhere, then keep the page clear of the status and navigation bars
        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        }
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF0E1520);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                Insets b = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                v.setPadding(b.left, b.top, b.right, b.bottom);
            } else {
                v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                        insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });

        web = new WebView(this);
        web.setBackgroundColor(0xFF0E1520);
        root.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setSupportMultipleWindows(false);
        s.setMediaPlaybackRequiresUserGesture(true);
        s.setUserAgentString(s.getUserAgentString() + " EnergyAnalyticsAndroid/" + BuildConfig.VERSION_NAME);

        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (isOurs(u)) return false;
                openOutside(u);
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                // only the page itself failing means "offline"; a missing image or font does not
                if (req.isForMainFrame()) view.loadUrl(OFFLINE);
            }
        });

        // the site's MP4 "Download" links: WebView cannot save files, let the browser do it
        web.setDownloadListener((url, ua, cd, mime, len) -> openOutside(Uri.parse(url)));

        web.addJavascriptInterface(new Bridge(), "PAAndroid");

        if (Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::goBack);
        }

        if (savedInstanceState != null) web.restoreState(savedInstanceState);
        else web.loadUrl(START);
    }

    private boolean isOurs(Uri u) {
        if ("file".equals(u.getScheme())) return true;
        String p = u.getPath() == null ? "" : u.getPath();
        return HOST.equals(u.getHost()) && (p.equals(PATH) || p.startsWith(PATH + "/"));
    }

    private void goBack() {
        if (web != null && web.canGoBack()) {
            String cur = web.getUrl();
            if (cur != null && cur.startsWith(OFFLINE)) { finish(); return; }
            web.goBack();
        } else {
            finish();
        }
    }

    @SuppressWarnings("deprecation")
    @Override
    public void onBackPressed() {
        goBack();
    }

    public class Bridge {
        /* share sheet: WebView has no navigator.share */
        @JavascriptInterface
        public void share(String text) {
            runOnUiThread(() -> {
                try {
                    Intent i = new Intent(Intent.ACTION_SEND);
                    i.setType("text/plain");
                    i.putExtra(Intent.EXTRA_TEXT, text == null ? "" : text);
                    startActivity(Intent.createChooser(i, null));
                } catch (Exception ignored) { }
            });
        }

        /* Play's rating sheet; if Play declines, open the store page so the button never does nothing */
        @JavascriptInterface
        public void review() {
            runOnUiThread(() -> {
                try {
                    final ReviewManager m = ReviewManagerFactory.create(MainActivity.this);
                    m.requestReviewFlow().addOnCompleteListener(t -> {
                        if (t.isSuccessful()) {
                            ReviewInfo info = t.getResult();
                            m.launchReviewFlow(MainActivity.this, info);
                        } else {
                            openStore();
                        }
                    });
                } catch (Exception e) {
                    openStore();
                }
            });
        }

        /* the offline page's "Try again" */
        @JavascriptInterface
        public void retry() {
            runOnUiThread(() -> { if (web != null) web.loadUrl(START); });
        }
    }

    private void openStore() {
        openOutside(Uri.parse("https://play.google.com/store/apps/details?id=" + getPackageName()));
    }

    private void openOutside(Uri u) {
        try {
            if ("play.google.com".equals(u.getHost()) && u.getQueryParameter("id") != null) {
                startActivity(new Intent(Intent.ACTION_VIEW,
                        Uri.parse("market://details?id=" + u.getQueryParameter("id"))));
                return;
            }
        } catch (ActivityNotFoundException ignored) { }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, u));
        } catch (ActivityNotFoundException ignored) { }
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        if (web != null) web.saveState(out);
    }

    @Override
    protected void onPause() {
        pausedAt = SystemClock.elapsedRealtime();
        if (web != null) web.onPause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web == null) return;
        web.onResume();
        if (pausedAt > 0 && SystemClock.elapsedRealtime() - pausedAt > STALE_MS) {
            String cur = web.getUrl();
            if (cur == null || cur.startsWith(OFFLINE)) web.loadUrl(START);
            else web.reload();
        }
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            ((FrameLayout) web.getParent()).removeView(web);
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
