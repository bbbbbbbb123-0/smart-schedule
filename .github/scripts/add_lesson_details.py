from pathlib import Path
import re

root = Path("project")

grade_models = r'''package kz.asckwab.smartschedule

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

data class SubjectGrades(
    val subject: String,
    val grades: List<String>,
    val journalId: String = ""
) {
    val numericGrades: List<Double>
        get() = grades.mapNotNull { it.replace(',', '.').toDoubleOrNull() }
            .filter { it.isFinite() && it in 0.0..100.0 }

    val average: Double?
        get() = numericGrades.takeIf { it.isNotEmpty() }?.average()
}

object GradeStorage {
    private const val PREFS = "smart_schedule_grade_data"
    private const val KEY_JSON = "subject_grades_json"

    fun saveFromWebJson(context: Context, raw: String): Boolean {
        return try {
            val root = JSONObject(raw)
            if (!root.optBoolean("ok", false)) return false
            val input = root.optJSONArray("subjects") ?: JSONArray()
            if (input.length() == 0) return false

            val updated = loadAll(context).toMutableList()
            var recognized = false
            for (i in 0 until input.length()) {
                val obj = input.optJSONObject(i) ?: continue
                val subject = obj.optString("subject").trim()
                if (subject.isBlank()) continue
                val journalId = obj.optString("journalId").trim()
                val marks = obj.optJSONArray("grades") ?: JSONArray()
                val grades = (0 until marks.length()).mapNotNull { j ->
                    val value = marks.optString(j).trim().replace(',', '.')
                    val n = value.toDoubleOrNull()
                    if (value.isNotBlank() && n != null && n.isFinite() && n in 0.0..100.0) value else null
                }
                val entry = SubjectGrades(subject, grades, journalId)
                val index = updated.indexOfFirst {
                    if (journalId.isNotBlank() && it.journalId.isNotBlank()) it.journalId == journalId
                    else normalize(it.subject) == normalize(subject)
                }
                if (index >= 0) {
                    // Empty pages must not erase grades previously captured from the same journal.
                    if (grades.isNotEmpty()) updated[index] = entry
                } else {
                    updated += entry
                }
                recognized = true
            }
            if (!recognized) return false

            val jsonSubjects = JSONArray()
            updated.forEach { record ->
                jsonSubjects.put(JSONObject()
                    .put("subject", record.subject)
                    .put("journalId", record.journalId)
                    .put("grades", JSONArray(record.grades)))
            }
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString(KEY_JSON, JSONObject().put("subjects", jsonSubjects).toString())
                .putLong("synced_at", System.currentTimeMillis())
                .apply()
            ScheduleWidgetProvider.updateAll(context)
            true
        } catch (_: Exception) {
            false
        }
    }

    fun loadAll(context: Context): List<SubjectGrades> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_JSON, null) ?: return emptyList()
        return try {
            val array = JSONObject(raw).optJSONArray("subjects") ?: JSONArray()
            (0 until array.length()).mapNotNull { i ->
                val obj = array.optJSONObject(i) ?: return@mapNotNull null
                val subject = obj.optString("subject").trim()
                if (subject.isBlank()) return@mapNotNull null
                val values = obj.optJSONArray("grades") ?: JSONArray()
                val grades = (0 until values.length()).mapNotNull { j ->
                    val value = values.optString(j).trim().replace(',', '.')
                    val n = value.toDoubleOrNull()
                    if (n != null && n.isFinite() && n in 0.0..100.0) value else null
                }
                SubjectGrades(subject, grades, obj.optString("journalId").trim())
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun findForSubject(context: Context, subject: String): SubjectGrades? {
        val wanted = normalize(subject)
        if (wanted.isBlank()) return null
        val all = loadAll(context)
        val exact = all.filter { normalize(it.subject) == wanted }
        val matches = if (exact.isNotEmpty()) exact else all.filter {
            val have = normalize(it.subject)
            have.isNotBlank() && (have.contains(wanted) || wanted.contains(have))
        }
        if (matches.isEmpty()) return null
        return SubjectGrades(
            subject = matches.first().subject,
            grades = matches.flatMap { it.grades },
            journalId = matches.map { it.journalId }.filter { it.isNotBlank() }.joinToString(",")
        )
    }

    fun detailsText(context: Context, subject: String): String {
        val record = findForSubject(context, subject)
            ?: return "Оценки: ещё не сохранены\nОткрой приложение и нажми «Обновить оценки из SmartNation»."
        if (record.numericGrades.isEmpty()) {
            return "Оценки пока не выставлены\nСреднее арифметическое: —"
        }
        val averageText = String.format(Locale("ru", "RU"), "%.2f", record.average)
        return "Оценки: ${record.grades.joinToString(", ")}\nСреднее арифметическое: $averageText"
    }

    private fun normalize(value: String): String =
        value.lowercase(Locale.ROOT).replace(Regex("[^\\p{L}\\p{N}]"), "")
}
'''
(root / "SmartSchedule/app/src/main/java/kz/asckwab/smartschedule/GradeModels.kt").write_text(
    grade_models, encoding="utf-8"
)

