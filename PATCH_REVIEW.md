# Аудит и исправление патчей Supermium 150

База: **Chromium 150.0.7871.287**. PDFium — ревизия `6fb120b2b21f`, `search_engines_data` — ревизия
`1aab872af8d44dcf59362d7ba8255922f74fafde` (обе из `DEPS` этой версии).

Ошибки из исходного аудита (он ниже, в разделе «Исходный аудит») исправлены прямо в патч-файлах,
кроме перечисленных в разделе «Сознательно не менялось». Исправлены и ошибки, найденные при
повторных проверках. Патчи перегенерированы так, что неизменённые hunk'и остались прежними, кроме
строк `index` и номеров строк в заголовках `@@`. У `xp_tts_fix` и `time_ticks_patch.diff`, которые
были сделаны на другой версии файлов, заголовки теперь соответствуют 150. Изменения по каждому
патчу — в разделе «Что исправлено».

## Как применять

Порядок важен: несколько файлов правятся цепочкой патчей. `layout_constants.cc`: `ui_part_2` →
`general_features` → `150_about_flags…`. `hwnd_message_handler.cc`: `ui_part_1` →
`touch_device_support_win7`. `url_fixer.cc` и `download_target_determiner.cc`: `general_features` →
`ungoogled_supermium_and_mv2`.

```bash
set -e
SUPERMIUM=/абсолютный/путь/к/этому/репозиторию
cd src   # корень дерева Chromium 150.0.7871.287
for p in \
    supermium_150_core_encrypt_mojo.patch \
    supermium_150_core_mem.patch \
    supermium_150_core_sandbox.patch \
    ui_part_1.patch \
    ui_part_2.patch \
    general_features.patch \
    150_about_flags_and_finishing_touches.patch \
    client_hints.patch \
    ungoogled_supermium_and_mv2.patch \
    misc_changes_20261002.patch \
    time_ticks_patch.diff \
    waveinput_output_restore.patch \
    win7_notification_bug_and_improved_pwa_install_prompt_block.patch \
    xp_tts_fix.patch \
    ptr_device_fix.patch \
    quic_fix.patch \
    touch_device_support_win7.patch; do
  git apply --whitespace=nowarn "$SUPERMIUM/$p"
done
git -C third_party/pdfium apply "$SUPERMIUM/pdfium_fix.patch"
git -C third_party/search_engines_data/resources apply "$SUPERMIUM/search_engines_data.patch"
```

Путь в `$SUPERMIUM` должен быть абсолютным: последние две команды выполняются из других каталогов.
`pdfium_fix.patch` применяется в `third_party/pdfium`, а новый `search_engines_data.patch` — в
`third_party/search_engines_data/resources` (это отдельные git-репозитории из `DEPS`).

## Как проверено

* Все 17 основных патчей применяются **строгим `git apply`** (без fuzz) последовательно в указанном
  порядке на чистые исходники 150.0.7871.287. Результат совпадает байт в байт с деревом, в котором
  делались исправления. Пять исходных hunk'ов автора в `general_features` и
  `ungoogled_supermium_and_mv2` ложатся со смещением на 1–5 строк, на результат это не влияет.
* `pdfium_fix.patch` и `search_engines_data.patch` проходят `git apply --check` на своих ревизиях.
* В каждом hunk совпадают счётчики строк, лишних строк `" "` в конце файлов больше нет.
* Исправления прошли три раунда независимого ревью. В каждом раунде по каждой группе изменений
  работали отдельные проверяющие, а каждое замечание перепроверялось скептиками, которые пытались
  его опровергнуть. Проверялось, что использованные функции, заголовки и цели GN существуют в 150,
  что логика соответствует задуманному и что поведение без флагов Supermium не меняется. Все
  подтверждённые замечания внесены.
* **Сборка не выполнялась**: для этого нужно полное дерево Chromium и Windows-тулчейн. Перед
  релизом нужно собрать браузер и проверить его на целевых ОС. Особенно это касается изменений
  песочницы на Windows 7/8/8.1 (раздел про `supermium_150_core_sandbox`).

## Что исправлено

### Ошибки сборки

* **`150_about_flags_and_finishing_touches`: созданы отсутствовавшие
  `chrome/browser/supermium_flag_choices.h` и `chrome/browser/supermium_flag_entries.h`.**
  Записи перенесены из Supermium 144 и сверены с переключателями, которые реально проверяют патчи
  150. Подробности — в разделе «Флаги chrome://flags».
* **`search_engines_data.patch` (новый)**: добавляет движок `nosearch`, на который ссылается
  `ungoogled_supermium_and_mv2.patch` (`TemplateURLPrepopulateData::nosearch`). Запись взята из
  удалённого в `cde2ba0` патча без изменений (в том числе `"id": 1`: при `--ungoogled-supermium`
  она подменяет данные Google). Старые переименования `SEARCH_ENGINE_*` → `IDR_SEARCH_ENGINE_*`
  и понижение `kCurrentDataVersion` не перенесены: они относились к более старой версии данных и
  ломали бы сборку 150.
* **`supermium_150_core_encrypt_mojo`**: `::CryptUnrotectMemory` → `::CryptUnprotectMemory`.

### Серьёзные логические ошибки

* **`win7_notification_bug…` (`ui/base/win/lock_state.cc`)**: `>= WIN7` → `== WIN7`. Флаги
  блокировки перевёрнуты только на Windows 7 и Server 2008 R2. Win8+ больше не стартует в
  состоянии «экран заблокирован», уведомления не блокируются.
* **`general_features` (`extensions/browser/extension_util.cc`)**: возвращено отрицание
  `!ShouldDownloadAsRegularFile()`. Установка расширений из CWS и .crx снова работает по умолчанию.
