import QtQuick
import Quickshell.Io
import qs.Ui
import qs.Commons

// Bar widget: a keyboard glyph whose colour answers "can I convert?".
// Accent = ready, amber = last run found no wrong layout, urgent = missing
// dependencies.
//
// Which button does what is a per-widget setting, so nobody has to accept this
// plugin's idea of a left click:
//   {"id": "stealth.langswitcher", "leftClick": "line", "rightClick": "panel"}
//   omarchy bar set stealth.langswitcher leftClick line
// Values: selection (default for left and middle), line, word, panel (default
// for right). The worker's own mode names (greedy, last-word) are aliases.
BarWidget {
  id: root
  moduleName: "stealth.langswitcher"

  readonly property var service: bar && bar.shell ? bar.shell.serviceFor("stealth.langswitcher") : null
  readonly property bool ready: service ? service.ready : false
  readonly property var lastRun: service ? service.lastRun : null
  // Nerd Font Material Design "keyboard" glyph.
  readonly property string glyph: String.fromCodePoint(0xF030C)

  readonly property color idleColor: bar ? bar.barForeground : Color.foreground

  readonly property color statusColor: {
    if (!service || !root.ready) return Color.urgent
    if (service.error !== "") return Color.urgent
    if (root.lastRun && root.lastRun.ok === false) return "#e0b341"
    return Color.accent
  }

  readonly property string tooltip: {
    if (!service) return "LangSwitcher is loading"
    if (!root.ready) {
      var miss = service.missing && service.missing.length > 0
        ? service.missing.join(", ")
        : "unknown";
      return "LangSwitcher: missing " + miss
        + "\nsudo pacman -S --needed wl-clipboard wtype";
    }
    var lines = ["LangSwitcher (" + service.layouts + ")",
      "Click: " + root.actionLabel(root.leftAction)];
    if (root.middleAction !== root.leftAction)
      lines.push("Middle: " + root.actionLabel(root.middleAction));
    lines.push("Right: " + root.actionLabel(root.rightAction));
    lines.push("SUPER+GRAVE · SUPER+SHIFT+GRAVE");
    if (root.lastRun) lines.push(service.lastRunText());
    return lines.join("\n");
  }

  // ---- click actions -------------------------------------------------------
  // Resolved once per configuration change, not per click: the tooltip and the
  // handlers then cannot disagree about what a button does.
  readonly property string leftAction: root.actionFor(root.setting("leftClick", "selection"), "selection")
  readonly property string middleAction: root.actionFor(root.setting("middleClick", "selection"), "selection")
  readonly property string rightAction: root.actionFor(root.setting("rightClick", "panel"), "panel")

  readonly property var actionLabels: ({
    selection: "converts the selection",
    line: "converts the line",
    word: "converts the last word",
    panel: "opens the panel"
  })

  function actionLabel(action) { return root.actionLabels[action] || action; }

  function isClickAction(value) {
    var v = String(value === undefined || value === null ? "" : value).toLowerCase();
    return v === "selection" || v === "select"
      || v === "line" || v === "greedy"
      || v === "word" || v === "last-word" || v === "lastword"
      || v === "panel" || v === "menu";
  }

  // One write path for the click mapping, used by the panel's dropdowns and by
  // the setClickAction IPC. The local echo applies instantly (so the tooltip and
  // the panel update on the click itself); shell.json is written through the
  // shell's own API, which is what survives a restart.
  function setClickAction(button, action) {
    if (button !== "left" && button !== "middle" && button !== "right") return false
    if (!root.isClickAction(action)) return false

    var entry = { id: root.moduleName }
    for (var key in root.settings) if (key !== "id") entry[key] = root.settings[key]
    // Store the canonical name, so shell.json always carries what the code and
    // the docs call it, even when the caller passed an alias.
    entry[button + "Click"] = root.actionFor(action, "selection")
    root.settings = entry

    if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
      root.bar.shell.updateEntryInline(root.moduleName, entry)
    return true
  }

  // A mistyped value falls back to that button's default rather than leaving
  // the click doing nothing.
  function actionFor(value, fallback) {
    var v = String(value === undefined || value === null ? "" : value).toLowerCase();
    if (v === "selection" || v === "select") return "selection"
    if (v === "line" || v === "greedy") return "line"
    if (v === "word" || v === "last-word" || v === "lastword") return "word"
    if (v === "panel" || v === "menu") return "panel"
    return fallback;
  }

  // The panel is only opened explicitly: it is a keyboard-interactive layer
  // surface, so when a button converts instead, nothing opens and the keys go
  // straight to the app being edited.
  function runAction(action) {
    if (!root.service) return
    if (action === "panel") { root.togglePanel(); return }
    if (action === "line") { root.service.convert("greedy"); return }
    if (action === "word") { root.service.convert("last-word"); return }
    root.service.convert("selection");
  }

  // ---- Panel shape contract for the shell's summon/hide/toggle routing ----
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function open() { if (panelLoader.item) panelLoader.item.open(); }
  function close() { if (panelLoader.item) panelLoader.item.close(); }
  function togglePanel() { if (panelLoader.item) panelLoader.item.toggle(); }

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch();
  }

  function injectPanel() {
    var target = panelLoader.item;
    if (!target) return;
    if ("bar" in target) target.bar = root.bar;
    if ("settings" in target) target.settings = root.settings;
    if ("anchorItem" in target) target.anchorItem = button;
    if ("hostWidget" in target) target.hostWidget = root;
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel();
      Qt.callLater(root.injectPanel);
    }
  }

  IpcHandler {
    target: "stealth.langswitcher"

    function status(): string {
      return root.service
        ? JSON.stringify(root.service.statusObject(), null, 2)
        : "LangSwitcher service is not running";
    }

    function statusJson(): string {
      return root.service
        ? JSON.stringify(root.service.statusObject(), null, 2)
        : JSON.stringify({ id: "stealth.langswitcher", error: "service_unavailable" }, null, 2);
    }

    function convertSelection(): string {
      if (!root.service) return "service_unavailable";
      return root.service.convert("selection") ? "ok" : "busy";
    }

    function convertLine(): string {
      if (!root.service) return "service_unavailable";
      return root.service.convert("greedy") ? "ok" : "busy";
    }

    function convertLastWord(): string {
      if (!root.service) return "service_unavailable";
      return root.service.convert("last-word") ? "ok" : "busy";
    }

    // What the three buttons will do, so a settings change can be checked
    // without clicking: omarchy-shell stealth.langswitcher clickActions
    function clickActions(): string {
      return JSON.stringify({
        left: root.leftAction,
        middle: root.middleAction,
        right: root.rightAction
      });
    }

    // omarchy-shell stealth.langswitcher setClickAction left line
    function setClickAction(button: string, action: string): string {
      return root.setClickAction(button, action) ? "ok" : "failed";
    }

    function open(): void { root.open(); }
    function close(): void { root.close(); }
    function show(): void { root.open(); }
    function hide(): void { root.close(); }
    function toggle(): void { root.togglePanel(); }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.glyph
    hasVisualContent: true
    foreground: root.statusColor
    tooltipText: root.tooltip
    onPressed: function(b) {
      if (b === Qt.RightButton) root.runAction(root.rightAction);
      else if (b === Qt.MiddleButton) root.runAction(root.middleAction);
      else root.runAction(root.leftAction);
    }
  }
}
