import QtQuick
import qs.Ui
import qs.Commons

// Popup for the LangSwitcher bar widget.
//
// Three convert actions (same worker as the Hyprland hotkeys), the click
// mapping, dependency status, active layouts and the last run. The panel holds
// no state of its own: it renders the service, and it edits the widget's own
// settings through the widget.
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
    if (!service) return "loading…";
    if (service.checking) return "checking…";
    if (root.ready) return "ready";
    var miss = service.missing && service.missing.length > 0
      ? service.missing.join(", ")
      : (service.error || "unknown");
    return "missing: " + miss;
  }

  function lastRunText() {
    if (!service || !service.lastRun) return "no conversions yet";
    return service.lastRunText();
  }

  // ---- click mapping -------------------------------------------------------
  //
  // Which button converts and which opens this panel is the widget's setting
  // (it is the thing being clicked), so the panel only renders it and writes
  // back through the widget — one write path, so a change made here and a
  // change made with `omarchy bar set` cannot drift apart. `hostWidget` is
  // injected by the widget's injectPanel(); the fallbacks keep the panel usable
  // if it is ever opened without one.
  readonly property var host: root.hostWidget
  readonly property string leftAction: host ? host.leftAction : "selection"
  readonly property string middleAction: host ? host.middleAction : "selection"
  readonly property string rightAction: host ? host.rightAction : "panel"

  readonly property var clickOptions: [
    { value: "selection", label: "Convert selection" },
    { value: "line", label: "Convert line (greedy)" },
    { value: "word", label: "Convert last word" },
    { value: "panel", label: "Open this panel" }
  ]

  function applyClickAction(button, action) {
    if (!host || typeof host.setClickAction !== "function") return;
    host.setClickAction(button, action);
  }

  // ---- panel actions -------------------------------------------------------
  //
  // This panel is a keyboard-interactive layer surface, so while it is open the
  // compositor delivers keys to the shell — including the worker's Ctrl+C (copy
  // the selection) and Ctrl+V (paste the result). A conversion started from a
  // panel button would then paste into the shell instead of the app being
  // edited, and the user would see nothing change. Every action therefore
  // closes the panel first and runs the worker once the surface is gone and the
  // app has the keyboard back, which is exactly what the hotkey path relies on.
  property string pendingMode: ""

  function convertAndClose(mode) {
    if (!service || !root.ready || root.busy) return
    root.pendingMode = mode
    root.close()
    handoff.restart()
  }

  Timer {
    id: handoff
    interval: 60
    repeat: true
    property int ticks: 0
    onTriggered: {
      ticks += 1
      // KeyboardPanel releases keyboard focus the moment it closes but keeps
      // its surface mapped through the fade-out, so wait for the window to go
      // away — bounded, so a stuck surface can never swallow the conversion.
      if (panel.backingWindowVisible && ticks < 20) return
      stop()
      ticks = 0
      var mode = root.pendingMode
      root.pendingMode = ""
      if (root.service && mode !== "") root.service.convert(mode)
    }
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
      // A dropdown owns the keyboard while its popup is open: suspend the
      // panel's own key model so j/k does not drive both at once.
      blocked: leftClick.popupOpen || middleClick.popupOpen || rightClick.popupOpen
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction); }

      Column {
        id: content
        width: parent.width
        spacing: Style.space(10)

        Text {
          width: parent.width
          text: "LangSwitcher"
          color: root.contentForeground
          font.family: root.fontFamily
          font.pixelSize: Style.font.heading
          font.bold: true
        }

        SectionTitle { text: "CONVERT" }

        Column {
          width: parent.width
          spacing: Style.space(6)

          Button {
            width: parent.width
            text: root.busy ? "Converting…" : "Convert selection"
            tooltipText: "Convert the selection (SUPER+GRAVE)"
            enabled: root.ready && !root.busy
            onClicked: root.convertAndClose("selection")
          }

          Button {
            width: parent.width
            text: root.busy ? "Converting…" : "Convert line (greedy)"
            tooltipText: "Convert the line left of the cursor (SUPER+SHIFT+GRAVE)"
            enabled: root.ready && !root.busy
            onClicked: root.convertAndClose("greedy")
          }

          Button {
            width: parent.width
            text: root.busy ? "Converting…" : "Convert last word"
            tooltipText: "Convert the word left of the cursor"
            enabled: root.ready && !root.busy
            onClicked: root.convertAndClose("last-word")
          }
        }

        SectionTitle { text: "CLICK ACTIONS" }

        Column {
          width: parent.width
          spacing: Style.space(6)

          Dropdown {
            id: leftClick
            width: parent.width
            label: "Left click"
            fontFamily: root.fontFamily
            options: root.clickOptions
            value: root.leftAction
            onChanged: function(v) { root.applyClickAction("left", v) }
          }

          Dropdown {
            id: middleClick
            width: parent.width
            label: "Middle click"
            fontFamily: root.fontFamily
            options: root.clickOptions
            value: root.middleAction
            onChanged: function(v) { root.applyClickAction("middle", v) }
          }

          Dropdown {
            id: rightClick
            width: parent.width
            label: "Right click"
            fontFamily: root.fontFamily
            options: root.clickOptions
            value: root.rightAction
            onChanged: function(v) { root.applyClickAction("right", v) }
          }
        }

        SectionTitle { text: "STATUS" }

        Note {
          text: (root.service ? root.service.layouts : "…") + " · " + root.statusText()
        }
        Note {
          visible: !root.ready && root.service && !root.service.checking
          text: "sudo pacman -S --needed wl-clipboard wtype"
        }
        Note { text: root.lastRunText() }
      }
    }
  }
}