* **`ui_part_2`, layout-константы и WebUI-тулбар**:
  * `kLast = kTabTitleYOffset` (снова последний элемент), массив значений размером `kLast + 1`,
    цикл в `SetLayoutConstants()` идёт до `kLast` включительно;
  * в `LayoutConstantToCssVarName()` (`webui_toolbar_layout_css_helper.cc`) вместо
    `default: break;` добавлены CSS-имена для всех 17 новых констант (`--tab-width`,
    `--tab-horizontal-padding`, …, `--tab-title-y-offset`). `NOTREACHED()` больше не срабатывает, `-Wswitch` снова ловит
    забытые константы;
  * в ключ `int_layout_constant_N{…}` из `scs` снова подставляется индекс `N`;
  * числа из `scs` разбираются через `base::StringToInt` (пустая строка или переполнение больше
    не приводят к `std::stoi` без исключений, то есть к аварийному завершению);
  * `GetLayoutConstant()` сама вызывает `SetLayoutConstants()` при первом обращении, поэтому ранние
    вызовы больше не получают нули.
* **`supermium_150_core_sandbox`, песочница на Windows 7/8/8.1**:
  * `broker_services.cc`: до Win10 целевой процесс, пока он приостановлен, помещается в job через
    `AssignProcessToJobObject()`. Теперь к нему применяются ограничения job, а `JobTracker`
    освобождается по `JOB_OBJECT_MSG_ACTIVE_PROCESS_ZERO`, как и задумано (раньше он утекал на
    каждый дочерний процесс);
  * до Windows 8 (Win7, Vista, XP) вложенные job не поддерживаются, поэтому процесс создаётся с
    `CREATE_BREAKAWAY_FROM_JOB`, если браузер сам запущен в job, который это разрешает. Старый
    Chromium ставил этот флаг безусловно, а при неудаче назначения job завершался ошибкой. Если
    назначить job всё же не удалось: на Win8+ это ошибка (`SBOX_ERROR_ASSIGN_PROCESS_TO_JOB_OBJECT`,
    как в Chromium 70–109), а до Win8 процесс продолжает работать без job, как в исходном патче.
    В этом случае `JobTracker` освобождается по завершении самого процесса: `TargetEventsThread`
    ждёт его handle через `RegisterWaitForSingleObject` и обрабатывает выход так же, как
    `JOB_OBJECT_MSG_ACTIVE_PROCESS_ZERO`. Пустой job такого процесса не привязывается к порту
    завершения, поэтому ранний выход процесса не может закрыть handle job'а, пока
    `FinishSpawnTargetImpl()` с ним ещё работает. Утечки нет, кроме маловероятного случая, когда
    сам `RegisterWaitForSingleObject` вернул ошибку;
  * `handle_closer_agent.cc`: до Win8.1 карта handle'ов, построенная перебором, теперь
    используется. Для каждого handle вызывается `MaybeCloseHandle()`. ALPC-порты пропускаются:
    отключение от CSRSS поддерживается только на Win10+. `\Device\KsecDD` в рендерерах
    закрывается только начиная с Win8.1 (`sandbox_win.cc`): раньше на Win7/8.0 он фактически не
    закрывался, его использует `RtlGenRandom()` из `cryptbase.dll`, и ни одна версия Chromium с
    поддержкой Win7 его не закрывала;
  * `interception.cc`: бесконечный `while (!ReadProcessMemory(...));` заменён на не более
    200 попыток с `Sleep(1)` и только при `ERROR_PARTIAL_COPY`;
  * `service_resolver_32.cc`: возвращено определение
    `ServiceResolverThunk::VerifyJumpTargetForTesting` (x86 `sbox_unittests` снова линкуется).
* **`ui_part_1` и `client_hints`, чтение `scs` и `uao`**: вместо `std::string(buf.data())` без
  завершающего нуля используется `base::ReadFileToString()`. Числа цветов из `scs`
  (`chrome_color_mixers.cc`) разбираются через `base::StringToInt`, пустые поля отбрасываются.
  Файл `uao` читается один раз и кешируется, кроме режима `--enable-advanced-customization` (тот
  же приём автор использует для layout-констант). `LOG(0)` → `LOG(WARNING)`.
* **`general_features`, `--compact-ui`**: обнуляется `kBookmarkBarButtonPadding`, а не высота
  панели закладок.

### Ошибки средней важности и мелкие

* **`--remove-tabsearch-button`** (`general_features`). В 150 кнопка Tab Search по умолчанию
  находится в `TabStripComboButton` (фича `kHorizontalTabStripComboButton` включена по умолчанию),
  поэтому:
  * `TabStripComboButton::IsTabSearchPinned()` с флагом возвращает `false`, и кнопка скрыта как в
    горизонтальной, так и в вертикальной полосе вкладок (новый раздел патча для
    `tab_strip_combo_button.cc`);
  * `UpdateTabSearchBubbleHost()` не привязывает к ней `TabSearchBubbleHost`;
  * `BrowserViewLayoutDelegateImpl::IsActiveTabAtLeadingWindowEdge()` считает, что кнопки нет (и при
    включённой, и при выключенной комбо-кнопке), поэтому верхний левый угол панели инструментов
    рисуется так же, как без кнопки;
  * в системном меню окна нет пункта «Открепить/закрепить поиск по вкладкам», который с флагом
    ничего не делал (`system_menu_model_builder.cc`);
  * если комбо-кнопка выключена, отдельная `TabSearchButton` не создаётся в
    `horizontal_tab_strip_region_view.cc`.

  Для `tab_strip_combo_button.cc`, `browser_view_layout_delegate_impl.cc`,
  `system_menu_model_builder.cc` и `horizontal_tab_strip_region_view.cc` в патч добавлены новые
  разделы.

  Кнопка Tab Search, которую пользователь сам закрепил на панели инструментов, остаётся.
* **`--popups-to-tabs` не работал** (`general_features`, найдено при повторной проверке).
  Disposition `NEW_POPUP` подменялся только в рендерере (`ToMojom`, `render_frame_impl.cc`), а
  рендерер этот переключатель не получает. Как в 144 и в ungoogled-chromium, проверка добавлена и
  в `FromMojom`, которая выполняется в процессе браузера. Известное ограничение (то же в 144 и
  ungoogled-chromium): всплывающее окно-«компаньон» Window Management API, которое сайт открывает
  после перехода в полноэкранный режим на другом мониторе, с этим флагом блокируется
  блокировщиком всплывающих окон.
