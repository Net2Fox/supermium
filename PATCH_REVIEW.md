# Аудит патчей Supermium 150

Проверены все 18 файлов патчей в корне репозитория (193 правки файлов, ~6000 строк).

## Как проверялось

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

**touch_device_support_win7.patch** (строка 117): hunk для `ui/base/ui_base_features.h` опирается на
контекст `BASE_DECLARE_FEATURE(kTSFImeSupport);`. Эту фичу из Chromium давно удалили, так что hunk
перенесён из старого дерева Supermium. Через `git apply` весь патч отклоняется (все 7 файлов).
`patch -p1` ставит его с fuzz 2 внутрь блока `#if BUILDFLAG(IS_WIN)`, и это место правильное.
Если сборочный скрипт использует `git apply` и не проверяет код возврата, поддержка touch для Win7
**молча пропадает целиком**. Исправление: перегенерировать hunk против 150.

## 2. Ошибки сборки: опубликованный набор не компилируется

1. **Нет файлов `chrome/browser/supermium_flag_choices.h` и `chrome/browser/supermium_flag_entries.h`.**
   `150_about_flags_and_finishing_touches.patch:17,21` подключает их в `about_flags.cc`, но ни один
   патч их не создаёт, а в upstream их тоже нет. Именно там, судя по всему, описаны все флаги
   Supermium в chrome://flags: `supermium-tab-options`, `compact-ui`, `hide-tab-close-buttons`,
   `ungoogled-supermium`, `revert-from-portable` и десятки других `HasSwitch("…")`. Без них
   `about_flags.cc` не собирается, а `SetFeatureEntryEnabled(…, "ungoogled-supermium")` в
   `chrome_browser_main.cc` и `"revert-from-portable"` в `infobar_utils.cc` ссылаются на
   несуществующие записи.
2. **`TemplateURLPrepopulateData::nosearch` не существует.** Его использует
   `ungoogled_supermium_and_mv2.patch:632`. Движок `nosearch` добавлял `search_engines_data.patch`
   (в `third_party/search_engines_data/resources`), но в коммите `cde2ba0` этот патч удалили и
   ничем не заменили. В upstream-версии `prepopulated_engines.json` (ревизия `1aab872a` из DEPS)
   `nosearch` нет, а старый патч к ней не применяется: он ещё и переименовывал
   `SEARCH_ENGINE_*` → `IDR_SEARCH_ENGINE_*` под более старую версию.
3. **Опечатка `::CryptUnrotectMemory`** в `supermium_150_core_encrypt_mojo.patch:148`
   (`crypto/process_bound_string.cc`). Должно быть `CryptUnprotectMemory`, иначе ошибка
   «undeclared identifier». Если в локальном дереве эта ошибка как-то обходится, то
   `MaybeDecryptBuffer` вообще не расшифровывает буфер. Это связано с той самой «двойной
   шифровкой строк», о которой написано в сообщении коммита `6e737e5`.

## 3. Серьёзные логические ошибки

### 3.1 На Windows 8/8.1/10/11 браузер считает экран заблокированным: блокируются уведомления
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
`ui_part_2.patch:395`, `SetLayoutConstants()`:
```cpp
for (int i = 0; i < (int)LayoutConstant::kLast; i++) {
  std::string layout_name = std::string("int_layout_constant_") + std::string("{");  // нет i
```
Индекс `i` в ключ не попадает, поэтому все итерации ищут одну и ту же строку. Ключи вида
`int_layout_constant_5{…}` никогда не находятся, а если записать `int_layout_constant_{N}`, то
значение N получат **все** константы. Видимо, потеряли `base::NumberToString(i)`.

### 3.8 При `--compact-ui` пропадает панель закладок
`general_features.patch:341`, `layout_constants.cc`:
```cpp
if (compact-ui) kBookmarkBarHeight = 30;
kBookmarkBarButtonPadding = touch_ui ? 0 : 4;
if (compact-ui) kBookmarkBarHeight = 0;   // копипаст: должен быть kBookmarkBarButtonPadding
```
Высота панели закладок становится 0.

## 4. Ошибки средней важности

* **`--remove-tabsearch-button` на Windows почти не работает.** `general_features.patch:750`:
  проверка попала в блок `#if BUILDFLAG(IS_CHROMEOS)` (инициализация
  `TopControlsSlideControllerChromeOS`) в `BrowserView::AddedToWidget`. В старом Chromium в этом
  месте создавалась кнопка Tab Search. Сейчас её создают `horizontal_tab_strip_region_view.cc` и
  `UpdateTabSearchBubbleHost()`, так что кнопка остаётся, а отключается только команда `IDC_TAB_SEARCH`.
