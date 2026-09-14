-- LangSwitcher (omarchy plugin stealth.langswitcher).
-- Додай ці рядки в ~/.config/hypr/bindings.lua, потім hyprctl reload.
-- Виділи текст -> хоткей -> текст заміниться конвертованим (EN/UK/PL).
-- Подвійний Shift як на macOS під Wayland не зловити, тому SUPER+GRAVE.
o.bind("SUPER + GRAVE", "LangSwitcher: конвертувати виділення", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-convert selection")
o.bind("SUPER + SHIFT + GRAVE", "LangSwitcher: конвертувати рядок (greedy)", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-convert greedy")
-- Авто-режим (потрібен require("hypr.langswitcher-auto")): скасувати останнє
-- авто-виправлення — текст і мова повертаються, а слово потрапляє у словник,
-- тож більше не конвертується. Працює до 2 хв і поки не змінилось вікно.
o.bind("SUPER + BACKSPACE", "LangSwitcher: скасувати останнє авто-виправлення", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-auto --undo")
