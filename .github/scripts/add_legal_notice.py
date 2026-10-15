from pathlib import Path
import re

root = Path("project")
files = list(root.rglob("MainActivity.kt"))
if not files:
    raise SystemExit("MainActivity.kt not found")
path = files[0]
text = path.read_text(encoding="utf-8")

function = r'''    private fun showLegalNotice(markAsSeen: Boolean = false) {
        val preferences = getSharedPreferences("smart_schedule_legal_notice", android.content.Context.MODE_PRIVATE)
        val notice = """
            УВЕДОМЛЕНИЕ О НАЗНАЧЕНИИ, ИСПОЛЬЗОВАНИИ И ОГРАНИЧЕНИЯХ ПРИЛОЖЕНИЯ SMARTSCHEDULE

            1. Назначение приложения

            SmartSchedule первоначально разработано автором для личного пользования в учебных целях. Приложение распространяется бесплатно и не предназначено для получения коммерческой выгоды. Оно не является официальным продуктом SmartNation, колледжа или какого-либо учебного заведения и не связано с ними официальными отношениями.

            Приложение предназначено для упрощения просмотра и сохранения учебного расписания и предоставляется в качестве вспомогательного инструмента.

            2. Работа приложения и актуальность расписания

            SmartSchedule помогает получать, отображать и сохранять сведения из учебного расписания. В процессе работы возможны технические ошибки, неполное отображение информации, использование устаревших данных или сбои при обновлении.

            Расписание может изменяться независимо от приложения. Поэтому перед занятиями и при возникновении сомнений рекомендуется сверять информацию с официальными источниками учебного заведения.

            3. Персональные данные и конфиденциальность

            SmartSchedule открывает SmartNation во встроенном браузере и позволяет сохранять данные расписания и распознанные оценки на устройстве. Для авторизации используется страница соответствующего стороннего сервиса.

            При использовании приложения могут обрабатываться технические данные, файлы cookie и сведения о сеансе, необходимые для работы встроенного браузера и взаимодействия со сторонними сервисами. Обработка данных на стороне SmartNation регулируется правилами и политикой конфиденциальности соответствующего сервиса.

            Не вводите учётные данные на страницах, подлинность которых вызывает сомнения, и не предоставляйте сведения, не необходимые для использования приложения. Рекомендуется соблюдать меры безопасности при работе с устройством и учитывать условия использования сторонних сервисов.

            4. Сторонние сервисы и ограничения

            Работа отдельных функций приложения зависит от доступности и изменений сторонних сайтов и сервисов. Они могут изменять интерфейс, ограничивать доступ, временно прекращать работу или становиться недоступными по причинам, не зависящим от разработчика.

            Разработчик не гарантирует бесперебойную работу сторонних сервисов, постоянную доступность всех функций приложения или абсолютную точность получаемых данных.

            5. Установка и использование

            Пользователь самостоятельно принимает решение об установке и использовании приложения, учитывая особенности своего устройства, настройки безопасности и возможные технические ограничения.

            Рекомендуется устанавливать APK-файлы только из источников, которым пользователь доверяет, и не использовать сборки неизвестного происхождения или версии, изменённые неустановленными лицами.

            6. Ограничения гарантий и ответственность

            Приложение предоставляется бесплатно и по принципу «как есть», без гарантии отсутствия ошибок, непрерывной работы или совместимости со всеми устройствами. Разработчик стремится исправлять обнаруженные ошибки, однако не гарантирует, что все проблемы будут выявлены или устранены немедленно.

            Настоящее уведомление информирует о назначении приложения и ограничениях его работы. Оно не отменяет права пользователей и обязанности разработчика, предусмотренные применимым законодательством.

            Используя приложение, пользователь подтверждает, что ознакомился с настоящим уведомлением и понимает назначение и ограничения SmartSchedule.
        """.trimIndent()

        val body = android.widget.TextView(this).apply {
            text = notice
            textSize = 14f
            setTextColor(android.graphics.Color.rgb(35, 39, 47))
            setPadding(24, 18, 24, 18)
            setTextIsSelectable(true)
        }
        val scroll = android.widget.ScrollView(this).apply {
            setBackgroundColor(android.graphics.Color.WHITE)
            isFillViewport = true
            addView(body, android.widget.FrameLayout.LayoutParams(-1, -2))
        }

        val dialog = android.app.AlertDialog.Builder(this)
            .setTitle("Уведомление о SmartSchedule")
            .setView(scroll)
            .setPositiveButton("Понятно", null)
            .create()

        dialog.setOnShowListener {
            dialog.window?.setLayout(
                (resources.displayMetrics.widthPixels * 0.92f).toInt(),
                (resources.displayMetrics.heightPixels * 0.78f).toInt()
            )
            dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                if (markAsSeen) {
                    preferences.edit().putBoolean("seen", true).apply()
                }
                dialog.dismiss()
            }
        }
        dialog.setOnDismissListener {
            if (markAsSeen) {
                preferences.edit().putBoolean("seen", true).apply()
            }
        }
        dialog.show()
    }

'''
if "private fun showLegalNotice(" not in text:
    marker = "    private fun createView() {"
    if marker not in text:
        raise SystemExit("Could not find createView() in MainActivity.kt")
    text = text.replace(marker, function + marker, 1)

button_code = r''' 
                  val legalNoticeButton = Button(this).apply {
                      text = "Уведомление и правила использования"
                      isAllCaps = false
                      setTextColor(Color.rgb(52, 84, 209))
                      background = rounded(Color.WHITE, 14)
                      setOnClickListener { showLegalNotice(markAsSeen = false) }
                  }
                  content.addView(
                      legalNoticeButton,
                      LinearLayout.LayoutParams(-1, dp(48)).apply { topMargin = dp(8) }
                  )
                  content.post {
                      val preferences = getSharedPreferences("smart_schedule_legal_notice", android.content.Context.MODE_PRIVATE)
                      if (!preferences.getBoolean("seen", false)) {
                          showLegalNotice(markAsSeen = true)
                      }
                  }
'''
pattern = r'(content\.addView\(\s*addWidgetButton,\s*LinearLayout\.LayoutParams\(-1,\s*dp\(48\)\)\.apply\s*\{\s*topMargin\s*=\s*dp\(10\)\s*\}\s*\))'
if "val legalNoticeButton = Button(this)" not in text:
    text, count = re.subn(pattern, lambda m: m.group(1) + "\n\n" + button_code, text, count=1)
    if count != 1:
        raise SystemExit("Could not insert legal-notice button after the widget button")
path.write_text(text, encoding="utf-8")
print("One-time legal notice and persistent review button added.")
