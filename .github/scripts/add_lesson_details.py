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
    val grades: List<String>
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
            val subjects = mutableListOf<SubjectGrades>()
            for (i in 0 until input.length()) {
                val obj = input.optJSONObject(i) ?: continue
                val subject = obj.optString("subject").trim()
                val marks = obj.optJSONArray("grades") ?: JSONArray()
                val grades = mutableListOf<String>()
                for (j in 0 until marks.length()) {
                    val value = marks.optString(j).trim().replace(',', '.')
                    val n = value.toDoubleOrNull()
                    if (value.isNotBlank() && n != null && n.isFinite() && n in 0.0..100.0) {
                        grades += value
                    }
                }
                if (subject.isNotBlank() && grades.isNotEmpty()) {
                    subjects += SubjectGrades(subject, grades)
                }
            }
            if (subjects.isEmpty()) return false
            val jsonSubjects = JSONArray()
            subjects.forEach { record ->
                jsonSubjects.put(JSONObject()
                    .put("subject", record.subject)
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
                val values = obj.optJSONArray("grades") ?: JSONArray()
                val grades = (0 until values.length()).map { values.optString(it).trim() }
                    .filter { it.replace(',', '.').toDoubleOrNull()?.let { n -> n.isFinite() && n in 0.0..100.0 } == true }
                if (subject.isBlank() || grades.isEmpty()) null else SubjectGrades(subject, grades)
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun findForSubject(context: Context, subject: String): SubjectGrades? {
        val wanted = normalize(subject)
        if (wanted.isBlank()) return null
        val all = loadAll(context)
        all.firstOrNull { normalize(it.subject) == wanted }?.let { return it }
        val candidates = all.filter {
            val have = normalize(it.subject)
            have.isNotBlank() && (have.contains(wanted) || wanted.contains(have))
        }
        return candidates.maxByOrNull { normalize(it.subject).length }
    }

    fun detailsText(context: Context, subject: String): String {
        val record = findForSubject(context, subject)
            ?: return "Оценки: пока не сохранены\nОткрой приложение и нажми «Обновить оценки»."
        val average = record.average
        val averageText = average?.let { String.format(Locale("ru", "RU"), "%.2f", it) }
            ?: "нет числовых оценок"
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

    adapter = '                      views.setRemoteAdapter(R.id.widget_lesson_list, serviceIntent)\n'
    if adapter not in provider:
        adapter = '                  views.setRemoteAdapter(R.id.widget_lesson_list, serviceIntent)\n'
    if adapter not in provider:
        raise SystemExit("Could not find setRemoteAdapter in widget provider")
    template = '''                      val clickTemplateIntent = Intent(context, ScheduleWidgetProvider::class.java).apply {
                          action = ACTION_TOGGLE_LESSON
                      }
                      val clickTemplate = PendingIntent.getBroadcast(
                          context,
                          3100 + id,
                          clickTemplateIntent,
                          PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
                      )
                      views.setPendingIntentTemplate(R.id.widget_lesson_list, clickTemplate)
'''
    provider = provider.replace(adapter, adapter + template, 1)

    needle = '                      manager.updateAppWidget(id, views)\n'
    detail_logic = '''                      val expandedKey = context.getSharedPreferences(WIDGET_PREFS, Context.MODE_PRIVATE)
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
                              "${expandedLesson.subject}\\nПреподаватель: $teacher\\n$gradeDetails"
                          )
                          views.setViewVisibility(R.id.widget_lesson_detail, android.view.View.VISIBLE)
                      } else {
                          views.setViewVisibility(R.id.widget_lesson_detail, android.view.View.GONE)
                      }
'''
    if needle not in provider:
        raise SystemExit("Could not find manager.updateAppWidget in widget provider")
    provider = provider.replace(needle, detail_logic + needle, 1)
    provider_path.write_text(provider, encoding="utf-8")

service_path = root / "SmartSchedule/app/src/main/java/kz/asckwab/smartschedule/ScheduleWidgetService.kt"
service = service_path.read_text(encoding="utf-8")
if "widget_lesson_key" not in service:
    service = service.replace(
        '              private var lessons: List<Lesson> = emptyList()\n',
        '              private var lessons: List<Lesson> = emptyList()\n              private var selectedDate: String = ""\n',
        1
    )
    service = service.replace(
        '                  lessons = selected?.lessons.orEmpty()\n',
        '                  selectedDate = selected?.date.orEmpty()\n                  lessons = selected?.lessons.orEmpty()\n',
        1
    )
    marker = '                  row.setTextViewText(R.id.widget_lesson_subject, room + lesson.subject)\n'
    fillin = '''                  row.setTextViewText(R.id.widget_lesson_subject, room + lesson.subject)
                  row.setOnClickFillInIntent(
                      R.id.widget_lesson_row_root,
                      Intent().putExtra(
                          ScheduleWidgetProvider.EXTRA_LESSON_KEY,
                          "$selectedDate|${lesson.start}|${lesson.subject}"
                      )
                  )
'''
    if marker not in service:
        raise SystemExit("Could not find lesson row subject label in ScheduleWidgetService.kt")
    service = service.replace(marker, fillin, 1)
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
            if (result?.optBoolean("ok", false) == true) {
                val accepted = GradeStorage.saveFromWebJson(this, decoded)
                if (accepted) {
                    syncSucceeded = true
                    handler.removeCallbacks(retryRunnable)
                    progress.visibility = ProgressBar.GONE
                    val count = result.optJSONArray("subjects")?.length() ?: 0
                    status.text = "Оценки сохранены для $count предметов. Можешь вернуться в приложение."
                    Toast.makeText(this, "Оценки сохранены", Toast.LENGTH_SHORT).show()
                } else {
                    status.text = "Оценки распознаны не полностью. Открой нужный журнал или книжку успеваемости и попробуй ещё раз."
                }
            } else {
                status.text = "Не нашёл таблицу с оценками. Открой «Журнал», перейди к оценкам по предметам и нажми эту кнопку ещё раз."
            }
        }
    }

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
              if (location.hostname !== 'college.smartnation.kz') return JSON.stringify({ok:false, reason:'not-smartnation-host'});
              const clean = v => (v || '').replace(/\s+/g, ' ').trim();
              const numericMarks = value => {
                const text = clean(value).replace(/,/g, '.');
                const matches = text.match(/(?<!\d)(?:100|[1-9]?\d(?:\.\d{1,2})?)(?!\d)/g) || [];
                return matches.filter(v => {
                  const n = Number(v);
                  return Number.isFinite(n) && n >= 0 && n <= 100;
                });
              };
              const subjects = [];
              const seen = new Set();
              const tables = Array.from(document.querySelectorAll('table'));
              tables.forEach(table => {
                const rows = Array.from(table.rows || []);
                if (rows.length < 2) return;
                const headerIndex = rows.findIndex(row =>
                  Array.from(row.cells || []).some(cell =>
                    /предмет|дисциплин|модул|наименован|subject|course/i.test(clean(cell.innerText || cell.textContent))
                  )
                );
                if (headerIndex < 0) return;
                const headers = Array.from(rows[headerIndex].cells || []).map(cell => clean(cell.innerText || cell.textContent));
                const subjectIndex = headers.findIndex(h => /предмет|дисциплин|модул|наименован|subject|course/i.test(h));
                const gradeIndices = headers.map((h, index) =>
                  /оценк|балл|результат|grade|mark|score|аттест|текущ/i.test(h) ? index : -1
                ).filter(index => index >= 0 && index !== subjectIndex);
                if (subjectIndex < 0 || gradeIndices.length === 0) return;
                rows.slice(headerIndex + 1).forEach(row => {
                  const cells = Array.from(row.cells || []);
                  const subject = clean(cells[subjectIndex]?.innerText || cells[subjectIndex]?.textContent);
                  if (!subject || subject.length < 2 || /^(итого|средн|всего|предмет|дисциплина)$/i.test(subject)) return;
                  const grades = [];
                  gradeIndices.forEach(index => {
                    const cell = cells[index];
                    if (!cell) return;
                    numericMarks(cell.innerText || cell.textContent).forEach(mark => grades.push(mark));
                  });
                  const uniqueGrades = grades.filter((v, i) => grades.indexOf(v) === i);
                  if (!uniqueGrades.length) return;
                  const key = subject.toLocaleLowerCase();
                  if (!seen.has(key)) {
                    seen.add(key);
                    subjects.push({subject:subject, grades:uniqueGrades});
                  }
                });
              });
              return JSON.stringify({ok:subjects.length > 0, subjects:subjects, reason:subjects.length ? '' : 'grade-table-not-found'});
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