* **`--disable-search-engine-collection` не работал** (`general_features`, найдено при повторной
  проверке). Его проверял только рендерер, которому переключатель не передаётся. Из 144 перенесена
  проверка в `TemplateURLService` (`ShouldAutocollect()`). В отличие от 144, она стоит в самом
  начале `CanAddAutogeneratedKeyword()`, поэтому собранные раньше движки тоже больше не
  перезаписываются. `TemplateURLFetcher::ScheduleDownload()` с этим флагом не скачивает
  OpenSearch-описание. Теперь блокируются и движки из OpenSearch-описаний, и ключевые слова из
  отправленных форм, а лишних сетевых запросов нет.
* **`render_frame_impl.cc`** (`general_features`): для Windows добавлена отдельная ветка
  `DUMP_WILL_BE_CHECK(!in_frame_tree_)`. Задуманное смягчение `CHECK` теперь действительно
  работает: на Windows создаётся дамп без падения рендерера.
* **`PaintVectorIcon`** (`ui_part_2`, `ui/gfx/paint_vector_icon.cc`):
  * пользовательские иконки читаются с диска один раз на каждое имя (кеш под `base::Lock`), кроме
    режима `--enable-advanced-customization`;
  * неизвестная команда или нехватка аргументов в файле иконки больше не вызывает `NOTREACHED()`
    или чтение за границей пути: такой файл игнорируется, и рисуется встроенная иконка;
  * подключение `chrome/common/chrome_paths.h` помечено `// nogncheck`, а в `ui/gfx/BUILD.gn`
    добавлены зависимости на сгенерированные заголовки, которые он подключает
    (`//build:branding_buildflags`, `//extensions/buildflags`,
    `//third_party/widevine/cdm:buildflags`). Иначе чистая параллельная сборка могла упасть с
    «file not found» в зависимости от порядка задач ninja. То же сделано для
    `components/embedder_support/BUILD.gn` (`client_hints`).
* **Legacy-диалог «Сохранить»** (`ui_part_2`, `execute_select_file_win.cc`):
  * `suggested_directory` живёт до вызова `GetSaveFileNameW` (висячего указателя больше нет);
  * в `wcslcpy` передаётся размер в символах;
  * удалены отладочные `LOG(ERROR)`;
  * в `ExecuteFolder_Legacy` ярлык разрешается только если путь действительно добавлен.
* **`ui/snapshot/snapshot_win.cc`** (`ui_part_2`): до Win8.1 копируется клиентская область
  (`ClientToScreen` вместо `GetWindowRect` + 8), DC экрана освобождается через `ReleaseDC` на всех
  путях.
* **`menu_config_win.cc`** (`ui_part_2`): `icons_in_label = true`, второй
  `separator_upper_height` исправлен на `separator_lower_height`.
* **`Tab::UpdateIconVisibility`** (`ui_part_2`): ширина кнопки закрытия снова вычитается только
  при `showing_close_button_`.
* **CPU Pressure** (`supermium_150_core_encrypt_mojo`, `cpu_probe_win.cc`): `PdhAddEnglishCounterW`
  берётся через `GetProcAddress`, `PdhAddCounterW` — только запасной вариант (Windows XP). Счётчики
  снова работают на неанглийских Windows.
* **`ShouldCustomDrawSystemTitlebar()`** (`ui_part_1`):
  * функция перенесена в `ui/base/win/shell.{h,cc}` (`ui::win::ShouldCustomDrawSystemTitlebar`),
    `hwnd_message_handler.cc` больше не зависит от `//chrome/browser`;
  * `chrome/browser/win/titlebar_config.cc` теперь просто вызывает её;
  * `dwmapi.dll` загружается и `DwmIsCompositionEnabled` ищется один раз, а не на каждом
    `WM_NCPAINT`.
* **Инкогнито-цвета тем** (`ui_part_1`): из Supermium 144 перенесены `ShouldIgnoreThemeSupplier()`
  и `UseIncognitoColor()`, `GetTint()` их использует. Объявления в `theme_helper.h` больше не
  висят без определений.
* **`FeatureList::IsFeatureEnabled`** (`ui_part_1`): перед `CommandLine::ForCurrentProcess()`
  проверяется `CommandLine::InitializedForCurrentProcess()`.
* **QUIC** (`quic_fix`): убран хак в `FinishCreateSession`, который на всех версиях Windows
  превращал любой `ERR_FAILED` в `OK`. Вместо него только на Windows < 10 игнорируется ошибка
  `SetRecvTos()`: этот вызов требует `IP_RECVECN`, а он появился только в Windows 10. Настоящие
  ошибки создания сессии больше не маскируются.
* **`time_ticks_patch.diff`**: `LiveTicksNowIgnoringOverride()` сама вызывает
  `InitializeNowFunctionPointer()`, если частота QPC ещё не получена. Деления на ноль нет:
  `QueryPerformanceFrequency` на XP и новее не возвращает ошибку.
* **`xp_tts_fix`**: убран `DCHECK`, который срабатывал до ленивой инициализации. Если
  инициализация не удалась, озвучка завершается с ошибкой, а не разыменованием `nullptr`.
* **`touch_device_support_win7`**:
  * патч перегенерирован под 150 и применяется `git apply` (раньше — только `patch` с fuzz 2);
  * `GetPointerDevice`, `GetPointerDevices` и `RegisterPointerDeviceNotifications` вызываются через
    указатели, полученные во время выполнения (раньше наличие одной функции проверялось, а
    вызывалась статически импортированная другая);
  * в `remoting/host/input_injector_win.cc` добавлен `#include "base/win/windows_version.h"`;
  * в `ui_base_features.cc` этот `#include` обёрнут в `#if BUILDFLAG(IS_WIN)`.
* **`pdfium_fix`**: после последнего fallback на `Tahoma` тоже заполняется `font_data_`.
* Убраны лишние строки `" "` в конце `client_hints`, `supermium_150_core_encrypt_mojo`,
  `supermium_150_core_mem` и `supermium_150_core_sandbox`.
