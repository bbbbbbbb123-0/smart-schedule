package kz.asckwab.inderbuswatch

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var statusView: TextView
    private val prefs by lazy { getSharedPreferences(BusCheckService.PREFS, MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermissionIfNeeded()
        buildUi()
    }

    override fun onResume() {
        super.onResume()
        if (::statusView.isInitialized) updateStatus()
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(24), dp(20), dp(20))
            setBackgroundColor(0xFFF7F7F7.toInt())
        }
        val scroll = ScrollView(this)
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
        }
        scroll.addView(content)
        content.addView(TextView(this).apply {
            text = "Билеты Индер — Атырау"
            textSize = 25f
            setTextColor(0xFF16202A.toInt())
            gravity = Gravity.CENTER
        }, matchWrap())
        content.addView(TextView(this).apply {
            text = "26 октября 2026 · отправление в 17:00 · рейс 110И"
            textSize = 16f
            gravity = Gravity.CENTER
            setTextColor(0xFF46515C.toInt())
            setPadding(0, dp(12), 0, dp(18))
        }, matchWrap())

        statusView = TextView(this).apply {
            textSize = 16f
            setTextColor(0xFF202830.toInt())
            setBackgroundColor(0xFFFFFFFF.toInt())
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        content.addView(statusView, matchWrap())
        content.addView(makeButton("Проверить места сейчас") {
            startCheck(monitor = prefs.getBoolean(BusCheckService.KEY_MONITORING, false))
        })
        content.addView(makeButton("Включить проверку каждый час") {
            prefs.edit().putBoolean(BusCheckService.KEY_MONITORING, true).apply()
            startCheck(monitor = true)
        })
        content.addView(makeButton("Выключить мониторинг") {
            prefs.edit().putBoolean(BusCheckService.KEY_MONITORING, false).apply()
            CheckAlarmReceiver.cancel(this)
            updateStatus()
        })
        content.addView(makeButton("Открыть страницу рейса") {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(BusCheckService.ROUTE_URL)))
        })
        content.addView(TextView(this).apply {
            text = "Приложение читает схему мест с актуальной страницы сайта и уведомляет только при наличии свободных мест (status-0). Бронь (status-4) свободным местом не считается. Android может задерживать фоновые проверки в режиме энергосбережения. Мониторинг прекращается после отправления 26 октября."
            textSize = 13f
            setTextColor(0xFF606A73.toInt())
            setPadding(0, dp(18), 0, 0)
        }, matchWrap())
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
        updateStatus()
    }

    private fun makeButton(label: String, action: () -> Unit): Button = Button(this).apply {
        text = label
        isAllCaps = false
        textSize = 15f
        setOnClickListener { action() }
        layoutParams = LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(10) }
    }

    private fun startCheck(monitor: Boolean) {
        if (monitor) prefs.edit().putBoolean(BusCheckService.KEY_MONITORING, true).apply()
        val intent = Intent(this, BusCheckService::class.java).putExtra(BusCheckService.EXTRA_CONTINUE, monitor)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
        statusView.text = if (monitor) "Проверка запущена. Мониторинг включён." else "Проверяю сайт…"
    }

    private fun updateStatus() {
        val last = prefs.getString(BusCheckService.KEY_LAST_RESULT, null)
        val monitoring = prefs.getBoolean(BusCheckService.KEY_MONITORING, false)
        statusView.text = buildString {
            append(if (monitoring) "Мониторинг включён" else "Мониторинг выключен")
            append("\n\n")
            append(last ?: "Проверка ещё не выполнялась.")
        }
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 71)
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
    private fun matchWrap() = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
}
