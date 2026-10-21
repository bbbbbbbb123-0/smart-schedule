package kz.asckwab.inderbuswatch

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONObject
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.format.DateTimeFormatter

class BusCheckService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private var webView: WebView? = null
    private var completed = false
    private var startIdForRun = 0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startIdForRun = startId
        createNotificationChannels()
        startForeground(CHECKING_NOTIFICATION_ID, checkingNotification())
        handler.post { beginCheck() }
        return START_NOT_STICKY
    }

    private fun beginCheck() {
        if (!withinMonitoringWindow()) {
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean(KEY_MONITORING, false).apply()
            CheckAlarmReceiver.cancel(this)
            finishService()
            return
        }
        completed = false
        val view = WebView(this)
        webView = view
        view.settings.javaScriptEnabled = true
        view.settings.domStorageEnabled = true
        view.settings.allowFileAccess = false
        view.settings.allowContentAccess = false
        view.settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        view.addJavascriptInterface(ResultBridge { json -> handler.post { handleResult(json) } }, "BusWatchBridge")
        view.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String) {
                if (completed) return
                handler.postDelayed({ selectDepartureAndRead(view) }, 700)
            }
        }
        view.loadUrl(ROUTE_URL)
        handler.postDelayed({
            if (!completed) handleResult("""{"ok":false,"error":"Превышено время ожидания сайта"}""")
        }, 28_000)
    }

    private fun selectDepartureAndRead(view: WebView) {
        if (completed || webView !== view) return
        val js = """
            (function() {
              try {
                var targetDate = '26.10.2026';
                var dateText = (document.querySelector('.js-date-text') || {}).textContent || '';
                var rows = Array.from(document.querySelectorAll('tr[data-dep-id]'));
                var row = rows.find(function(r) {
                  var t = r.querySelector('.js-timed');
                  return t && t.textContent.trim() === '17:00';
                });
                if (!row) {
                  BusWatchBridge.onResult(JSON.stringify({ok:false,error:'В расписании не найдено отправление 17:00'}));
                  return;
                }
                if (dateText.trim() && dateText.trim() !== targetDate) {
                  BusWatchBridge.onResult(JSON.stringify({ok:false,error:'Сайт открыл другую дату: ' + dateText.trim()}));
                  return;
                }
                if (!row.classList.contains('active')) {
                  row.click();
                  setTimeout(report, 3800);
                } else {
                  setTimeout(report, 1600);
                }
                function report() {
                  try {
                    var active = Array.from(document.querySelectorAll('tr.active')).find(function(r) {
                      var t = r.querySelector('.js-timed');
                      return t && t.textContent.trim() === '17:00';
                    });
                    var scheme = document.querySelector('.js-bus-scheme');
                    var seats = scheme ? Array.from(scheme.querySelectorAll('span.place.status-0, span.place.status-1, span.place.status-4')) : [];
                    if (!active || !scheme || seats.length === 0) {
                      BusWatchBridge.onResult(JSON.stringify({ok:false,error:'Сайт не загрузил схему выбранного рейса'}));
                      return;
                    }
                    var free = scheme.querySelectorAll('span.place.status-0').length;
                    var occupied = scheme.querySelectorAll('span.place.status-1').length;
                    var booked = scheme.querySelectorAll('span.place.status-4').length;
                    var message = (document.querySelector('#js-message') || {}).textContent || '';
                    BusWatchBridge.onResult(JSON.stringify({ok:true,free:free,occupied:occupied,booked:booked,total:seats.length,message:message.trim()}));
                  } catch (e) {
                    BusWatchBridge.onResult(JSON.stringify({ok:false,error:'Ошибка чтения схемы'}));
                  }
                }
              } catch (e) {
                BusWatchBridge.onResult(JSON.stringify({ok:false,error:'Ошибка проверки страницы'}));
              }
            })();
        """.trimIndent()
        view.evaluateJavascript(js, null)
    }

    private fun handleResult(raw: String) {
        if (completed) return
        completed = true
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        val now = LocalDateTime.now().format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
        var shouldNotify = false
        var free = 0
        val resultText = try {
            val json = JSONObject(raw)
            if (!json.optBoolean("ok", false)) {
                val errorText = json.optString("error", "Неизвестная ошибка")
                "Не удалось подтвердить наличие мест ($now). $errorText."
            } else {
                free = json.optInt("free", 0)
                val occupied = json.optInt("occupied", 0)
                val booked = json.optInt("booked", 0)
                val total = json.optInt("total", 0)
                if (total <= 0) {
                    "Не удалось прочитать схему мест ($now). Повторю проверку позже."
                } else if (free > 0) {
                    shouldNotify = true
                    "НАЙДЕНЫ СВОБОДНЫЕ МЕСТА: $free ($now). Всего в схеме: $total; занято: $occupied; бронь: $booked."
                } else {
                    "Свободных мест нет ($now). Занято: $occupied; бронь: $booked; всего: $total."
                }
            }
        } catch (_: Exception) {
            "Не удалось проверить сайт ($now). Ответ схемы имеет неизвестный формат."
        }
        prefs.edit().putString(KEY_LAST_RESULT, resultText).putLong(KEY_LAST_CHECK_MILLIS, System.currentTimeMillis()).apply()
        if (shouldNotify && free > 0) sendAvailableNotification(free, resultText)
        finishService()
    }

    private fun finishService() {
        try {
            webView?.stopLoading()
            webView?.removeJavascriptInterface("BusWatchBridge")
            webView?.destroy()
        } catch (_: Exception) { }
        webView = null
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        val monitoring = prefs.getBoolean(KEY_MONITORING, false)
        if (monitoring && withinMonitoringWindow()) CheckAlarmReceiver.scheduleNext(this)
        else CheckAlarmReceiver.cancel(this)
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.cancel(CHECKING_NOTIFICATION_ID)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf(startIdForRun)
    }

    private fun withinMonitoringWindow(): Boolean {
        val today = LocalDate.now()
        val target = LocalDate.of(2026, 10, 26)
        return today.isBefore(target) || (today == target && LocalTime.now().isBefore(LocalTime.of(17, 0)))
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= 26) {
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(NotificationChannel(CHANNEL_ID, "Проверка билетов", NotificationManager.IMPORTANCE_LOW))
            manager.createNotificationChannel(NotificationChannel(AVAILABLE_CHANNEL_ID, "Свободные билеты", NotificationManager.IMPORTANCE_HIGH))
        }
    }

    private fun checkingNotification(): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_search)
            .setContentTitle("Проверяю билеты Индер — Атырау")
            .setContentText("Рейс 26 октября, 17:00")
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    private fun sendAvailableNotification(free: Int, detail: String) {
        val open = PendingIntent.getActivity(this, 1, Intent(this, MainActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val n = Notification.Builder(this, AVAILABLE_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Появились билеты: Индер → Атырау")
            .setContentText("На рейс 26.10.2026 в 17:00 свободных мест: $free")
            .setStyle(Notification.BigTextStyle().bigText(detail))
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(AVAILABLE_NOTIFICATION_ID, n)
    }

    private class ResultBridge(private val result: (String) -> Unit) {
        @JavascriptInterface
        fun onResult(json: String) { result(json) }
    }

    override fun onDestroy() {
        try { webView?.destroy() } catch (_: Exception) { }
        webView = null
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    companion object {
        const val PREFS = "inder_bus_watch"
        const val KEY_MONITORING = "monitoring"
        const val KEY_LAST_RESULT = "last_result"
        const val KEY_LAST_CHECK_MILLIS = "last_check_millis"
        const val EXTRA_CONTINUE = "continue_monitoring"
        const val ROUTE_URL = "https://atyraubus.kz/%D1%80%D0%B0%D1%81%D0%BF%D0%B8%D1%81%D0%B0%D0%BD%D0%B8%D0%B5-%D0%B0%D0%B2%D1%82%D0%BE%D0%B1%D1%83%D1%81%D0%BE%D0%B2/%D0%BC%D0%B0%D1%80%D1%88%D1%80%D1%83%D1%82/atyrau-state-437?date=26.10.2026&to=451757833&from=1542563949"
        private const val CHANNEL_ID = "bus_watch_running"
        private const val AVAILABLE_CHANNEL_ID = "bus_watch_available"
        private const val CHECKING_NOTIFICATION_ID = 11
        private const val AVAILABLE_NOTIFICATION_ID = 12
    }
}