* В `supermium_150_core_mem`, `ungoogled_supermium_and_mv2`, `misc_changes_20261002`,
  `waveinput_output_restore` и `ptr_device_fix` по существу ничего не менялось.

## Флаги chrome://flags

`supermium_flag_entries.h` содержит 53 записи. Перенесены все флаги Supermium 144, переключатели
которых проверяются патчами 150 или самим Chromium 150. Внутренние имена и порядок вариантов
сохранены, поэтому настройки, сохранённые в 144, при обновлении не теряются.

Изменения по сравнению с 144:

* Добавлена новая запись `enable-win7-webrtc-hw-h264-decoding` (только Windows) для
  переключателя, который восстанавливает `general_features`.
* Флаги, которые в 144 были `FEATURE_VALUE_TYPE`, а в 150 реализованы через переключатель
  командной строки: `force-dark-mode`, `clear-data-on-exit`, `disable-qr-generator`,
  `show-managed-ui`, `top-chrome-toasts`. Они объявлены как `MULTI_VALUE_TYPE` с теми же тремя
  вариантами («Default», «Enabled», «Disabled»). В Local State 144 хранил их как `имя@1` или
  `имя@2`, и эти значения продолжают работать: например, `clear-data-on-exit@1` по-прежнему
  включает очистку данных при выходе. С `SINGLE_VALUE_TYPE` Chromium молча удалил бы такие
  значения при первом запуске. `show-managed-ui` и `top-chrome-toasts` в положении «Disabled»
  передают переключатели `disable-managed-ui` и `disable-toasts`, которые проверяют патчи 150.
  `force-dark-mode` теперь использует штатный переключатель Chromium `--force-dark-mode`, поэтому
  фича `base::features::kForceDarkModeFlag` из `ui_part_1` больше нигде не используется. Это
  безвредно.
* `custom-ntp` и `http-accept-header` объявлены как `STRING_VALUE_TYPE`. В 144 был
  `ORIGIN_LIST_VALUE_TYPE`, который приводит значение к списку origin'ов: из
  `text/html,application/xml;q=0.9` или `file:///…/start.html` получалась пустая или искажённая
  строка. Оба типа хранятся в одном и том же словаре Local State, так что старые значения
  сохраняются.
* У записи Supermium для Mica изменено внутреннее имя: `windows11-mica-titlebar-system`. В 144
  она называлась так же, как запись upstream `windows11-mica-titlebar` (`kWindows11MicaTitlebar`).
  Flags ищет записи по внутреннему имени, поэтому выбор варианта в записи upstream сбрасывал флаг
  Supermium, а сама запись upstream не возвращалась в «Default» и копила выбранные варианты до
  «Reset all». Переключатель командной строки остался прежним (`windows11-mica-titlebar`).
  Сохранённое в 144 значение переносится на новое имя при запуске
  (`about_flags::ConvertFlagsToSwitches()`), поэтому включать флаг заново не нужно.
* Не перенесены флаги, переключатели которых не проверяет ни один патч 150 и ни один файл
  Chromium: `force-gdi` (`disable-direct-write`), `bookmark-bar-ntp`, `remove-grab-handle`,
  `disable-grease-tls`, `hide-sidepanel-button`, `override-tab-outline-default`,
  `override-new-tab-button-shape-default`, `power-bookmarks-side-panel` (фичи
  `kPowerBookmarksSidePanel` в 150 нет), `legacy-tooltips-win`, `native-ui-style`,
  `old-tab-strip-bounds`, `disable-crashpad`. Если их реализацию вернут, записи можно перенести
  из 144.

## Сознательно не менялось

* **`--force-generic-download-icons`** (`general_features`, `icon_loader_win.cc`). В исходном
  аудите это было названо ошибкой, но это не так. В Supermium 144 флаг описан как «традиционный
  способ Chromium получать иконки», то есть с флагом иконка и должна читаться из файла. Название
  флага сбивает с толку, но поведение задумано так.
* **`kTabOverlap`** (`150_about_flags…`). Значение по умолчанию (16) и формула `2 * kTabOverlap`
  такие же, как в Supermium 144. Значения для `v60`, `rectangular` и `cr23` автор сам уменьшил на 5
  в этом же патче. Скорее всего, это задумано, но без проверки на глаз это не подтверждено.
* **`URLDatabase::IsTypedHost()`** при `--user-data-dir` (`general_features`). Автор пометил это
  как временный обход, причина неизвестна. Без воспроизведения исходной проблемы трогать не стоит.
* **`CreateSimpleURLLoaderWithVariationsHeader()` → `nullptr`** при `--ungoogled-supermium`. То же
  было в 144, вызывающих мест, которые бы на этом падали, не найдено.
* Runtime-фича **`UserAgentClientHint`** в `client_hints` никем не используется, но и не мешает.
* **Layout-константы, зависящие от `touch_ui`** (`ui_part_2`, `layout_constants.cc`). Они
  вычисляются один раз, при первом обращении, и не пересчитываются при переключении в режим
  планшета, кроме режима `--enable-advanced-customization`. Это намеренное кеширование автора.
* Закомментированный код **пользовательских форм вкладок** из `scs` (`ui_part_2`). Это незаконченная
  функциональность, а не ошибка.

---

# Исходный аудит

Ниже — исходный отчёт без изменений, кроме пометок о статусе и двух уточнений. Номера строк
относятся к **исходным** патчам (до исправлений). Раздел «Краткий итог» описывает состояние до
исправлений.

Проверены все 18 файлов патчей в корне репозитория (193 правки файлов, ~6000 строк).

## Как проводился аудит

1. **Базовая версия.** Хеши blob'ов из строк `index` в патчах сверены с исходниками Chromium.
   Базой оказался **Chromium 150.0.7871.287**: 173 из 189 исходных файлов совпали байт в байт.
   Остальные 16 — либо цепочки (один файл правится несколькими патчами), либо патч сделан
   на дереве, которое отличается от того, что лежит в репозитории.
   PDFium проверялся на ревизии `6fb120b2b21f` (из `DEPS` версии 150.0.7871.287).
2. **Синтаксис.** Строгий разбор каждого hunk: совпадают ли счётчики строк в заголовках `@@`,
   нет ли строк, которые `git`/`patch` молча пропустят.
