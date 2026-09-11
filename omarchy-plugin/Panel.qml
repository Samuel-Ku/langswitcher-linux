import QtQuick
import qs.Ui
import qs.Commons

// Popup for the LangSwitcher bar widget.
//
// Three convert actions (same worker as the Hyprland hotkeys), dependency
// status, active layouts and the last run. The panel holds no state of its
// own: it renders the service.
Panel {
  id: root
  moduleName: "stealth.langswitcher"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null

  readonly property var service: bar && bar.shell ? bar.shell.serviceFor("stealth.langswitcher") : null
  readonly property bool ready: service ? service.ready : false
  readonly property bool busy: service ? service.busy : false

  readonly property color contentForeground: bar ? bar.barForeground : Color.foreground
  readonly property color dim: Qt.darker(root.contentForeground, 1.5)
  readonly property color faint: Qt.rgba(root.contentForeground.r, root.contentForeground.g,
    root.contentForeground.b, 0.12)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  function open() { root.controller.show(); }
  function close() { root.controller.hide(); }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.hostWidget || root, direction);
    return false;
  }

  function statusText() {
    if (!service) return "Service is loading…";
    if (service.checking) return "Checking dependencies…";
    if (root.ready) return "Ready — wl-clipboard, wtype, python3 OK";
    var miss = service.missing && service.missing.length > 0
      ? service.missing.join(", ")
      : (service.error || "unknown");
    return "Missing: " + miss;
  }

  function lastRunText() {
    var run = service ? service.lastRun : null;
    if (!run) return "No conversions yet — select text and press SUPER+GRAVE";
    var when = Qt.formatTime(new Date(run.at), "HH:mm:ss");
    return run.mode + (run.ok ? " — converted" : " — no wrong layout found") + " (" + when + ")";
  }

  component SectionTitle: Text {
    width: parent ? parent.width : 0
    color: root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    font.bold: true
    font.letterSpacing: 1.2
  }

  component Note: Text {
    width: parent ? parent.width : 0
    color: root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.bodySmall
    wrapMode: Text.WordWrap
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(330))
    contentHeight: panel.fittedContentHeight(content.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction); }

      Column {
        id: content
        width: parent.width
        spacing: Style.space(10)

        Column {
          width: parent.width
          spacing: Style.space(2)

          Text {
            width: parent.width
            text: "LangSwitcher"
            color: root.contentForeground
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            font.bold: true
          }

          Note {
            text: "Fix text typed in the wrong keyboard layout — a port of macOS LangSwitcher."
          }
        }

        SectionTitle { text: "CONVERT" }

        Column {
          width: parent.width
          spacing: Style.space(6)

          Button {
            width: parent.width
            text: root.busy ? "Converting…" : "Convert selection"
            tooltipText: "Convert the selected text (SUPER+GRAVE)"
            enabled: root.ready && !root.busy
            onClicked: if (root.service) root.service.convert("selection")
          }

          Button {
            width: parent.width
            text: root.busy ? "Converting…" : "Convert line (greedy)"
            tooltipText: "Take the line before the cursor, find where the wrong layout starts (SUPER+SHIFT+GRAVE)"
            enabled: root.ready && !root.busy
            onClicked: if (root.service) root.service.convert("greedy")
          }

          Button {
            width: parent.width
            text: root.busy ? "Converting…" : "Convert last word"
            tooltipText: "Convert the word left of the cursor"
            enabled: root.ready && !root.busy
            onClicked: if (root.service) root.service.convert("last-word")
          }
        }

        SectionTitle { text: "STATUS" }

        Note { text: "Layouts: " + (root.service ? root.service.layouts : "…") }
        Note { text: root.statusText() }
        Note {
          visible: !root.ready && root.service && !root.service.checking
          text: "Install: sudo pacman -S --needed wl-clipboard wtype"
        }
        Note { text: root.lastRunText() }

        SectionTitle { text: "HOTKEYS" }

        Note {
          text: "SUPER+GRAVE converts selection, SUPER+SHIFT+GRAVE converts the line. "
            + "Add both lines from bindings.snippet.lua to ~/.config/hypr/bindings.lua "
            + "(Wayland cannot catch double-Shift like macOS does)."
        }
      }
    }
  }
}
