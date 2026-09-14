# LangSwitcher для Fedora KDE (Plasma 6)

Виділив текст не в тій розкладці → хоткей → текст замінився правильним **і**
перемкнулась розкладка, щоб наступне слово вже було в потрібній мові.
`ghbdsn ` → `привіт `.

Це той самий конвертер, що в Omarchy-плагіні (ядро `lib/` байт-у-байт ідентичне),
але обгортка інша, бо Plasma 6 — не Hyprland у трьох місцях, і кожне з них
коштувало б годин навздогін:

| | Hyprland (Omarchy) | KDE Plasma 6 |
|---|---|---|
| вставити текст | `wtype` | **`ydotool`** — `wtype` на KWin не працює взагалі |
| перемкнути розкладку | `hyprctl switchxkblayout` | `org.kde.keyboard` через `gdbus` |
| хоткей | бінд у `hyprland.lua` | command shortcut у `kglobalshortcutsrc` |

## Встановлення

```sh
git clone https://github.com/Samuel-Ku/langswitcher-linux
cd langswitcher-linux
./fedora-kde/install.sh --dry-run   # спершу подивитись, що воно зробить
./fedora-kde/install.sh
```

Скрипт: ставить пакети через `dnf`, кладе файли в `~/.local/share/langswitcher-kde`,
лінкує `~/.local/bin/kde-convert`, **віддає сокет `ydotoold` твоєму користувачу**
(див. нижче) і реєструє два хоткеї: `Meta+\`` — виділення, `Meta+Shift+\`` — рядок.

RPM-варіант — у [`packaging/README.md`](packaging/README.md).

## Використання

1. Набери текст не тією розкладкою (`ghbdsn` замість `привіт`).
2. Виділи його (або постав курсор у кінець рядка для режиму `greedy`).
3. `Meta+\`` — текст замінено, розкладка перемкнулась.

Перевірка після встановлення — це те, з чого варто почати, бо воно саме скаже,
чого не хватає:

```sh
kde-convert --check        # JSON: session, backend, typer, deps, розкладки KDE, hints
```

## Три речі, об які тут спотикаються

**1. `wtype` на KWin не працює — і мовчки.** `wtype` надсилає клавіші через
`zwp_virtual_keyboard_v1` — це протокол wlroots, а KWin його не реалізує (у KWin
немає жодної згадки про цей протокол; він дає `zwp_input_method_v1`,
`zwp_input_panel_v1` і `zwp_xwayland_keyboard_grab_manager_v1`). Тому звичайний
порт «wl-clipboard + wtype» на Plasma виглядає робочим і не робить нічого.
`ydotool` іде через `uinput` ядра і працює на будь-якому композиторі. Тут
`ydotool` — типовий, `wtype` лишається тільки для wlroots-композиторів
(`LANGSWITCHER_TYPER=wtype`). Зверни увагу: `ydotool key` приймає **числові
кевкоди** (`29:1 46:1 46:0 29:0` — це Ctrl+C), а не назви клавіш.

**2. Сокет `ydotoold` — найчастіша причина «нічого не відбувається».** Fedora
ставить `ydotool.service`, який запускає `ydotoold` **від root** і створює
`/tmp/.ydotool_socket` з правами `0600`. Клієнт від твого користувача до нього
не підключиться. `install.sh` додає drop-in, який віддає сокет тобі:

```ini
# /etc/systemd/system/ydotool.service.d/socket-own.conf
[Service]
ExecStart=
ExecStart=/usr/bin/ydotoold --socket-path=/tmp/.ydotool_socket --socket-own=<uid>:<gid> --socket-perm=0660
```

`kde-convert --check` показує `ydotool.writable` — якщо `false`, дивись
`systemctl status ydotool` і `journalctl -u ydotool`.

**3. `qdbus6` у Fedora не існує.** Qt6-тул зветься `qdbus-qt6` (пакет
`qt6-qttools`, якого в KDE-наборі немає), а голий `/usr/bin/qdbus` — це **Qt4**.
Тому весь D-Bus тут через `gdbus` (пакет `glib2`, є завжди):

```sh
gdbus call --session --dest org.kde.keyboard --object-path /Layouts \
  --method org.kde.KeyboardLayouts.getLayoutsList
gdbus call --session --dest org.kde.keyboard --object-path /Layouts \
  --method org.kde.KeyboardLayouts.setLayout 1
```

`getLayoutsList()` віддає `a(sss)` — `(shortName, displayName, longName)` на
кожну розкладку, і машиночитний там лише перший рядок: це xkb-код (`us`, `ua`),
який і потрібен. `setLayout` повертає bool, тож відмову видно, а не припускається.

## Статус перевірки — прочитай перед тим, як вірити

Ця версія писалася **без жодного сеансу KDE**: на машині розробника Hyprland.
Тому чесно розділю те, що доведено, і те, що ні.

| Перевірено тут | Як саме |
|---|---|
| Конвертер (ядро, `en↔uk`, польські ⌥-артефакти) | `linux/tests/*` — 8 наборів, 463 перевірки |
| Розбір `getLayoutsList()` і вибір індексу для `setLayout` | `test_layoutswitch.py`, на справжньому форматі виводу `gdbus` і з інʼєкцією runner'а |
| Вибір бекенда (Hyprland / KDE / нічого) і override `LANGSWITCHER_LAYOUT_BACKEND` | там же |
| Що `wtype` на KWin — глухий кут | первинне джерело: у дереві KWin немає `zwp_virtual_keyboard`; у wlroots він є |
| Що `key` в ydotool — лише кевкоди | README ydotool: «key now (only) accepts keycodes» |
| Назви пакунків Fedora, шлях `ydotoold`, 0600 на сокеті | dist-git spec `ydotool` для Fedora 44 |
| Перемикання розкладки на Hyprland (регресія) | живий тест: `switched=True`, клавіатура переїхала на `ua` |

