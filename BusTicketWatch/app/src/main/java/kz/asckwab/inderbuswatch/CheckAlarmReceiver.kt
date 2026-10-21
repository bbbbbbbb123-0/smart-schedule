package kz.asckwab.inderbuswatch

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

class CheckAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val prefs = context.getSharedPreferences(BusCheckService.PREFS, Context.MODE_PRIVATE)
        if (!prefs.getBoolean(BusCheckService.KEY_MONITORING, false)) return
        val serviceIntent = Intent(context, BusCheckService::class.java).putExtra(BusCheckService.EXTRA_CONTINUE, true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(serviceIntent)
        else context.startService(serviceIntent)
    }

    companion object {
        fun scheduleNext(context: Context) {
            val alarm = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val pending = PendingIntent.getBroadcast(context, 110, Intent(context, CheckAlarmReceiver::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, System.currentTimeMillis() + 60L * 60L * 1000L, pending)
        }

        fun cancel(context: Context) {
            val alarm = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val pending = PendingIntent.getBroadcast(context, 110, Intent(context, CheckAlarmReceiver::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            alarm.cancel(pending)
        }
    }
}
