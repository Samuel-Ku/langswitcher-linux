# LangSwitcher для Linux (Ubuntu + Mint)

Порт [LangSwitcher for macOS](https://github.com/Samuel-Ku/langSwitcher) під Linux:
той самий алгоритм (фізичні позиції клавіш, автовизначення, Greedy Line,
збереження пунктуації), дефолтні розкладки `en,uk,pl`.

Одна версія на обидва світи:
- **Ubuntu (GNOME/Wayland)** — через `wl-clipboard` + `wtype`
- **Linux Mint (Cinnamon/X11)** — через `xclip` + `xdotool`

`bin/linux-convert` сам визначає сесію (`$XDG_SESSION_TYPE`, наявність
`$WAYLAND_DISPLAY`/`$DISPLAY` та утиліт). Перевизначити можна змінною
`LANGSWITCHER_BACKEND=wayland|x11`.

## Встановлення

```bash
cd langswitcher-linux
./install.sh
```

Це встановить пакети (`python3`, `wl-clipboard`, `wtype`, `xclip`, `xdotool`,
`libnotify-bin`), покладе файли в `~/.local/share/langswitcher`, зробить
симлінк `~/.local/bin/linux-convert` і (на GNOME/Cinnamon) зареєструє шорткати:

| Шорткат | Дія |
|---|---|
| `Super+\`` | конвертувати виділення |
| `Super+Shift+\`` | конвертувати рядок (greedy) |

Якщо DE інше (KDE, XFCE…) — додай дві команди вручну:
`linux-convert selection` і `linux-convert greedy`.

Подвійний Shift як на macOS під Linux не зловити (на Wayland — через
композитор, на X11 — ненадійно), тому `Super+\``.

## Використання

1. Надрукував `ghbdsn` замість `привіт`.
2. Виділив текст (або курсор у кінці рядка для greedy).
3. Натиснув `Super+\`` — текст замінився.

## CLI

```bash
~/.local/bin/linux-convert --check   # сесія, бекенд, залежності (JSON)
echo -n 'ghbdsn' | python3 lib/switch.py --layouts en,uk,pl   # привіт
echo -n 'привіт' | python3 lib/switch.py --layouts en,uk,pl   # ghbdsn
echo -n 'hello'  | python3 lib/switch.py --mode auto          # без змін (exit 2)
echo -n 'ghbdsn' | python3 lib/switch.py --mode auto          # привіт
python3 tests/test_convert.py                                  # self-tests
```

`--mode auto` — обережний однопрохідний режим: конвертує лише те, що справді
схоже на неправильну розкладку (немає голосної в поточному скрипті й є в
цільовому), тож звичайні англійські слова не чіпає. Це той самий критерій, що
використовує хук автозаміни після пробілу на Windows.

## Розкладки

- Реальна конвертація: пара `en↔uk` з автовизначенням.
- Польська programisty фізично = US QWERTY, тому кейсу `en↔pl` не існує;
  текст з діакритикою (`ą ć ę ł ń ó ś ź ż`) конвертер **ніколи не чіпає**.
- **Польська через ⌥-шар (як у macOS):** якщо набрати польський текст, коли
  активна кирилична розкладка, діакритичні ⌥-акорди виходять як символи цієї
  розкладки (`ą`=⌥+A→`ƒ`, `ś`=⌥+S→`ы`, `ć`=⌥+C→`≠`, `ż`=⌥+Z→`ђ`). Конвертер
  відновлює їх за фізпозицією: `ьƒлф` → `mąka`, `сяуы≠` → `cześć`. Коли в тексті
  є такі артефакти, ціллю автоматично обирається `pl`.
- Ядро містить рівно `en`, `uk`, `pl` (`en/us`, `uk/ua` — аліаси).

## Layout Switch mode

Як у macOS: після конвертації перемкнути й **системну** розкладку на цільову,
щоб наступне слово вже було в правильній мові.

```bash
printf 'ghbdsn' | python3 lib/switch.py --switch always   # конвертує + перемикає
```

- `--switch never` (default для CLI) / `if-converted` / `always`.
- **Hyprland:** реалізовано через `hyprctl switchxkblayout` (обирає main-клавіатуру,
  знаходить індекс цільової xkb-розкладки). Перевірено наживо.
- **GNOME/Cinnamon/інші:** поки no-op (програмного перемикання без гіпотез немає)
  — конвертація працює, розкладку перемикаєш вручну.
- Воркери (`linux-convert`, omarchy-плагін) передають `--switch always`, тож із
  хоткея поведінка як на macOS. Таблиця мов: `en→us`, `uk→ua`, `pl→pl`.

## Обмеження (чесно)

- Тільки по хоткею: авто-перемикання «на льоту» (як Punto/xneur під X11)
  на Wayland неможливе технічно, а ми тримаємо однакову поведінку скрізь.
- На Mint/X11 після `ctrl+c` потрібна ~0.15с пауза — greedy на дуже
  повільних машинах може не встигнути скопіювати (натисни ще раз).
- В XWayland-вікнах надійніше виділяти мишею (primary selection).

## Файли

- `bin/linux-convert` — воркер (Wayland/X11 автовизначення)
- `lib/langswitcher.py`, `lib/switch.py` — ядро + CLI (тільки stdlib)
- `install.sh` — deps + файли + шорткати GNOME/Cinnamon
- `tests/test_convert.py` — self-tests ядра

## Видалення

```bash
rm -rf ~/.local/share/langswitcher ~/.local/bin/linux-convert
```

(+ прибери два шорткати: GNOME — Параметри → Клавіатура;
Cinnamon — Параметри системи → Клавіатура → Комбінації.)