3. **Применимость.** Каждый патч отдельно и все последовательно в порядке, указанном автором
   (`core_*` → `ui_part_*` → `general_features` → `150_about_flags…` → остальные).
   Проверено двумя инструментами: `git apply` (строгий, без fuzz) и `patch -p1` (с fuzz).
   Результаты обоих сравнивались, чтобы убедиться, что смещённые hunk'и легли в нужное место.
4. **Смысл изменений.** Каждый hunk прочитан в контексте исходников 150. Проверено, что
   используемые символы, файлы и функции существуют и что логика делает то, что заявлено.

## Краткий итог

* Синтаксически все патчи целы. У четырёх в самом конце есть лишняя строка `" "`, это безвредно.
* `git apply` применяет всё, **кроме `touch_device_support_win7.patch`**. `patch -p1` применяет
  и его, но с fuzz 2.
* **Из опубликованного набора браузер собрать нельзя.** Есть 3 гарантированные ошибки компиляции,
  а одна из них — два заголовочных файла, которых нет в репозитории (раздел 2).
  Значит, релизы собирались из локального дерева, которое отличается от того, что опубликовано.
* Найдено около 10 серьёзных логических ошибок, которые видны пользователю (раздел 3), и ряд мелких.

## 1. Применимость

| Патч | `git apply` | `patch -p1` | Комментарий |
|---|---|---|---|
| supermium_150_core_encrypt_mojo | OK | OK | |
| supermium_150_core_mem | OK | OK | |
| supermium_150_core_sandbox | OK | OK | |
| ui_part_1 | OK | OK | |
| ui_part_2 | OK | OK | |
| general_features | OK* | OK (со смещениями) | *только после ui_part_2 (цепочка `layout_constants.cc`) |
| 150_about_flags_and_finishing_touches | OK* | OK | *только после general_features |
| client_hints | OK | OK | |
| ungoogled_supermium_and_mv2 | OK | OK (смещение) | |
| misc_changes_20261002 | OK | OK | |
| time_ticks_patch.diff | OK | OK (смещение +110) | сделан на другой версии `time_win.cc`, но ложится верно |
| **touch_device_support_win7** | **FAIL** | OK, **fuzz 2** | см. ниже |
| waveinput_output_restore | OK | OK | |
| win7_notification_bug_… | OK | OK | |
| xp_tts_fix | OK | OK (смещение +29) | |
| ptr_device_fix | OK | OK | |
| quic_fix | OK | OK | |
| pdfium_fix (к `third_party/pdfium`) | OK | OK | |

**[исправлено]** **touch_device_support_win7.patch** (строка 117): hunk для `ui/base/ui_base_features.h` опирается на
контекст `BASE_DECLARE_FEATURE(kTSFImeSupport);`. Эту фичу из Chromium давно удалили, так что hunk
перенесён из старого дерева Supermium. Через `git apply` весь патч отклоняется (все 7 файлов).
`patch -p1` ставит его с fuzz 2 внутрь блока `#if BUILDFLAG(IS_WIN)`, и это место правильное.
Если сборочный скрипт использует `git apply` и не проверяет код возврата, поддержка touch для Win7
**молча пропадает целиком**. Исправление: перегенерировать hunk против 150.

## 2. Ошибки сборки: опубликованный набор не компилируется

1. **[исправлено]** **Нет файлов `chrome/browser/supermium_flag_choices.h` и `chrome/browser/supermium_flag_entries.h`.**
   `150_about_flags_and_finishing_touches.patch:17,21` подключает их в `about_flags.cc`, но ни один
   патч их не создаёт, а в upstream их тоже нет. Именно там, судя по всему, описаны все флаги
   Supermium в chrome://flags: `supermium-tab-options`, `compact-ui`, `hide-tab-close-buttons`,
   `ungoogled-supermium`, `revert-from-portable` и десятки других `HasSwitch("…")`. Без них
   `about_flags.cc` не собирается, а `SetFeatureEntryEnabled(…, "ungoogled-supermium")` в
   `chrome_browser_main.cc` и `"revert-from-portable"` в `infobar_utils.cc` ссылаются на
   несуществующие записи.
2. **[исправлено]** **`TemplateURLPrepopulateData::nosearch` не существует.** Его использует
   `ungoogled_supermium_and_mv2.patch:632`. Движок `nosearch` добавлял `search_engines_data.patch`
   (в `third_party/search_engines_data/resources`), но в коммите `cde2ba0` этот патч удалили и
   ничем не заменили. В upstream-версии `prepopulated_engines.json` (ревизия `1aab872a` из DEPS)
   `nosearch` нет, а старый патч к ней не применяется: он ещё и переименовывал
   `SEARCH_ENGINE_*` → `IDR_SEARCH_ENGINE_*` под более старую версию.
3. **[исправлено]** **Опечатка `::CryptUnrotectMemory`** в `supermium_150_core_encrypt_mojo.patch:148`
   (`crypto/process_bound_string.cc`). Должно быть `CryptUnprotectMemory`, иначе ошибка
   «undeclared identifier». Если в локальном дереве эта ошибка как-то обходится, то
   `MaybeDecryptBuffer` вообще не расшифровывает буфер. Это связано с той самой «двойной
   шифровкой строк», о которой написано в сообщении коммита `6e737e5`.

## 3. Серьёзные логические ошибки

### 3.1 На Windows 8/8.1/10/11 браузер считает экран заблокированным: блокируются уведомления
**[исправлено]**

`win7_notification_bug_and_improved_pwa_install_prompt_block.patch:68`, `ui/base/win/lock_state.cc`:
```cpp
// Lock and unlock are reversed on Windows 7.
if (base::win::GetVersion() >= base::win::Version::WIN7)   // <-- должно быть ==
```
По документации Microsoft флаги `WTS_SESSIONSTATE_LOCK` и `WTS_SESSIONSTATE_UNLOCK` перепутаны
**только** в Windows 7 и Server 2008 R2; в старом Chromium здесь было `== WIN7`. С `>=` логика
инвертируется на всех новых версиях. `IsSessionLocked()` задаёт начальное состояние
`SessionLockedObserver`, поэтому на Win8+ браузер стартует в состоянии «заблокировано» и остаётся
в нём до первого цикла «заблокировать → разблокировать». Пока так,
`ScreenLockNotificationBlocker` блокирует веб-уведомления, а Idle API и `chrome.idle` сообщают
`locked`. Патч исправил Win7, но сломал всё, что новее.

