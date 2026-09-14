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

**Linux** (сам зрозуміє систему — Omarchy, Ubuntu, Mint, …):

```bash
curl -fsSL https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/install.sh | bash
```

**Windows 11** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/windows/install.ps1 | iex
```

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
знову — воно запам'ятається і більше не чіпатиметься. Деталі —
у [`omarchy-plugin/README.md`](omarchy-plugin/README.md).

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
- [`windows/`](windows/) — Windows 11: `LangSwitcher.ahk` (усе в одному файлі),
  `install.bat`, `install.ps1`

## Подяка

Алгоритм і таблиці розкладок — з оригінального
[reg2005/langSwitcher](https://github.com/reg2005/langSwitcher) (і форку
Samuel-Ku), ліцензія MIT збережена — див. [`omarchy-plugin/LICENSE`](omarchy-plugin/LICENSE).
Я лише навчив це все жити за межами macOS, щоб більше ніхто не передруковував.
