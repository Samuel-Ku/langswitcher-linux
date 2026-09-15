# LangSwitcher — більше ніколи не передруковувати

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](omarchy-plugin/LICENSE)
![Linux](https://img.shields.io/badge/Linux-Omarchy%20%7C%20Ubuntu%20%7C%20Mint-lightgrey)
![Windows](https://img.shields.io/badge/Windows-11-blue)
![EN/UK/PL](https://img.shields.io/badge/layouts-EN%20%7C%20UK%20%7C%20PL-green)

Порт [LangSwitcher for macOS](https://github.com/Samuel-Ku/langSwitcher)
(open-source конвертер тексту, набраного не в тій розкладці) на Linux і Windows.

## Чому це існує

Мене капець як дратувало писати текст, не дивлячись на екран. Думка ллється,
пальці літають — а коли думка вже завершена і перед відправкою перевіряю,
чи немає помилок, бачу якусь білібєрду. Виявляється, я забув мову перемкнути.
І треба писати наново. Знову. Кожного разу.

На маку мене рятував LangSwitcher: виділив, натиснув `⇧⇧` — і `ghbdsn`
стає `привіт`. Але на Arch, Ubuntu, Mint і Windows його немає в принципі
(оригінал — Swift + Apple API, тільки macOS). Тому я портовав його усюди,
де працюю. Тепер жодна забута розкладка не змусить мене передруковувати.

## Встановлення в один рядок

**Linux** (сам зрозуміє систему — Omarchy, Ubuntu, Mint, Fedora KDE, …):

```bash
curl -fsSL https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/install.sh | bash
```

На Omarchy до цього варто додати `--auto` — тоді вмикається автоматичний режим
(сам ловить пробіл і виправляє слово):

```bash
curl -fsSL https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/install.sh | bash -s -- --auto
```

**Windows 11** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/windows/install.ps1 | iex
```

### Що надіслати людині

Скопіюй їй один рядок — вона вставляє його в термінал і більше нічого не робить:

| Її система | Що надіслати |
|---|---|
| Omarchy (Hyprland) | `curl -fsSL https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/install.sh \| bash -s -- --auto` |
| Ubuntu / Mint | `curl -fsSL https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/install.sh \| bash` |
| Fedora KDE | те саме, що Ubuntu |
| Windows 11 | `irm https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/windows/install.ps1 \| iex` (у PowerShell) |

`install.sh` спершу друкує, що саме знайшов і що збирається зробити
(`--print-plan` — тільки показати), і за потреби передає прапорці бандлу:
`--auto` на Omarchy, `--dry-run` / `--no-ydotool` / `--no-shortcuts` на Fedora KDE.
На Ubuntu/Mint авто-режиму немає (Wayland не дає скриптам бачити клавіатуру) —
`--auto` там чесно про це скаже й поставить хоткей.

## Як це виглядає

```
Друкуєш:   ghbdsn zr ltkf lheu      (хотів українську, стоїть англійська)
Натискаєш: SUPER + `                (або подвійний Shift на Windows)
Отримуєш:  привіт як дела друг
```

Ніякого передруку. Секунда — і думка врятована.

## Що куди ставиться

| Система | Що встановлюється | Гарячі клавіші |
|---|---|---|
| Omarchy (Hyprland) | Quattro-плагін: іконка ⌨ в барі + панель + сервіс | `SUPER+\`` — виділення, `SUPER+SHIFT+\`` — рядок, `SUPER+BACKSPACE` — скасувати авто-виправлення |
| Fedora KDE (Plasma 6) | воркер `kde-convert` (ydotool + `org.kde.keyboard`) | `Meta+\`` — виділення, `Meta+Shift+\`` — рядок |
| Ubuntu (GNOME) | фоновий воркер + шорткати в Параметрах | `Super+\`` / `Super+Shift+\`` |
| Mint (Cinnamon) | фоновий воркер + шорткати в Параметрах системи | ті самі |
| Windows 11 | AutoHotkey-скрипт в автозапуску | подвійний Shift — виділення, пробіл — автозаміна останнього слова |

Подвійний Shift як на маку під Linux зловити неможливо (Wayland не віддає
такі події), тому там `Super+\``. Зате на Windows — чесний подвійний Shift
і навіть автозаміна після пробілу, як у Punto Switcher.

На Omarchy до цього є авто-режим (плагін сам ловить пробіл) і **словник
користувача**: слово, яке він перетворив дарма, досить стерти й надрукувати
знову — воно запам'ятається і більше не чіпатиметься. Рішення ухвалюють
частотні списки української та англійської плюс оцінка літерних n-грамів, тож
перетворюються і **однолітерні слова** (`z` → `я`), і **відмінкові форми**,
яких немає в жодному списку (`абетки`, `автономної`), і **одруки**
(`ghbdsm` → `привіь`), і **український IT-сленг** (`rjvsn` → `коміт`).
Списки й статистика — згенеровані (`tools/build_words.py`), не рукописні.
Деталі — у [`omarchy-plugin/README.md`](omarchy-plugin/README.md).

На Fedora KDE авто-режиму немає і бути не може: Plasma 6 не дає скриптам
бачити клавіатуру (єдиний справжній API у KWin замкнений на екранні читачі).
Тому там хоткей — і чесний опис того, що перевірено, а що ні, —
у [`fedora-kde/README.md`](fedora-kde/README.md).

## Розкладки

- Працює пара **`en ↔ uk`** з автовизначенням напрямку.
- Польська programisty фізично збігається з US QWERTY — пари `en↔pl`
  не існує в природі, зате текст з `ą ć ę ł ń ó ś ź ż` скрипт
  **ніколи не чіпає** в жодному режимі.
- **Польська через ⌥-шар (як у macOS):** якщо набрати польський текст на
  кириличній розкладці, діакритичні ⌥-акорди виходять символами цієї розкладки
  (`ą`=⌥+A→`ƒ`, `ś`=⌥+S→`ы`, `ć`=⌥+C→`≠`), і конвертер відновлює їх за
  фізпозицією: `ьƒлф` → `mąka`, `сяуы≠` → `cześć`.
- Ядро містить рівно ці три розкладки (`en`, `uk`, `pl`). Російська
  не потрібна і в коді відсутня.

## Структура репозиторію

- [`install.sh`](install.sh) — універсальна точка входу (детект → завантаження → інсталятор компонента)
- [`omarchy-plugin/`](omarchy-plugin/) — плагін для Omarchy: `manifest.json`,
  `Service/BarWidget/Panel.qml`, `bin/langswitcher-convert`, `lib/` (Python-ядро, тільки stdlib)
- [`fedora-kde/`](fedora-kde/) — Fedora KDE (Plasma 6): `bin/kde-convert` (ydotool,
  бо `wtype` на KWin не працює), KDE-бекенд перемикання розкладки в `lib/`,
  `install.sh`, spec для RPM
- [`linux/`](linux/) — Ubuntu/Mint: `bin/linux-convert` (Wayland/X11 автовизначення),
  `install.sh` (apt/dnf/pacman + шорткати GNOME/Cinnamon), тести
- [`tools/build_words.py`](tools/build_words.py) — генератор даних (частотні
  списки + літерні n-грами) з одного пінованого джерела; пише `dist/words.py`
  і `dist/words.txt` з заголовком про джерело й ліцензію
- [`windows/`](windows/) — Windows 11: `LangSwitcher.ahk` (хуки, розкладки,
  рішення, трей), `langswitcher-data.txt` (качається інсталятором), `install.bat`,
  `install.ps1`

## Дані й ліцензія

Код — MIT (спадок оригіналу). Але дані, з яких авто-режим ухвалює рішення, —
похідні від CC BY-SA 4.0 корпусу (`hermitdave/FrequencyWords`, далі
OPUS/OpenSubtitles), тож **у репозиторії їх немає**: `words.py`/`words.txt`
публікуються як release-ассет, пінований URL-ом і SHA-256 в інсталяторах.
Інсталятори качають, звіряють хеш і аж тоді підміняють встановлене. Атрибуція й
умови — у `NOTICE` всередині артефакту та в заголовку кожного згенерованого
файлу.

## Подяка

Алгоритм і таблиці розкладок — з оригінального
[reg2005/langSwitcher](https://github.com/reg2005/langSwitcher) (і форку
Samuel-Ku), ліцензія MIT збережена — див. [`omarchy-plugin/LICENSE`](omarchy-plugin/LICENSE).
Я лише навчив це все жити за межами macOS, щоб більше ніхто не передруковував.