### 3.2 По умолчанию не работает установка расширений (Chrome Web Store и .crx)
**[исправлено]**

`general_features.patch:1358`, `extensions/browser/extension_util.cc`:
```cpp
-    return true;
+    return ShouldDownloadAsRegularFile();     // <-- должно быть !ShouldDownloadAsRegularFile()
```
Это порт `extension-mime-request-handling` из ungoogled-chromium, но потеряно отрицание. Без флага
`IsExtensionDownload()` теперь возвращает `false`. В итоге:
* `WebstoreInstaller::OnDownloadUpdated` (`extensions/browser/webstore_installer.cc:440`) завершает
  установку из CWS ошибкой `kInvalidDownloadError`;
* `ChromeDownloadManagerDelegate::ShouldOpenDownload` не запускает `CrxInstaller` для .crx и юзерскриптов;
* с флагом `download-as-regular-file` происходит обратное: файлы, наоборот, считаются расширениями.

Остальная часть порта, в `download_target_determiner.cc`, написана правильно, с `!`.

### 3.3 Крэш (`NOTREACHED`) при генерации CSS для WebUI-тулбара
**[исправлено]**

`ui_part_2.patch:477` и `:1025`. В `LayoutConstant` добавлены 17 новых констант, а смысл `kLast`
изменился: раньше `kLast` было равно последнему элементу (`kLast = kWebAppPageActionIconSize`),
теперь это элемент «за последним». `WebUIToolbarLayoutCssHelper::GenerateLayoutConstantsCss()`
перебирает `i <= kLast`, поэтому:
* для новых констант `LayoutConstantToCssVarName()` попадает в добавленный патчем
  `default: break;` и вызывает `NOTREACHED()`, а в 150 это фатальный крэш;
* `GetLayoutConstant(kLast)` читает `layout_constant_values[kLast]`, то есть за границей массива.

`default: break;` по сути только заглушил предупреждение компилятора `-Wswitch` и превратил ошибку
сборки в ошибку времени выполнения. Код срабатывает, когда включён WebUI-тулбар (`InitialWebUI` +
`WebUIReloadButton` и т. п.). Эти фичи включает исследование `WebUIReloadButtonStudy` в
`testing/variations/fieldtrial_testing_config.json`, поэтому крэш будет сразу, если Supermium
собирается без `disable_fieldtrial_testing_config=true`. Иначе — после включения соответствующих
флагов.
Исправление: вернуть `kLast = kTabTitleYOffset`, сделать массив размером `kLast + 1` и в
`LayoutConstantToCssVarName` возвращать имена (или пропускать) для новых констант.

### 3.4 Песочница на Win7/8/8.1: процессы не помещаются в job, объекты утекают
**[исправлено]**

`supermium_150_core_sandbox.patch:96`, `sandbox/win/src/broker_services.cc`. До Win10 вызов
`AddJobToAssociate()` просто пропускается, а запасного `AssignProcessToJobObject()` после
создания процесса нет (в старом Chromium он был). Последствия:
* ограничения job (`KILL_ON_JOB_CLOSE`, лимит активных процессов, UI-ограничения, лимит памяти)
  к рендерерам и GPU-процессу не применяются;
* `FinishSpawnTargetImpl()` всё равно создаёт `JobTracker` и привязывает completion port к
  пустому job. Сообщение `JOB_OBJECT_MSG_ACTIVE_PROCESS_ZERO` не приходит никогда, так что на
  каждый запущенный изолированный процесс утекают `PolicyBase`, `TargetProcess` (handle процесса,
  shared section IPC) и handle job'а.