layout_path = root / "SmartSchedule/app/src/main/res/layout/widget_schedule.xml"
if not layout_path.exists():
    raise SystemExit("widget_schedule.xml not found")
layout = layout_path.read_text(encoding="utf-8")
if "widget_lesson_detail" not in layout:
    detail = '''    <TextView
        android:id="@+id/widget_lesson_detail"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:layout_marginTop="4dp"
        android:background="#263550"
        android:padding="6dp"
        android:textColor="#FFFFFF"
        android:textSize="10sp"
        android:maxLines="7"
        android:visibility="gone" />

'''
    marker = '              <TextView\n                  android:id="@+id/widget_empty"'
    if marker in layout:
        layout = layout.replace(marker, detail + marker, 1)
    else:
        marker = '    <TextView\n        android:id="@+id/widget_empty"'
        if marker not in layout:
            raise SystemExit("Could not find empty-view location in widget_schedule.xml")
        layout = layout.replace(marker, detail + marker, 1)
    layout_path.write_text(layout, encoding="utf-8")

row_path = root / "SmartSchedule/app/src/main/res/layout/widget_lesson_row.xml"
if not row_path.exists():
    raise SystemExit("widget_lesson_row.xml not found")
row = row_path.read_text(encoding="utf-8")
if "widget_lesson_row_root" not in row:
    row = row.replace(
        'android:layout_width="match_parent"',
        'android:id="@+id/widget_lesson_row_root"\n    android:layout_width="match_parent"',
        1
    )
    row = row.replace(
        'android:orientation="vertical"',
        'android:orientation="vertical"\n    android:clickable="true"\n    android:focusable="true"',
        1
    )
    row_path.write_text(row, encoding="utf-8")

