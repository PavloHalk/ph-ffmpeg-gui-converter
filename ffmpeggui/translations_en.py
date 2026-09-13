"""Англійські переклади. Ключ — український рядок з коду.

Перевірити повноту: python tools/check_i18n.py
"""

EN: dict[str, str] = {
    # ---------------------------------------------------------------- черга та журнал
    'Черга оброблена.': 'Queue finished.',
    'У файлі не знайдено відеопотоку.': 'No video stream found in the file.',
    'Завдання «{name}» додано в чергу. Файлів: {count}.': 'Task "{name}" queued. Files: {count}.',
    '[{task}] Почато: {src} → {dst}': '[{task}] Started: {src} → {dst}',
    'Завдання «{name}» зупинено.': 'Task "{name}" stopped.',
    'Завдання «{name}» завершено. Готових файлів: {done}. Витрачено: {time}.':
        'Task "{name}" finished. Files done: {done}. Time: {time}.',
    '[{task}] Готово за {time}: {path}': '[{task}] Done in {time}: {path}',
    '[{task}] ПОМИЛКА: {name}: {error}': '[{task}] ERROR: {name}: {error}',
    'ffmpeg завершився з кодом {code}': 'ffmpeg exited with code {code}',
    'Завдання «{name}» завершено з помилками: жоден файл не сконвертовано.':
        'Task "{name}" failed: not a single file was converted.',
    'Завдання «{name}» завершено: готово {done}, з помилками {errors}. Витрачено: {time}.':
        'Task "{name}" finished: {done} done, {errors} failed. Time: {time}.',

    # ---------------------------------------------------------------- ffmpeg
    'Завантаження скасовано.': 'Download cancelled.',
    'Розпакування…': 'Extracting…',
    'Не вдалося завантажити ffmpeg.': 'Could not download ffmpeg.',
    'ffprobe не зміг прочитати файл': 'ffprobe could not read the file',
    'Некоректна відповідь ffprobe': 'Malformed ffprobe response',
    'в архіві не знайдено ffmpeg.exe/ffprobe.exe': 'ffmpeg.exe/ffprobe.exe not found in the archive',
    'Завантаження з {source}…': 'Downloading from {source}…',
    'Не вдалося запустити ffprobe: {error}': 'Could not start ffprobe: {error}',

    # ---------------------------------------------------------------- довідка про процеси
    'Скільки файлів конвертувати одночасно.\n\n'
    'Значення можна змінювати й під час конвертації — вона не переривається:\n\n'
    '• Якщо збільшити — діє одразу: програма тут же бере наступні файли з черги '
    'й запускає додаткові процеси ffmpeg.\n\n'
    '• Якщо зменшити — жоден процес не вбивається. Файли, що вже конвертуються, '
    'спокійно дораховуються до кінця, а нові не запускаються, доки їх кількість '
    'не впаде до нового значення. Тобто зменшення діє поступово, на відміну від '
    'кнопки «Зупинити».\n\n'
    '1 означає строго послідовну обробку. Врахуйте, що x264 і так використовує всі '
    'ядра процесора, тож виграш від кількох одночасних процесів зазвичай невеликий.':
        'How many files to convert at the same time.\n\n'
        'You can change this value while conversion is running — nothing is interrupted:\n\n'
        '• Increasing it takes effect immediately: the program picks the next files from '
        'the queue and starts additional ffmpeg processes.\n\n'
        '• Decreasing it kills nothing. Files that are already being converted are finished '
        'normally, and no new ones start until their number drops to the new value. So a '
        'decrease applies gradually, unlike the "Stop" button.\n\n'
        '1 means strictly sequential processing. Keep in mind that x264 already uses all CPU '
        'cores, so running several processes at once rarely helps much.',

    # ---------------------------------------------------------------- головне вікно
    'Показати / сховати список файлів завдання': 'Show / hide the task file list',
    'Почати або зупинити конвертування цього завдання': 'Start or stop converting this task',
    'Змінити файли та налаштування завдання': 'Change the files and settings of the task',
    'Перемістити завдання на 1 позицію вгору': 'Move the task one position up',
    'Перемістити завдання на 1 позицію вниз': 'Move the task one position down',
    'Відкрити в Провіднику теку з готовими файлами': 'Open the output folder in Explorer',
    'Видалити завдання зі списку (файли на диску не видаляються)':
        'Remove the task from the list (no files on disk are deleted)',
    'роздільність як є': 'source resolution',
    'Мову інтерфейсу змінено.': 'Interface language changed.',
    'Створити нове завдання: вибрати файли, теку для результату та якість (Ctrl+N)':
        'Create a new task: choose files, the output folder and the quality (Ctrl+N)',
    'Поставити в чергу всі незавершені завдання й конвертувати їх по черзі':
        'Queue every unfinished task and convert them one after another',
    'Негайно зупинити всі процеси ffmpeg (прогрес поточних файлів буде втрачено)':
        'Stop every ffmpeg process immediately (progress of the current files is lost)',
    'Скільки файлів конвертувати одночасно. 1 — строго по черзі. Значення можна змінювати '
    'під час конвертації: збільшення діє одразу, зменшення — у міру завершення поточних файлів.':
        'How many files to convert at the same time. 1 means strictly one after another. '
        'You may change it during conversion: an increase applies at once, a decrease applies '
        'as the current files finish.',
    'Що буде, якщо змінити це значення під час конвертації?':
        'What happens if you change this value during conversion?',
    'Частка сконвертованих файлів серед усіх файлів у списку завдань — незалежно від того, '
    'що саме зараз запущено.':
        'Share of converted files among all files in the task list — no matter what is '
        'running right now.',
    'Згорнути або розгорнути журнал, щоб звільнити місце для завдань':
        'Collapse or expand the log to free up room for the task list',
    'Зберегти вміст журналу у файл .log': 'Save the log contents to a .log file',
    'Паралельні процеси': 'Parallel processes',
    'Черга порожня': 'The queue is empty',
    'Конвертер відео у формат H.264 — графічна оболонка для ffmpeg.':
        'Video converter to H.264 — a graphical front-end for ffmpeg.',
    'Про програму': 'About',
    'Редагувати': 'Edit',
    'Тека': 'Folder',
    'Видалити': 'Delete',
    '№': '#',
    'Вихідний файл': 'Source file',
    'Результат': 'Output',
    'Стан': 'Status',
    'Прогрес': 'Progress',
    'Час': 'Time',
    'Залишилось': 'Remaining',
    'кадр/с': 'fps',
    'минуло {time}': 'elapsed {time}',
    'витрачено {time}': 'took {time}',
    'Додати завдання…': 'Add task…',
    'Вихід': 'Exit',
    'Файл': 'File',
    'Запустити всі': 'Start all',
    'Зупинити все': 'Stop all',
    'Прибрати завершені завдання зі списку': 'Remove finished tasks from the list',
    'Черга': 'Queue',
    'Мова інтерфейсу': 'Interface language',
    'Перевірити / встановити ffmpeg…': 'Check / install ffmpeg…',
    'Відкрити теку bin (ffmpeg)': 'Open the bin folder (ffmpeg)',
    'Відкрити теку з пресетами та чергою': 'Open the folder with presets and queue',
    'Налаштування': 'Settings',
    'Довідка': 'Help',
    '▶ Запустити всі': '▶ Start all',
    '■ Зупинити все': '■ Stop all',
    'Завдання': 'Tasks',
    'Немає завдань. Натисніть «Додати завдання…», щоб почати.':
        'No tasks yet. Click "Add task…" to get started.',
    'Зберегти журнал…': 'Save log…',
    'Журнал': 'Log',
    'Журнал порожній.': 'The log is empty.',
    'Зберегти журнал': 'Save log',
    'Редагування': 'Editing',
    'Спершу зупиніть конвертування цього завдання.': 'Stop converting this task first.',
    'Немає завдань для запуску (список порожній або всі завдання вже готові).':
        'Nothing to start (the list is empty or every task is already done).',
    'Видалити завдання «{name}» зі списку?\n\nВихідні та готові файли на диску не видаляються.':
        'Remove task "{name}" from the list?\n\nSource and converted files on disk are kept.',
    'Конвертування цього завдання буде зупинено.': 'Conversion of this task will be stopped.',
    'Видалити завдання': 'Remove task',
    'Немає повністю завершених завдань.': 'There are no fully finished tasks.',
    'Для конвертування потрібен ffmpeg.': 'ffmpeg is required for conversion.',
    '(запущено з вихідних кодів)': '(running from source)',
    '■ Стоп': '■ Stop',
    '▶ Старт': '▶ Start',
    '{app} {version} запущено. Налаштування та черга: {path}':
        '{app} {version} started. Settings and queue: {path}',
    'Помилка': 'Error',
    'Журнал збережено у файл: {path}': 'Log saved to file: {path}',
    'Сконвертовано {processed} з {total} файлів ({percent}%)':
        'Converted {processed} of {total} files ({percent}%)',
    'Додано завдання «{name}». Файлів: {count}.': 'Task "{name}" added. Files: {count}.',
    'Завдання «{name}» змінено.': 'Task "{name}" updated.',
    'Повторна конвертація': 'Convert again',
    'Завдання «{name}» видалено зі списку.': 'Task "{name}" removed from the list.',
    'Версія: {version} від {date}': 'Version: {version} ({date})',
    'Дата збірки: {date}': 'Build date: {date}',
    'Автор: {author}': 'Author: {author}',
    'ffmpeg: {path}': 'ffmpeg: {path}',
    'Дані програми: {path}': 'Application data: {path}',
    'Конвертування ще триває. Зупинити його та вийти?\n\nНедописані файли буде видалено, '
    'завдання залишаться в списку як незавершені.':
        'Conversion is still running. Stop it and exit?\n\nUnfinished output files will be '
        'deleted; the tasks stay in the list as unfinished.',
    'ширина {value}': 'width {value}',
    'висота {value}': 'height {value}',
    'Файлів: {count}  |  CRF {crf}, {preset}, {res}, {container}  |  → {out}':
        'Files: {count}  |  CRF {crf}, {preset}, {res}, {container}  |  → {out}',
    'Перенесено з теки попередньої версії: {files}':
        'Migrated from the folder of the previous version: {files}',
    'Відновлено завдань із попереднього сеансу: {count}.':
        'Tasks restored from the previous session: {count}.',
    'Паралельних процесів:': 'Parallel processes:',
    'Загальний прогрес:': 'Overall progress:',
    'Очистити': 'Clear',
    'Файли журналу': 'Log files',
    'Текстові файли': 'Text files',
    'Усі файли': 'All files',
    'Кількість паралельних процесів: {count}.': 'Parallel processes: {count}.',
    'Завдання {number}': 'Task {number}',
    'Без назви': 'Untitled',
    'Прибрати зі списку завершені завдання ({count})?\nФайли на диску не видаляються.':
        'Remove finished tasks ({count}) from the list?\nNo files on disk are deleted.',
    'Тека ще не існує:\n{path}\n\nВона буде створена під час конвертування першого файлу.':
        'The folder does not exist yet:\n{path}\n\nIt will be created while the first file '
        'is being converted.',
    'ffmpeg знайдено:\n{version}\n\nТека: {path}': 'ffmpeg found:\n{version}\n\nFolder: {path}',
    'залишилось ~{time}': '~{time} left',
    '{fps} кадр/с': '{fps} fps',
    'помилок: {count}': 'errors: {count}',
    'Не вдалося зберегти журнал:\n{error}': 'Could not save the log:\n{error}',
    'Не вдалося зберегти чергу: {error}': 'Could not save the queue: {error}',
    'Не вдалося зберегти налаштування: {error}': 'Could not save the settings: {error}',
    'Усі файли завдання «{name}» вже сконвертовано.\nСконвертувати їх заново '
    '(готові файли буде перезаписано)?':
        'Every file of task "{name}" is already converted.\nConvert them again '
        '(existing output files will be overwritten)?',
    'ffmpeg не знайдено в {path} — конвертація недоступна':
        'ffmpeg not found in {path} — conversion is unavailable',

    # ---------------------------------------------------------------- встановлення ffmpeg
    'ffmpeg не знайдено': 'ffmpeg not found',
    'Як встановити ffmpeg вручну:\n\n'
    '1. Відкрийте сторінку завантаження:\n'
    '      {page1}\n'
    '   і завантажте архів «ffmpeg-release-essentials.zip».\n'
    '   Інший варіант — сторінка\n'
    '      {page2}\n'
    '   файл «ffmpeg-master-latest-win64-gpl.zip».\n\n'
    '2. Розпакуйте архів у будь-яке місце.\n\n'
    '3. Усередині архіву знайдіть теку «bin» і скопіюйте з неї два файли:\n'
    '      ffmpeg.exe\n'
    '      ffprobe.exe\n'
    '   у теку програми:\n'
    '      {bin}\n'
    '   (якщо теки ще немає — створіть її або натисніть «Відкрити теку bin»).\n\n'
    '4. Натисніть «Перевірити знову».\n\n'
    'Встановлювати ffmpeg у систему чи змінювати PATH не потрібно — програма\n'
    'використовує лише файли з теки bin поруч із собою.':
        'How to install ffmpeg manually:\n\n'
        '1. Open the download page:\n'
        '      {page1}\n'
        '   and download the archive "ffmpeg-release-essentials.zip".\n'
        '   An alternative is the page\n'
        '      {page2}\n'
        '   file "ffmpeg-master-latest-win64-gpl.zip".\n\n'
        '2. Unpack the archive anywhere.\n\n'
        '3. Inside the archive find the "bin" folder and copy two files from it:\n'
        '      ffmpeg.exe\n'
        '      ffprobe.exe\n'
        '   into the program folder:\n'
        '      {bin}\n'
        '   (if the folder does not exist yet, create it or press "Open the bin folder").\n\n'
        '4. Press "Check again".\n\n'
        'You do not need to install ffmpeg system-wide or change PATH — the program\n'
        'only uses the files in the bin folder next to itself.',
    'Завантаження ffmpeg': 'Downloading ffmpeg',
    'Встановлення ffmpeg': 'Installing ffmpeg',
    'Підготовка…': 'Preparing…',
    'Скасування…': 'Cancelling…',
    'ffmpeg та ffprobe знайдено. Можна працювати!': 'ffmpeg and ffprobe found. You are all set!',
    'Не знайдено ffmpeg.exe та ffprobe.exe у теці:\n{path}\n\n'
    'Завантажити статичну збірку ffmpeg автоматично?\n'
    '(близько 100 МБ; джерело — gyan.dev, резервне — GitHub)\n\n'
    'Файли буде розпаковано лише в цю теку: системний PATH і реєстр не змінюються, '
    'права адміністратора не потрібні.\n\n'
    '«Ні» — показати інструкцію для ручного встановлення.':
        'ffmpeg.exe and ffprobe.exe were not found in the folder:\n{path}\n\n'
        'Download a static ffmpeg build automatically?\n'
        '(about 100 MB; source — gyan.dev, fallback — GitHub)\n\n'
        'The files are extracted into this folder only: the system PATH and the registry are '
        'left untouched and no administrator rights are needed.\n\n'
        'Choose "No" to see instructions for installing it manually.',
    'Завантаження ffmpeg…': 'Downloading ffmpeg…',
    'ffmpeg знайдено.': 'ffmpeg found.',
    'ffmpeg не встановлено — конвертація недоступна.':
        'ffmpeg is not installed — conversion is unavailable.',
    'ffmpeg успішно завантажено та встановлено.': 'ffmpeg was downloaded and installed successfully.',
    'Скасувати': 'Cancel',
    'Відкрити сторінку завантаження': 'Open the download page',
    'Відкрити теку bin': 'Open the bin folder',
    'Завантажити автоматично': 'Download automatically',
    'Закрити': 'Close',
    'Перевірити знову': 'Check again',
    'Файли ffmpeg.exe та ffprobe.exe досі не знайдено в теці:\n{path}':
        'ffmpeg.exe and ffprobe.exe are still missing from the folder:\n{path}',
    'Автоматичне завантаження не вдалося:': 'The automatic download failed:',
    'ffmpeg встановлено в {path}': 'ffmpeg installed into {path}',
    'Файли буде розпаковано в: {path}': 'The files will be extracted to: {path}',
    '{done} з {total} МБ': '{done} of {total} MB',
    '{done} МБ': '{done} MB',

    # ---------------------------------------------------------------- вікно завдання
    'Вибрати один чи кілька файлів. Можна додати будь-який файл, який здатен прочитати ffmpeg.':
        'Pick one or more files. Any file ffmpeg can read may be added.',
    'Додати всі відеофайли з теки (mp4, mov, mkv, avi, mts, m2ts тощо).':
        'Add every video file from a folder (mp4, mov, mkv, avi, mts, m2ts and so on).',
    'Текст, що додається на початок імені кожного готового файлу. Можна залишити порожнім.':
        'Text added to the beginning of every converted file name. May be left empty.',
    'CRF (Constant Rate Factor) — рівень якості. 0 — без втрат, 17–18 — візуально без втрат, '
    '23 — типове значення ffmpeg. Менше число = краща якість і більший файл.':
        'CRF (Constant Rate Factor) is the quality level. 0 is lossless, 17–18 is visually '
        'lossless, 23 is the ffmpeg default. A lower number means better quality and a bigger file.',
    'Повільніші пресети стискають ефективніше (менший файл за тієї самої якості), але кодують '
    'довше. На якість при заданому CRF впливає мало.':
        'Slower presets compress more efficiently (a smaller file at the same quality) but take '
        'longer to encode. At a given CRF they barely change the picture itself.',
    'Можна вибрати зі списку або ввести своє значення (наприклад 25 або 29.97).':
        'Choose a value from the list or type your own (for example 25 or 29.97).',
    'Використати бітрейт звуку вихідного файлу (якщо його вдасться визначити).':
        'Use the audio bitrate of the source file (if it can be detected).',
    'Розширені налаштування': 'Advanced settings',
    'Інтервал ключових\nкадрів (keyint):': 'Keyframe interval\n(keyint):',
    'Як часто у відео трапляються повні (незалежні) кадри. Менший інтервал дає плавніше '
    'перемотування/скрабінг при монтажі, але трохи збільшує розмір файлу. 30 ≈ один ключовий '
    'кадр на секунду при 30 кадр/с. 0 — не задавати (типове значення x264 — 250).':
        'How often complete (independent) frames appear in the video. A shorter interval makes '
        'seeking and scrubbing smoother while editing, but slightly increases the file size. '
        '30 ≈ one keyframe per second at 30 fps. 0 means "do not set" (the x264 default is 250).',
    'Мінімальний інтервал\n(min-keyint):': 'Minimum interval\n(min-keyint):',
    'Найменша відстань між ключовими кадрами. 1 дозволяє кодеку ставити ключовий кадр '
    'на будь-якій зміні сцени.':
        'The smallest distance between keyframes. 1 lets the encoder put a keyframe at every '
        'scene change.',
    'Формат пікселів\n(pix_fmt):': 'Pixel format\n(pix_fmt):',
    'Спосіб кодування кольору. yuv420p забезпечує сумісність відео з переважною більшістю '
    'програм монтажу та програвачів — змінювати без потреби не варто. yuv422p/yuv444p '
    'зберігають більше інформації про колір, але можуть не відкриватися в деяких програмах.':
        'How colour is encoded. yuv420p keeps the video compatible with the vast majority of '
        'editors and players — there is rarely a reason to change it. yuv422p/yuv444p keep more '
        'colour information but may not open in some applications.',
    'Оптимізація (tune):': 'Tuning (tune):',
    'Підлаштовує кодек під тип вмісту. Зазвичай не потрібна — залиште «Немає».':
        'Adapts the encoder to the type of content. Usually unnecessary — leave it at "None".',
    'Контейнер:': 'Container:',
    'Тип вихідного файлу. MP4 — найсумісніший. MOV — якщо копіюєте звук у форматі PCM. '
    'MKV — універсальний, але гірше підтримується програмами монтажу.':
        'The type of the output file. MP4 is the most compatible. MOV helps when you copy PCM '
        'audio. MKV is universal but less well supported by editing software.',
    'Швидкий старт:': 'Fast start:',
    'Переносить службову інформацію на початок файлу, щоб відео починало грати ще до повного '
    'завантаження (браузер, мережа). Для монтажу не потрібно. Лише для MP4/MOV.':
        'Moves the service information to the beginning of the file so the video starts playing '
        'before it is fully downloaded (browser, network). Not needed for editing. MP4/MOV only.',
    'Додаткові параметри\nffmpeg:': 'Extra ffmpeg\narguments:',
    'Для досвідчених користувачів: довільні параметри ffmpeg, що додаються перед іменем '
    'вихідного файлу. Приклад: -map_metadata 0. Залиште порожнім, якщо не впевнені.':
        'For advanced users: arbitrary ffmpeg arguments inserted before the output file name. '
        'For example: -map_metadata 0. Leave empty if you are not sure.',
    '(змінено)': '(modified)',
    'Налаштування нижче відрізняються від збережених у цьому пресеті. Щоб оновити сам пресет, '
    'натисніть «Зберегти як пресет…» і підтвердіть перезапис під тим самим іменем.':
        'The settings below differ from the ones stored in this preset. To update the preset '
        'itself, press "Save as preset…" and confirm overwriting it under the same name.',
    'Зберегти пресет': 'Save preset',
    'Назва пресету:': 'Preset name:',
    'Видалити пресет': 'Delete preset',
    'Якість (CRF)': 'Quality (CRF)',
    'Інтервал ключових кадрів': 'Keyframe interval',
    'Мінімальний інтервал': 'Minimum interval',
    'Редагування завдання': 'Edit task',
    'Нове завдання': 'New task',
    'Вихідні файли': 'Source files',
    'Додати файли…': 'Add files…',
    'Додати теку…': 'Add folder…',
    'Куди зберігати': 'Where to save',
    'Пресет налаштувань': 'Settings preset',
    'Відео (H.264 / libx264)': 'Video (H.264 / libx264)',
    'Ширина': 'Width',
    'Висота': 'Height',
    'Введіть значення в головне поле — друге розраховується автоматично зі збереженням '
    'пропорцій кожного вихідного файлу.':
        'Type the value into the main field — the other one is calculated automatically, '
        'keeping the aspect ratio of each source file.',
    'Аудіо': 'Audio',
    'Як є': 'As is',
    'Власний:': 'Custom:',
    'Друге поле буде розраховано автоматично для кожного файлу (ffmpeg не знайдено).':
        'The other field will be calculated automatically for each file (ffmpeg not found).',
    'авто': 'auto',
    'Визначення розміру першого файлу…': 'Reading the size of the first file…',
    'Виберіть відеофайли': 'Choose video files',
    'Виберіть теку з відео': 'Choose a folder with video',
    'Нічого не знайдено': 'Nothing found',
    'Додано файли': 'Files added',
    'Вилучити всі файли зі списку завдання?': 'Remove every file from the task list?',
    'Тека для готових файлів': 'Folder for converted files',
    'Пресет': 'Preset',
    'Спершу виберіть пресет у списку.': 'Choose a preset from the list first.',
    'Бітрейт аудіо': 'Audio bitrate',
    'Додайте хоча б один файл.': 'Add at least one file.',
    'Вкажіть повний шлях до теки для готових файлів.':
        'Enter the full path of the folder for converted files.',
    'Префікс не може містити символи  < > : " / \\ | ? *':
        'The prefix cannot contain the characters  < > : " / \\ | ? *',
    "Якщо кілька файлів завдання отримають однакове ім'я (наприклад, з різних тек), "
    "до імені додається суфікс _000, _001, _002 …":
        'If several files of the task end up with the same name (for example from different '
        'folders), the suffix _000, _001, _002 … is appended.',
    'Пресет зберігає всі налаштування якості нижче (базові та розширені). Вибір пресету '
    'одразу заповнює поля.':
        'A preset stores every quality setting below (basic and advanced). Choosing a preset '
        'fills in the fields at once.',
    '0–51; менше = краща якість і більший файл. 17–18 — візуально без втрат.':
        '0–51; lower means better quality and a bigger file. 17–18 is visually lossless.',
    '«Копіювати без перекодування» зберігає звук без змін (бітрейт не застосовується). '
    'Деякі кодеки (наприклад PCM) не підтримуються контейнером MP4 — тоді виберіть '
    'контейнер MOV у розширених налаштуваннях.':
        '"Copy without re-encoding" keeps the audio untouched (the bitrate is not applied). '
        'Some codecs (PCM for example) are not supported by the MP4 container — choose the MOV '
        'container in the advanced settings then.',
    'Розмір першого файлу: {w}×{h}. Для інших файлів пропорції беруться з кожного файлу окремо.':
        'Size of the first file: {w}×{h}. For the other files the aspect ratio is taken from '
        'each file separately.',
    'Друге поле буде розраховано автоматично для кожного файлу.':
        'The other field will be calculated automatically for each file.',
    'Додайте файли, щоб побачити розрахунок другого поля.':
        'Add files to see how the second field is calculated.',
    'Помилка в налаштуваннях': 'Invalid settings',
    'Пресет існує': 'Preset already exists',
    'Видалити пресет «{name}»?': 'Delete preset "{name}"?',
    'Поле «Частота кадрів»: значення має бути від 1 до 1000.':
        'Field "Frame rate": the value must be between 1 and 1000.',
    'Назва завдання:': 'Task name:',
    'Зберегти': 'Save',
    'разом з підтеками': 'including subfolders',
    'Вилучити': 'Remove',
    '▲ Вгору': '▲ Up',
    '▼ Вниз': '▼ Down',
    'За назвою': 'By name',
    'Тека для готових файлів:': 'Folder for converted files:',
    'Огляд…': 'Browse…',
    'Префікс імені:': 'Name prefix:',
    'Зберегти як пресет…': 'Save as preset…',
    'Якість (CRF):': 'Quality (CRF):',
    'Швидкість (preset):': 'Speed (preset):',
    'Роздільність:': 'Resolution:',
    'Власна': 'Custom',
    'Головне поле:': 'Main field:',
    '×  Висота': '×  Height',
    'px': 'px',
    'Частота кадрів:': 'Frame rate:',
    'Власна:': 'Custom:',
    'Кодек:': 'Codec:',
    'Бітрейт:': 'Bitrate:',
    'кбіт/с': 'kbit/s',
    'Файлів: {count}': 'Files: {count}',
    'Приклад: {name}': 'Example: {name}',
    'Відеофайли': 'Video files',
    'У теці не знайдено відеофайлів:\n{path}': 'No video files found in the folder:\n{path}',
    'Знайдено файлів: {found}, додано: {added} (решта вже є в списку).':
        'Files found: {found}, added: {added} (the rest are already in the list).',
    'Поле «{field}»: значення має бути від {lo} до {hi}.':
        'Field "{field}": the value must be between {lo} and {hi}.',
    'Поле «Частота кадрів»: введіть число, наприклад 25 або 29.97.':
        'Field "Frame rate": enter a number, for example 25 or 29.97.',
    'Пресет «{name}» вже існує. Перезаписати?': 'Preset "{name}" already exists. Overwrite?',
    'Поле «{field}»: введіть ціле число.': 'Field "{field}": enter a whole number.',
    'Не вдалося прочитати теку:\n{error}': 'Could not read the folder:\n{error}',
    'Поле «Додаткові параметри ffmpeg»: {error}': 'Field "Extra ffmpeg arguments": {error}',
    '(натисніть, щоб розгорнути)': '(click to expand)',

    # ---------------------------------------------------------------- статуси та списки
    'Очікує': 'Waiting',
    'Конвертується': 'Converting',
    'Готово': 'Done',
    'Зупинено': 'Stopped',
    'Не почато': 'Not started',
    'В черзі': 'Queued',
    'З помилками': 'Failed',
    'Готово, є помилки': 'Done, with errors',
    'Не завершено': 'Unfinished',
    'найшвидше кодування, найбільший файл': 'fastest encoding, biggest file',
    'дуже швидко, файл великий': 'very fast, large file',
    'швидко': 'fast',
    'швидше за стандарт': 'faster than the default',
    'трохи швидше за стандарт': 'slightly faster than the default',
    'стандарт ffmpeg — баланс': 'the ffmpeg default — balanced',
    'повільніше, менший файл': 'slower, smaller file',
    'ще повільніше, ще менший файл': 'even slower, even smaller file',
    'найповільніше, найменший файл': 'slowest, smallest file',
    'AAC (рекомендовано)': 'AAC (recommended)',
    'MP3': 'MP3',
    'Копіювати без перекодування': 'Copy without re-encoding',
    'Без звуку': 'No audio',
    'yuv420p (рекомендовано)': 'yuv420p (recommended)',
    'yuv422p': 'yuv422p',
    'yuv444p': 'yuv444p',
    'Як у вихідного файлу': 'Same as the source file',
    'Немає': 'None',
    'film — зйомка з реального життя': 'film — live action footage',
    'animation — мультиплікація': 'animation — cartoons',
    'grain — зберегти плівкове зерно': 'grain — keep the film grain',
    'stillimage — статичні кадри': 'stillimage — static images',
    'fastdecode — легке декодування': 'fastdecode — easy decoding',
}