Для Win8/8.1 (где вложенные job'ы поддерживаются) нужен `AssignProcessToJobObject(job, process)`
до `ResumeThread`. Для Win7 — тот же вызов, и только при ошибке (браузер уже в job без breakaway)
отказываться от job.

### 3.5 Песочница до Win8.1: HandleCloser ничего не закрывает
**[исправлено]**

`supermium_150_core_sandbox.patch:121`, `sandbox/win/src/handle_closer_agent.cc`:
```cpp
if (base::win::GetVersion() < base::win::Version::WIN8_1)  {
  if(GetCurrentProcessHandlesWin7()) return true; else return false;
}
```
Карту handle'ов строят, но не используют: `MaybeCloseHandle()` не вызывается. В итоге в
изолированных процессах на Win7/8.0 остаются открытыми `Windows Shell Global Counters`, `KsecDD`
и другие объекты, которые песочница должна закрывать. Исправление: пройти по карте и для каждой
пары (тип, handle) вызвать `MaybeCloseHandle(type, handle)`.

### 3.6 Чтение файлов `scs` и `uao` за границей буфера
**[исправлено]**

`ui_part_1.patch:352` (`chrome_color_mixers.cc`, `AddUserDefinedMixer`) и
`client_hints.patch:183` (`user_agent_utils.cc`, `parseFile`):
```cpp
std::vector<char> buf(file_size.value());
base::ReadFile(userpath, buf.data(), file_size.value());
std::string bufstr = std::string(buf.data());   // нет завершающего '\0'
```
Строка читается до первого нулевого байта где-то в куче за пределами буфера (UB). Если файл
пустой, `buf.data()` может оказаться `nullptr`. Кроме того, `parseFile()` вызывается при
**каждом** `GetUserAgent()` и `GetUserAgentBrandList()`, то есть блокирующий дисковый I/O на
каждый запрос. Исправление: `base::ReadFileToString()` и кеширование результата.

### 3.7 Пользовательские layout-константы из `scs` не работают
**[исправлено]**

`ui_part_2.patch:395`, `SetLayoutConstants()`:
```cpp
for (int i = 0; i < (int)LayoutConstant::kLast; i++) {
  std::string layout_name = std::string("int_layout_constant_") + std::string("{");  // нет i
```
Индекс `i` в ключ не попадает, поэтому все итерации ищут одну и ту же строку. Ключи вида
`int_layout_constant_5{…}` никогда не находятся, а если записать `int_layout_constant_{N}`, то
значение N получат **все** константы. Видимо, потеряли `base::NumberToString(i)`.

### 3.8 При `--compact-ui` пропадает панель закладок
**[исправлено]**

`general_features.patch:341`, `layout_constants.cc`:
```cpp
if (compact-ui) kBookmarkBarHeight = 30;
kBookmarkBarButtonPadding = touch_ui ? 0 : 4;
if (compact-ui) kBookmarkBarHeight = 0;   // копипаст: должен быть kBookmarkBarButtonPadding
```
Высота панели закладок становится 0.

## 4. Ошибки средней важности

* **[исправлено]** **`--remove-tabsearch-button` на Windows почти не работает.** `general_features.patch:750`:
  проверка попала в блок `#if BUILDFLAG(IS_CHROMEOS)` (инициализация
  `TopControlsSlideControllerChromeOS`) в `BrowserView::AddedToWidget`. В старом Chromium в этом
  месте создавалась кнопка Tab Search. Сейчас её создают `horizontal_tab_strip_region_view.cc` и
  `UpdateTabSearchBubbleHost()`, так что кнопка остаётся, а отключается только команда `IDC_TAB_SEARCH`.
* **[исправлено]** **Правка `render_frame_impl.cc` ничего не делает.** `general_features.patch:1248`: условие
  меняется на `#if !ANDROID && !WIN`, но в 150 обе ветки содержат один и тот же
  `CHECK(!in_frame_tree_)`. Задуманное смягчение CHECK на Windows не работает, потому что
  upstream уже сделал Android-ветку тоже жёсткой.
* **[исправлено; `chrome_paths.h` по-прежнему подключается (с `// nogncheck`), в `ui/gfx/BUILD.gn` добавлены зависимости только на его сгенерированные заголовки]** **`PaintVectorIcon` читает файл с диска при каждой отрисовке иконки.** `ui_part_2.patch:1151`.
  Это блокирующий I/O на UI-потоке. Если такой файл содержит неизвестную команду, срабатывает
  `NOTREACHED()` в `CommandFromString` и браузер падает при каждой отрисовке. К тому же `//ui/gfx`
  начинает зависеть от `chrome/common/chrome_paths.h`.
* **[исправлено]** **Legacy-диалог «Сохранить» (XP/2003).** `ui_part_2.patch:1540`:
  `lpstrInitialDir = suggested_directory.value().c_str()`, а `suggested_directory` — локальная
  переменная внутреннего блока `if`, которая уничтожена до вызова `GetSaveFileNameW`. Получается
  висячий указатель. Строка `:1546`: `wcslcpy(…, sizeof(filename_buffer))` передаёт размер в
  байтах вместо символов. Строки `:1588` и далее: оставлены отладочные `LOG(ERROR)`.
  В `ExecuteFolder_Legacy` вызывается `paths->at(0)` даже тогда, когда путь не добавлен
  (это abort).
* **[исправлено]** **`ui/snapshot/snapshot_win.cc`** (`ui_part_2.patch:1860`): DC, полученный через `GetDC(NULL)`,
  освобождается через `DeleteDC` вместо `ReleaseDC`. На ветке с ранним `return` DC вообще не
  освобождается, то есть GDI-утечка. Кроме того, берётся `GetWindowRect` (окно целиком с рамкой),
  а не клиентская область, поэтому снимок смещён (это пытаются компенсировать через `+ 8`).
* **[исправлено]** **CPU Pressure не работает на нелокализованных именах счётчиков.**
  `supermium_150_core_encrypt_mojo.patch:86`: `PdhAddEnglishCounter` заменён на `PdhAddCounter`
  для всех ОС. Пути счётчиков заданы по-английски (`\Processor(_Total)\% Processor Time`), а
  `PdhAddCounter` ожидает локализованные имена. На русской (и любой неанглийской) Windows Vista+
  `CpuProbeWin` перестаёт работать. Правильнее брать `PdhAddEnglishCounterW` через `GetProcAddress`
  и использовать `PdhAddCounter` только как запасной вариант на XP.
* **[исправлено]** **Возможное зависание в песочнице.** `supermium_150_core_sandbox.patch:166`:
  `while(!::ReadProcessMemory(...)) ;` — бесконечный busy-loop, если память дочернего процесса так
  и не станет доступной (процесс упал, нет прав).
* **[исправлено; значения, зависящие от `touch_ui`, по-прежнему вычисляются один раз (кроме `--enable-advanced-customization`)]** **Нулевые layout-константы до первой инициализации.** `GetLayoutConstant()` теперь просто читает
  массив, который заполняется только в `SetLayoutConstants()`. Её вызывают лишь
  `LocationBarView::Init`, `TabStrip::Init` и `TabStyle::GetStandardWidth`, так что любое обращение
  до них вернёт 0. Надёжнее инициализировать лениво внутри самой `GetLayoutConstant()`.
  Все 69 upstream-констант в массив перенесены. Значения совпадают с upstream, кроме намеренно
  изменённых (`kTabHeight` 30/35 вместо 35, `kTabSeparatorHeight` и т. п.). От `touch_ui` они
  теперь пересчитываются только при `--enable-advanced-customization`.
* **[исправлено]** **`ShouldCustomDrawSystemTitlebar()`** (`ui_part_1.patch:465`) вызывает `LoadLibraryW(dwmapi.dll)`
  без `FreeLibrary` при каждом вызове, а вызывается она из `WM_NCPAINT`, `WM_ERASEBKGND`,
  `ScopedRedrawLock` и т. д. Кроме того, `ui/views/win/hwnd_message_handler.cc` теперь подключает
  `chrome/browser/win/titlebar_config.h` (`ui_part_1.patch:617`), то есть `//ui/views` зависит от
  `//chrome/browser`. Монолитная release-сборка `chrome.dll` так линкуется, а component-сборка
  и `views_unittests` — нет.
* **[исправлено]** **QUIC.** `quic_fix.patch:12`: любой `ERR_FAILED` при создании сессии превращается в `OK` на
  **всех** версиях Windows, а не только на Win7, как сказано в комментарии. Настоящие ошибки
  создания сокета маскируются. Правильнее игнорировать конкретную неподдерживаемую опцию сокета на Win7.
* **[не ошибка]** **`--force-generic-download-icons` работает наоборот.** `general_features.patch:242`: с флагом
  иконка читается из самого файла в sandbox-процессе (то есть не generic), без флага используется
  generic. Вероятно, нужно `!HasSwitch(...)`.
  *Уточнение: в Supermium 144 флаг описан как «традиционный способ Chromium получать иконки», то
  есть такое поведение задумано.*
* **[оставлено как есть]** **`URLDatabase::IsTypedHost()` всегда `false` при `--user-data-dir`.** `general_features.patch:980`.
  Помечено как «временное», но ломает эвристику omnibox для всех portable-пользователей.

## 5. Мелкие замечания

* **[исправлено]** `pdfium_fix.patch:18`: если сработал последний fallback (`Tahoma`), `font_data_` не присваивается.
  Skia в этом случае рисует текст медленным путём через битмапы глифов (`fx_skia_device.cpp:813`).
  Нужен ещё один `if (face_) font_data_ = face_->GetData();`.
* **[исправлено]** `ui_part_2.patch:590`, `Tab::UpdateIconVisibility`: вычитание ширины кнопки закрытия стало
  безусловным (было `if (showing_close_button_)`). При включённом declutter у активной вкладки без
  hover может исчезать favicon.
* **[исправлено]** `ui_part_2.patch:1914`, `menu_config_win.cc`: `separator_upper_height = 5` присваивается дважды
  (видимо, имелся в виду `separator_lower_height`). `icons_in_label = 10` — это поле типа `bool`.
* **[исправлено; `GetIncognitoId()` по-прежнему не используется, как и в 144]** `ui_part_1.patch:212`: в `theme_helper.h` объявлены `UseIncognitoColor()` и
  `ShouldIgnoreThemeSupplier()`, но не определены и не используются. `GetIncognitoId()` определена,
  но не вызывается. Порт инкогнито-цветов тем неполный.
* **[оставлено как есть]** `client_hints.patch:107`: runtime-фича `UserAgentClientHint` в json5 не используется ни одним
  IDL, то есть мёртвая.
* **[оставлено как есть]** `ui_part_2.patch:696`: весь код пользовательских форм вкладок из `scs` закомментирован `/* … */`.
* **[исправлено]** `time_ticks_patch.diff:29`: `LiveTicksNowIgnoringOverride()` делит на `g_qpc_ticks_per_second`,
  который инициализируется только при первом `TimeTicks::Now()`. Комментарий «Ensure that the
  assignment … has happened» ничего не гарантирует. Возможно деление на ноль, если `LiveTicks`
  вызовут первым.
* **[исправлено]** `xp_tts_fix.patch:32`: если повторная `Initialize()` не удалась, `ProcessSpeech` дальше
  разыменовывает `speech_synthesizer_ == nullptr`. Кроме того, перед ленивой инициализацией стоит
  `DCHECK(speech_synthesizer_)`.
* **[исправлено]** `touch_device_support_win7.patch:74`: в `remoting/host/input_injector_win.cc` используется
  `base::win::GetVersion()` без `#include "base/win/windows_version.h"`. Это ошибка компиляции,
  если собирать remoting.
* **[исправлено]** `touch_device_support_win7.patch`: в `GetPointerDevice()` наличие API проверяется по указателю на
  `GetPointerDevices`, а вызывается статически импортированный `::GetPointerDevice`. Это непоследовательно.
* **[исправлено]** `supermium_150_core_sandbox.patch:701`: для 32-бит удалено определение
  `ServiceResolverThunk::VerifyJumpTargetForTesting`, а объявление осталось. В x86 не слинкуется
  `sbox_unittests`.
* **[исправлено]** `ui_part_1.patch:21`: внутри `FeatureList::IsFeatureEnabled` вызывается
  `CommandLine::ForCurrentProcess()`. Если `CommandLine` не инициализирован, это разыменование `nullptr`.
* **[оставлено как есть]** `150_about_flags_and_finishing_touches.patch:34`: значения `kTabOverlap` для `v60`, `rectangular`
  и `cr23` уменьшены на 5 (формула стала `2 * kTabOverlap`), а значение по умолчанию (16) осталось
  прежним. Перекрытие вкладок по умолчанию теперь 26 px против 18 в upstream. Стоит проверить,
  не забыто ли.
  *Уточнение: значение по умолчанию (16) и формула такие же, как в Supermium 144; значения для
  `v60`, `rectangular` и `cr23` автор сам уменьшил на 5. Скорее всего, это задумано.*
* **[оставлено как есть]** `ungoogled_supermium_and_mv2.patch:734`: `CreateSimpleURLLoaderWithVariationsHeader()` при
  `--ungoogled-supermium` возвращает `nullptr`, хотя контракт функции этого не предполагает.
  В каталогах omnibox, NTP и search вызывающих мест не найдено, но это хрупкое место.
* **[исправлено]** В `client_hints`, `supermium_150_core_encrypt_mojo`, `supermium_150_core_mem` и
  `supermium_150_core_sandbox` в конце файла лишняя строка из одного пробела. Безвредно.

## 6. Что в порядке

`supermium_150_core_mem` (динамический размер пула PartitionAlloc для Windows < 8.1 реализован по
образцу iOS-ветки, маски пулов динамические), `misc_changes_20261002`, `waveinput_output_restore`
(восстановленный `PCMWaveInAudioInputStream` соответствует интерфейсу `AudioInputStream` из 150),
`ptr_device_fix`, отключение PWA-действия (отсутствие `ActionItem` обрабатывается корректно),
большая часть переключателей в `general_features` и `ungoogled_supermium_and_mv2`.