provider_path = root / "SmartSchedule/app/src/main/java/kz/asckwab/smartschedule/ScheduleWidgetProvider.kt"
provider = provider_path.read_text(encoding="utf-8")
if "ACTION_TOGGLE_LESSON" not in provider:
    receive = '''    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == ACTION_TOGGLE_LESSON) {
            val key = intent.getStringExtra(EXTRA_LESSON_KEY).orEmpty()
            if (key.isNotBlank()) {
                val prefs = context.getSharedPreferences(WIDGET_PREFS, Context.MODE_PRIVATE)
                val current = prefs.getString(KEY_EXPANDED_LESSON, "")
                prefs.edit().putString(KEY_EXPANDED_LESSON, if (current == key) "" else key).apply()
                updateAll(context)
            }
            return
        }
        super.onReceive(context, intent)
    }

'''
    marker = '    override fun onUpdate(context: Context, manager: AppWidgetManager, appWidgetIds: IntArray) {'
    if marker not in provider:
        raise SystemExit("Could not find onUpdate in ScheduleWidgetProvider.kt")
    provider = provider.replace(marker, receive + marker, 1)

    marker = '    companion object {\n'
    constants = '''    companion object {
        private const val ACTION_TOGGLE_LESSON = "kz.asckwab.smartschedule.TOGGLE_WIDGET_LESSON"
        const val EXTRA_LESSON_KEY = "widget_lesson_key"
        private const val WIDGET_PREFS = "smart_schedule_widget_details"
        private const val KEY_EXPANDED_LESSON = "expanded_lesson"
'''
    if marker not in provider:
        raise SystemExit("Could not find companion object in ScheduleWidgetProvider.kt")
    provider = provider.replace(marker, constants, 1)

    adapter_match = re.search(r'(?m)^([ \t]*)views\.setRemoteAdapter\(R\.id\.widget_lesson_list, serviceIntent\)\s*$', provider)
    if not adapter_match:
        raise SystemExit("Could not find setRemoteAdapter in widget provider")
    indent = adapter_match.group(1)
    template_body = '''val clickTemplateIntent = Intent(context, ScheduleWidgetProvider::class.java).apply {
    action = ACTION_TOGGLE_LESSON
}
val clickTemplate = PendingIntent.getBroadcast(
    context,
    3100 + id,
    clickTemplateIntent,
    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
)
views.setPendingIntentTemplate(R.id.widget_lesson_list, clickTemplate)'''
    template = "\n" + "\n".join(indent + line if line else "" for line in template_body.splitlines()) + "\n"
    provider = provider[:adapter_match.end()] + template + provider[adapter_match.end():]

    update_match = re.search(r'(?m)^([ \t]*)manager\.updateAppWidget\(id, views\)\s*$', provider)
    if not update_match:
        raise SystemExit("Could not find manager.updateAppWidget in widget provider")
    indent = update_match.group(1)
    detail_body = r'''val expandedKey = context.getSharedPreferences(WIDGET_PREFS, Context.MODE_PRIVATE)
    .getString(KEY_EXPANDED_LESSON, "")
val expandedLesson = selected?.let { day ->
    day.lessons.firstOrNull { lesson ->
        "${day.date}|${lesson.start}|${lesson.subject}" == expandedKey
    }
}
if (expandedLesson != null) {
    val teacher = expandedLesson.teacher.takeIf { it.isNotBlank() } ?: "не указан в расписании"
    val gradeDetails = GradeStorage.detailsText(context, expandedLesson.subject)
    views.setTextViewText(
        R.id.widget_lesson_detail,
        "${expandedLesson.subject}\nПреподаватель: $teacher\n$gradeDetails"
    )
    views.setViewVisibility(R.id.widget_lesson_detail, android.view.View.VISIBLE)
} else {
    views.setViewVisibility(R.id.widget_lesson_detail, android.view.View.GONE)
}'''
    detail_logic = "\n".join(indent + line for line in detail_body.splitlines()) + "\n"
    provider = provider[:update_match.start()] + detail_logic + provider[update_match.start():]
    provider_path.write_text(provider, encoding="utf-8")

service_path = root / "SmartSchedule/app/src/main/java/kz/asckwab/smartschedule/ScheduleWidgetService.kt"
service = service_path.read_text(encoding="utf-8")
if "widget_lesson_key" not in service:
    match = re.search(r'(?m)^([ \\t]*)private var lessons: List<Lesson> = emptyList\(\)\s*$', service)
    if not match:
        raise SystemExit("Could not find lesson list in ScheduleWidgetService.kt")
    indent = match.group(1)
    service = service[:match.end()] + "\n" + indent + 'private var selectedDate: String = ""' + service[match.end():]

    match = re.search(r'(?m)^([ \\t]*)lessons = selected\?\.lessons\.orEmpty\(\)\s*$', service)
    if not match:
        raise SystemExit("Could not find lessons assignment in ScheduleWidgetService.kt")
    indent = match.group(1)
    service = service[:match.start()] + indent + 'selectedDate = selected?.date.orEmpty()' + "\n" + service[match.start():]

    match = re.search(r'(?m)^([ \t]*)row\.setTextViewText\(R\.id\.widget_lesson_subject, room \+ lesson\.subject\)\s*$', service)
    if not match:
        raise SystemExit("Could not find lesson row subject label in ScheduleWidgetService.kt")
    indent = match.group(1)
    fill_body = r'''row.setOnClickFillInIntent(
    R.id.widget_lesson_row_root,
    Intent().putExtra(
        ScheduleWidgetProvider.EXTRA_LESSON_KEY,
        "$selectedDate|${lesson.start}|${lesson.subject}"
    )
)'''
    fillin = "\n" + "\n".join(indent + line for line in fill_body.splitlines()) + "\n"
    service = service[:match.end()] + fillin + service[match.end():]
    service_path.write_text(service, encoding="utf-8")

