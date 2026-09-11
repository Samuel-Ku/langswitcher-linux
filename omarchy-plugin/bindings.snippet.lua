-- LangSwitcher (omarchy plugin stealth.langswitcher).
-- Додай ці два рядки в ~/.config/hypr/bindings.lua, потім hyprctl reload.
-- Виділи текст -> хоткей -> текст заміниться конвертованим (EN/UK/PL).
-- Подвійний Shift як на macOS під Wayland не зловити, тому SUPER+GRAVE.
o.bind("SUPER + GRAVE", "LangSwitcher: конвертувати виділення", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-convert selection")
o.bind("SUPER + SHIFT + GRAVE", "LangSwitcher: конвертувати рядок (greedy)", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-convert greedy")
