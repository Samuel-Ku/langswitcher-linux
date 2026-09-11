import QtQuick
import Quickshell.Io
import qs.Ui
import qs.Commons

// Bar widget: a keyboard glyph whose colour answers "can I convert?".
// Accent = ready, amber = last run found no wrong layout, urgent = missing
// dependencies. Left click opens the panel, middle click converts the current
// selection immediately (same as the SUPER+GRAVE hotkey).
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
      return "LangSwitcher: missing dependencies\n" + miss
        + "\nInstall: sudo pacman -S --needed wl-clipboard wtype";
    }
    var lines = ["LangSwitcher (" + service.layouts + ")",
      "SUPER+GRAVE converts selection",
      "SUPER+SHIFT+GRAVE converts line"];
    if (root.lastRun) {
      var when = Qt.formatTime(new Date(root.lastRun.at), "HH:mm:ss");
      lines.push("Last run: " + root.lastRun.mode + (root.lastRun.ok ? " — converted" : " — no wrong layout") + " (" + when + ")");
    }
    return lines.join("\n");
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
      if (b === Qt.MiddleButton) {
        if (root.service) root.service.convert("selection");
        return;
      }
      root.togglePanel();
    }
  }
}