* **Правка `render_frame_impl.cc` ничего не делает.** `general_features.patch:1248`: условие
  меняется на `#if !ANDROID && !WIN`, но в 150 обе ветки содержат один и тот же
  `CHECK(!in_frame_tree_)`. Задуманное смягчение CHECK на Windows не работает, потому что
  upstream уже сделал Android-ветку тоже жёсткой.
* **`PaintVectorIcon` читает файл с диска при каждой отрисовке иконки.** `ui_part_2.patch:1151`.
  Это блокирующий I/O на UI-потоке. Если такой файл содержит неизвестную команду, срабатывает
  `NOTREACHED()` в `CommandFromString` и браузер падает при каждой отрисовке. К тому же `//ui/gfx`
  начинает зависеть от `chrome/common/chrome_paths.h`.
* **Legacy-диалог «Сохранить» (XP/2003).** `ui_part_2.patch:1540`:
  `lpstrInitialDir = suggested_directory.value().c_str()`, а `suggested_directory` — локальная
  переменная внутреннего блока `if`, которая уничтожена до вызова `GetSaveFileNameW`. Получается
  висячий указатель. Строка `:1546`: `wcslcpy(…, sizeof(filename_buffer))` передаёт размер в
  байтах вместо символов. Строки `:1588` и далее: оставлены отладочные `LOG(ERROR)`.
  В `ExecuteFolder_Legacy` вызывается `paths->at(0)` даже тогда, когда путь не добавлен
  (это abort).
* **`ui/snapshot/snapshot_win.cc`** (`ui_part_2.patch:1860`): DC, полученный через `GetDC(NULL)`,
  освобождается через `DeleteDC` вместо `ReleaseDC`. На ветке с ранним `return` DC вообще не
  освобождается, то есть GDI-утечка. Кроме того, берётся `GetWindowRect` (окно целиком с рамкой),
  а не клиентская область, поэтому снимок смещён (это пытаются компенсировать через `+ 8`).
* **CPU Pressure не работает на нелокализованных именах счётчиков.**
  `supermium_150_core_encrypt_mojo.patch:86`: `PdhAddEnglishCounter` заменён на `PdhAddCounter`
  для всех ОС. Пути счётчиков заданы по-английски (`\Processor(_Total)\% Processor Time`), а
  `PdhAddCounter` ожидает локализованные имена. На русской (и любой неанглийской) Windows Vista+
  `CpuProbeWin` перестаёт работать. Правильнее брать `PdhAddEnglishCounterW` через `GetProcAddress`
  и использовать `PdhAddCounter` только как запасной вариант на XP.
* **Возможное зависание в песочнице.** `supermium_150_core_sandbox.patch:166`:
  `while(!::ReadProcessMemory(...)) ;` — бесконечный busy-loop, если память дочернего процесса так
  и не станет доступной (процесс упал, нет прав).
* **Нулевые layout-константы до первой инициализации.** `GetLayoutConstant()` теперь просто читает
  массив, который заполняется только в `SetLayoutConstants()`. Её вызывают лишь
  `LocationBarView::Init`, `TabStrip::Init` и `TabStyle::GetStandardWidth`, так что любое обращение
  до них вернёт 0. Надёжнее инициализировать лениво внутри самой `GetLayoutConstant()`.
  Все 69 upstream-констант в массив перенесены. Значения совпадают с upstream, кроме намеренно
  изменённых (`kTabHeight` 30/35 вместо 35, `kTabSeparatorHeight` и т. п.). От `touch_ui` они
  теперь пересчитываются только при `--enable-advanced-customization`.
* **`ShouldCustomDrawSystemTitlebar()`** (`ui_part_1.patch:465`) вызывает `LoadLibraryW(dwmapi.dll)`
  без `FreeLibrary` при каждом вызове, а вызывается она из `WM_NCPAINT`, `WM_ERASEBKGND`,
  `ScopedRedrawLock` и т. д. Кроме того, `ui/views/win/hwnd_message_handler.cc` теперь подключает
  `chrome/browser/win/titlebar_config.h` (`ui_part_1.patch:617`), то есть `//ui/views` зависит от
  `//chrome/browser`. Монолитная release-сборка `chrome.dll` так линкуется, а component-сборка
  и `views_unittests` — нет.
* **QUIC.** `quic_fix.patch:12`: любой `ERR_FAILED` при создании сессии превращается в `OK` на
  **всех** версиях Windows, а не только на Win7, как сказано в комментарии. Настоящие ошибки
  создания сокета маскируются. Правильнее игнорировать конкретную неподдерживаемую опцию сокета на Win7.
* **`--force-generic-download-icons` работает наоборот.** `general_features.patch:242`: с флагом
  иконка читается из самого файла в sandbox-процессе (то есть не generic), без флага используется
  generic. Вероятно, нужно `!HasSwitch(...)`.