main_path = root / "SmartSchedule/app/src/main/java/kz/asckwab/smartschedule/MainActivity.kt"
main = main_path.read_text(encoding="utf-8")
if "val updateGradesButton = Button(this)" not in main:
    grades_button = '''                  val updateGradesButton = Button(this).apply {
                      text = "Обновить оценки из SmartNation"
                      isAllCaps = false
                      setTextColor(Color.rgb(52, 84, 209))
                      background = rounded(Color.WHITE, 14)
                      setOnClickListener {
                          startActivity(
                              Intent(this@MainActivity, ScheduleWebActivity::class.java)
                                  .putExtra(ScheduleWebActivity.EXTRA_GRADES_MODE, true)
                          )
                      }
                  }
                  content.addView(
                      updateGradesButton,
                      LinearLayout.LayoutParams(-1, dp(48)).apply { topMargin = dp(8) }
                  )
'''
    marker = '                  content.post {\n                      val preferences = getSharedPreferences("smart_schedule_legal_notice"'
    if marker not in main:
        raise SystemExit("Could not find insertion point after legal notice button")
    main = main.replace(marker, grades_button + marker, 1)
    main_path.write_text(main, encoding="utf-8")

web_path = root / "SmartSchedule/app/src/main/java/kz/asckwab/smartschedule/ScheduleWebActivity.kt"
web = web_path.read_text(encoding="utf-8")
if "EXTRA_GRADES_MODE" not in web:
    web = web.replace(
        '    private var syncSucceeded = false\n',
        '    private var syncSucceeded = false\n    private val gradesMode: Boolean get() = intent.getBooleanExtra(EXTRA_GRADES_MODE, false)\n',
        1
    )
    web = web.replace(
        '                status.text = "Если ты уже вошёл, открой меню → «Процесс обучения» → «Расписание». Когда таблица появится, нажми «Проверить и сохранить»."',
        '                status.text = if (gradesMode) "Открой раздел «Журнал» или выбери предмет, чтобы отобразились оценки, затем нажми «Проверить и сохранить оценки»." else "Если ты уже вошёл, открой меню → «Процесс обучения» → «Расписание». Когда таблица появится, нажми «Проверить и сохранить»."',
        1
    )
    web = web.replace(
        '                status.text = "Страница загружается… После входа открой расписание."',
        '                status.text = if (gradesMode) "Открываю раздел оценок SmartNation…" else "Страница загружается… После входа открой расписание."',
        1
    )
    web = web.replace(
        '            text = "Проверить и сохранить расписание"',
        '            text = if (gradesMode) "Проверить и сохранить оценки" else "Проверить и сохранить расписание"',
        1
    )
    web = web.replace(
        '                status.text = "Проверяю, появилась ли таблица расписания…"',
        '                status.text = if (gradesMode) "Проверяю, появились ли оценки…" else "Проверяю, появилась ли таблица расписания…"',
        1
    )
    web = re.sub(r'(?<!fun )inspectPage\(\)', 'inspectCurrentPage()', web)
    web = web.replace(
        '        webView.loadUrl(SCHEDULE_URL)',
        '        webView.loadUrl(if (gradesMode) JOURNALS_URL else SCHEDULE_URL)',
        1
    )
    switch_button = '''        val gradesShortcut = Button(this).apply {
            text = "Журнал оценок"
            isAllCaps = false
            textSize = 12f
            setOnClickListener {
                syncSucceeded = false
                checks = 0
                handler.removeCallbacks(retryRunnable)
                webView.loadUrl(JOURNALS_URL)
            }
        }
        top.addView(gradesShortcut, LinearLayout.LayoutParams(-1, dp(40)))
'''
    if 'val gradesShortcut = Button(this)' not in web:
        marker = '        top.addView(action, LinearLayout.LayoutParams(-1, dp(46)))\n'
        if marker not in web:
            raise SystemExit("Could not find main WebView action button to add grades shortcut")
        web = web.replace(marker, marker + switch_button, 1)

    dispatch_method = '''    private fun inspectCurrentPage() {
        if (gradesMode) inspectGradesPage() else inspectPage()
    }

    private fun inspectGradesPage() {
        if (!::webView.isInitialized || syncSucceeded) return
        val token = currentPageToken
        webView.evaluateJavascript(EXTRACT_GRADES_JS) { value ->
            if (syncSucceeded || isFinishing || token != currentPageToken || value == null || value == "null") return@evaluateJavascript
            val decoded = try {
                JSONArray("[$value]").getString(0)
            } catch (_: Exception) {
                value
            }
            val result = try { JSONObject(decoded) } catch (_: Exception) { null }
            if (result?.optString("stage") == "journal_list") {
                status.text = "Открылся список журналов. Нажми значок глаза справа от нужного предмета — после открытия журнала приложение прочитает оценки."
                progress.visibility = ProgressBar.GONE
                return@evaluateJavascript
            }
            if (result?.optBoolean("ok", false) == true &&
                result.optString("stage") == "journal_detail") {
                val entry = result.optJSONArray("subjects")?.optJSONObject(0)
                val subject = entry?.optString("subject").orEmpty()
                val count = entry?.optJSONArray("grades")?.length() ?: 0
                if (count == 0) {
                    syncSucceeded = true
                    handler.removeCallbacks(retryRunnable)
                    progress.visibility = ProgressBar.GONE
                    status.text = "Предмет «$subject» найден, но на этой странице пока нет числовых оценок. Уже сохранённые оценки не удалены."
                    return@evaluateJavascript
                }

                val accepted = GradeStorage.saveFromWebJson(this, decoded)
                if (accepted) {
                    syncSucceeded = true
                    handler.removeCallbacks(retryRunnable)
                    progress.visibility = ProgressBar.GONE
                    status.text = "Оценки по «$subject» сохранены ($count). Вернись в приложение и нажми на пару в виджете."
                    Toast.makeText(this, "Оценки сохранены", Toast.LENGTH_LONG).show()
                } else {
                    status.text = "Журнал «${entrySubject(decoded)}» найден, но не удалось сохранить оценки. Обнови страницу и попробуй ещё раз."
                }
            } else {
                status.text = "Перейди в раздел «Журнал», нажми значок глаза напротив нужного предмета и дождись загрузки страницы с оценками."
                progress.visibility = ProgressBar.GONE
            }
        }
    }

    private fun entrySubject(raw: String): String = try {
        JSONObject(raw).optJSONArray("subjects")?.optJSONObject(0)?.optString("subject").orEmpty()
    } catch (_: Exception) { "" }

'''
    marker = '    private fun inspectPage() {\n'
    if marker not in web:
        raise SystemExit("Could not find inspectPage() in ScheduleWebActivity.kt")
    web = web.replace(marker, dispatch_method + marker, 1)

    web = web.replace(
        '                    status.text = "Сайт SmartNation открыт. Для обновления выбери расписание и нажми «Проверить и сохранить расписание»."',
        '                    status.text = if (gradesMode) "Раздел SmartNation открыт. Перейди к оценкам по предметам и нажми «Проверить и сохранить оценки»." else "Сайт SmartNation открыт. Для обновления выбери расписание и нажми «Проверить и сохранить расписание»."',
        1
    )
    marker = '        private const val SCHEDULE_URL = "https://college.smartnation.kz/ru/atr/control/training-schedule/33125"'
    constants = '''        const val EXTRA_GRADES_MODE = "smart_schedule_grades_mode"
        private const val JOURNALS_URL = "https://college.smartnation.kz/ru/atr/control/journals"
        private const val GRADEBOOK_URL = "https://college.smartnation.kz/ru/atr/contingent-performance-book"
'''
    if marker not in web:
        raise SystemExit("Could not find SmartNation schedule URL constant")
    web = web.replace(marker, constants + marker, 1)

    extract_js = r'''        private val EXTRACT_GRADES_JS = """
            (function() {
              const clean = value => (value || '').replace(/\s+/g, ' ').trim();
              if (location.hostname !== 'college.smartnation.kz') {
                return JSON.stringify({ok:false, stage:'wrong_host'});
              }

              // On the journals list, every eye icon opens a separate journal page.
              const journalList = document.querySelector('.s-table-cabinet');
              const eyeLinks = Array.from(document.querySelectorAll(
                '.s-table-cabinet a.s-btn-table[title="Посмотреть"], .s-table-cabinet a .s-ico--thm-eye'
              ));
              if (journalList && eyeLinks.length > 0) {
                return JSON.stringify({ok:false, stage:'journal_list'});
              }

              // A journal detail page keeps the subject in a metadata table and marks
              // in a separate horizontally-scrollable table.
              const metadataRows = Array.from(document.querySelectorAll('tr.sc-journal__control--table-row'));
              const subjectRow = metadataRows.find(row => {
                const label = clean(row.querySelector('.sc-journal__control--table-label')?.innerText);
                return /^предмет\s*:?$/i.test(label);
              });
              const subject = clean(subjectRow?.querySelector('.sc-journal__control--table-value')?.innerText);
              const gradeTable = document.querySelector('table.sc-journal__table--scroll-part');
              if (!subject || !gradeTable) {
                return JSON.stringify({ok:false, stage:'not_journal_detail'});
              }

              const grades = [];
              Array.from(gradeTable.querySelectorAll('tr.sc-journal__table--row')).forEach(row => {
                Array.from(row.querySelectorAll('td.sc-journal__table--cell-day')).forEach(cell => {
                  const valueNode = cell.querySelector('.sc-journal__table--cell-value');
                  const raw = clean(valueNode ? valueNode.innerText : cell.innerText).replace(/,/g, '.');
                  // Accept only a whole numeric cell value so dates and unrelated numbers are ignored.
                  if (!/^(?:100(?:\.0{1,2})?|[0-9]{1,2}(?:\.[0-9]{1,2})?)$/.test(raw)) return;
                  const mark = Number(raw);
                  if (Number.isFinite(mark) && mark >= 0 && mark <= 100) grades.push(raw);
                });
              });

              const match = location.pathname.match(/\/journals\/(\d+)(?:\/|$)/);
              const journalId = match ? match[1] : '';
              return JSON.stringify({
                ok:true,
                stage:'journal_detail',
                subjects:[{subject:subject, grades:grades, journalId:journalId}]
              });
            })();
        """.trimIndent()
'''
    if 'private val EXTRACT_GRADES_JS' not in web:
        end_marker = '        """.trimIndent()\n    }\n}'
        idx = web.rfind(end_marker)
        if idx < 0:
            raise SystemExit("Could not find end of EXTRACT_SCHEDULE_JS to add grade extractor")
        web = web[:idx] + '        """.trimIndent()\n\n' + extract_js.strip("\n") + '    }\n}' + web[idx + len(end_marker):]

    web_path.write_text(web, encoding="utf-8")

notice_script = Path(".github/scripts/add_legal_notice.py")
if notice_script.exists():
    content = notice_script.read_text(encoding="utf-8")
    content = content.replace(
        "позволяет сохранять данные расписания на устройстве.",
        "позволяет сохранять данные расписания и распознанные оценки на устройстве."
    )
    notice_script.write_text(content, encoding="utf-8")

print("Lesson tap details, local grade cache, and SmartNation grade sync UI added.")