| **НЕ перевірено** (потрібен твій Fedora KDE) | Що зробити |
|---|---|
| Реальна вставка через `ydotool` на KWin | `kde-convert --check`, потім виділити слово і натиснути хоткей |
| Реальні виклики `org.kde.keyboard` проти живого KWin | той самий `--check` покаже `kde.layouts`; якщо там `["us","ua"]` — інтерфейс живий |
| Реєстрація хоткеїв через `kwriteconfig6` + перезапуск `kglobalacceld` | System Settings → Keyboard → Shortcuts → Custom: записи мають зʼявитись |
| X11-сеанс Plasma (там розкладку дає kded-модуль) | те саме, API однакове |
| Збірка RPM (`rpmbuild`) | `packaging/README.md`, `%check` там лише конвертер |
| Чи спрацьовує `Ctrl+C`/`Ctrl+V` від `ydotool` у застосунках без «латинських акселераторів» | якщо в якомусь застосунку не працює — напиши, це відоме місце (GTK/Qt це вміють, деякі Electron — ні) |

Якщо `--check` каже `ok: true` — це вже сильний сигнал: усі залежності на місці,
`org.kde.keyboard` відповідає, і розкладки `us`/`ua` налаштовані.

## Чому тут немає авто-режиму (Punto-style)

Це **свідоме рішення**, а не недоробка: на Plasma 6 авто-режим неможливий як порт
цього воркера, і краще мати чесний хоткей, ніж демон із root-правами, який
неможливо перевірити. Ось чому — на Omarchy авто-режим живий, бо Hyprland сам
віддає кожну клавішу (`input.keyboard.key`). У Plasma такого немає ні для
скриптів, ні для звичайних програм:

- KWin scripting уміє лише `registerShortcut` — жодного колбека на клавіші;
  `KWin::InputEventSpy::keyboardKey()` існує тільки як C++ SPI всередині KWin;
- `org.kde.KWin` не має методів для синтезу чи спостереження клавіш (є
  `/Scripting`, але він лише завантажує скрипти; `org.kde.KWin.VirtualKeyboard`
  лише показує екранну клавіатуру; `org_kde_kwin_fake_input` є, але в
  blacklist і доступний тільки через портал);
- справжній API `org.freedesktop.a11y.KeyboardMonitor` у KWin **жорстко
  замкнений на Orca**: `checkPermission()` порівнює імʼя власника шини і
  відмовляє всім іншим («Only screen readers are allowed to use this interface»);
- `fcitx5` міг би це в принципі (через `zwp_input_method`), але готового
  punto-style аддона не існує — це писати повноцінний IME, а не порт;
- `xneur`/`gxneur` — тільки X11.

Тому чесний обсяг цієї версії — хоткей. Якщо авто-режим конче потрібен, єдиний
робочий шлях — стати **під** композитором: `keyd` (тільки з COPR
`alternateved/keyd`, від root) або власний демон на `evdev`+`uinput`. Це окрема
програма з root-правами, а не порт цього воркера — і на машині розробника її
неможливо перевірити, тому вона тут свідомо не написана навмання.

## Обмеження

- **Виділення**: спершу читається `wl-paste --primary` (KWin підтримує і
  data-control, і primary-selection), якщо порожньо — Ctrl+C. PRIMARY порожній,
  коли нічого не виділено — це нормально, не баг KWin.
- **XWayland**-вікна: надійніше виділяти мишею.
- **Розкладка ydotool-пристрою**: ydotool створює власний віртуальний пристрій;
  на wlroots-композиторах йому варто задати розкладку (для Hyprland це
  `device:ydotoold-virtual-device { kb_layout = us }`). На KWin цього не
  потрібно для наших цілей: текст вставляється з буфера, а не набирається.
- Одна розкладка на сеанс — тому `switch_everywhere` для KDE робить те саме, що
  `switch_to` (один виклик `setLayout`).
- Якщо в сеансі увімкнений `fcitx5`/`ibus`, він керує своєю розкладкою окремо
  від KWin: `org.kde.keyboard` перемикає xkb-розкладку KWin, а не стан IM.
  За замовчуванням на Fedora KDE IM не встановлено, тож зазвичай це не заважає.

## Файли

- `bin/kde-convert` — воркер (вибір/рядок/останнє слово; `--check`)
- `lib/` — ядро, байт-у-байт як у `omarchy-plugin/lib` (`langswitcher.py`,
  `switch.py`, `layoutswitch.py` — саме в ньому тепер і Hyprland-, і KDE-бекенд)
- `install.sh` — dnf + файли + сокет ydotoold + хоткеї (`--dry-run`,
  `--no-ydotool`, `--no-shortcuts`)
- `packaging/` — spec і два command-shortcut `.desktop` для RPM
- тести ядра — `linux/tests/`

## Видалення

```sh
rm -rf ~/.local/share/langswitcher-kde ~/.local/bin/kde-convert
rm -f ~/.local/share/applications/net.local.langswitcher-*.desktop
# і, якщо install.sh додавав drop-in:
sudo rm -f /etc/systemd/system/ydotool.service.d/socket-own.conf
sudo systemctl daemon-reload && sudo systemctl restart ydotool
```