* **`URLDatabase::IsTypedHost()` всегда `false` при `--user-data-dir`.** `general_features.patch:980`.
  Помечено как «временное», но ломает эвристику omnibox для всех portable-пользователей.

## 5. Мелкие замечания

* `pdfium_fix.patch:18`: если сработал последний fallback (`Tahoma`), `font_data_` не присваивается.
  Skia в этом случае рисует текст медленным путём через битмапы глифов (`fx_skia_device.cpp:813`).
  Нужен ещё один `if (face_) font_data_ = face_->GetData();`.
* `ui_part_2.patch:590`, `Tab::UpdateIconVisibility`: вычитание ширины кнопки закрытия стало
  безусловным (было `if (showing_close_button_)`). При включённом declutter у активной вкладки без
  hover может исчезать favicon.
* `ui_part_2.patch:1914`, `menu_config_win.cc`: `separator_upper_height = 5` присваивается дважды
  (видимо, имелся в виду `separator_lower_height`). `icons_in_label = 10` — это поле типа `bool`.
* `ui_part_1.patch:212`: в `theme_helper.h` объявлены `UseIncognitoColor()` и
  `ShouldIgnoreThemeSupplier()`, но не определены и не используются. `GetIncognitoId()` определена,
  но не вызывается. Порт инкогнито-цветов тем неполный.
* `client_hints.patch:107`: runtime-фича `UserAgentClientHint` в json5 не используется ни одним
  IDL, то есть мёртвая.
* `ui_part_2.patch:696`: весь код пользовательских форм вкладок из `scs` закомментирован `/* … */`.
* `time_ticks_patch.diff:29`: `LiveTicksNowIgnoringOverride()` делит на `g_qpc_ticks_per_second`,
  который инициализируется только при первом `TimeTicks::Now()`. Комментарий «Ensure that the
  assignment … has happened» ничего не гарантирует. Возможно деление на ноль, если `LiveTicks`
  вызовут первым.
* `xp_tts_fix.patch:32`: если повторная `Initialize()` не удалась, `ProcessSpeech` дальше
  разыменовывает `speech_synthesizer_ == nullptr`. Кроме того, перед ленивой инициализацией стоит
  `DCHECK(speech_synthesizer_)`.
* `touch_device_support_win7.patch:74`: в `remoting/host/input_injector_win.cc` используется
  `base::win::GetVersion()` без `#include "base/win/windows_version.h"`. Это ошибка компиляции,
  если собирать remoting.
* `touch_device_support_win7.patch`: в `GetPointerDevice()` наличие API проверяется по указателю на
  `GetPointerDevices`, а вызывается статически импортированный `::GetPointerDevice`. Это непоследовательно.
* `supermium_150_core_sandbox.patch:701`: для 32-бит удалено определение
  `ServiceResolverThunk::VerifyJumpTargetForTesting`, а объявление осталось. В x86 не слинкуется
  `sbox_unittests`.
* `ui_part_1.patch:21`: внутри `FeatureList::IsFeatureEnabled` вызывается
  `CommandLine::ForCurrentProcess()`. Если `CommandLine` не инициализирован, это разыменование `nullptr`.
* `150_about_flags_and_finishing_touches.patch:34`: значения `kTabOverlap` для `v60`, `rectangular`
  и `cr23` уменьшены на 5 (формула стала `2 * kTabOverlap`), а значение по умолчанию (16) осталось
  прежним. Перекрытие вкладок по умолчанию теперь 26 px против 18 в upstream. Стоит проверить,
  не забыто ли.
* `ungoogled_supermium_and_mv2.patch:734`: `CreateSimpleURLLoaderWithVariationsHeader()` при
  `--ungoogled-supermium` возвращает `nullptr`, хотя контракт функции этого не предполагает.
  В каталогах omnibox, NTP и search вызывающих мест не найдено, но это хрупкое место.
* В `client_hints`, `supermium_150_core_encrypt_mojo`, `supermium_150_core_mem` и
  `supermium_150_core_sandbox` в конце файла лишняя строка из одного пробела. Безвредно.

## 6. Что в порядке

`supermium_150_core_mem` (динамический размер пула PartitionAlloc для Windows < 8.1 реализован по
образцу iOS-ветки, маски пулов динамические), `misc_changes_20261002`, `waveinput_output_restore`
(восстановленный `PCMWaveInAudioInputStream` соответствует интерфейсу `AudioInputStream` из 150),
`ptr_device_fix`, отключение PWA-действия (отсутствие `ActionItem` обрабатывается корректно),
большая часть переключателей в `general_features` и `ungoogled_supermium_and_mv2`.
