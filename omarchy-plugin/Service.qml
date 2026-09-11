import QtQuick
import Quickshell
import Quickshell.Io

// Headless service: the single place that knows the converter.
//
// bin/langswitcher-convert does the Wayland work (wl-paste -> lib/switch.py
// -> wl-copy -> wtype Ctrl+V). This file only checks dependencies at startup
// and exposes convert() + status, so the bar widget and the panel share one
// implementation and one "last run" record.
//
// Privacy: clipboard plain text never enters QML properties — only the mode,
// exit code and timestamp of the last run.
Item {
  id: root

  // Injected by omarchy-shell's generic service loader.
  property var shell: null

  readonly property string pluginId: "stealth.langswitcher"

  // Absolute path to the helper, derived from this file's own location,
  // so it works both in the repo checkout and in ~/.config/omarchy/plugins/.
  readonly property string binPath:
    Qt.resolvedUrl("bin/langswitcher-convert").toString().replace(/^file:\/\//, "")

  // Candidate layouts, same values as lib/switch.py --layouts.
  // The Hyprland binds carry their own --layouts flag; this is the default
  // used by the panel buttons and IPC.
  property string layouts: "en,uk,pl"

  property bool checking: true
  property bool ready: false
  property var missing: []
  property string error: ""

  // One conversion at a time; hotkey presses are discrete, this is only
  // a guard against double-firing.
  property bool busy: false
  // Last run record: { mode: string, ok: bool, code: int, at: double }.
  property var lastRun: null

  function check() {
    if (checkProc.running) return
    root.checking = true
    checkProc.command = [root.binPath, "--check"]
    checkProc.running = true
    watchdog.restart()
  }

  // mode: "selection" | "greedy" | "last-word". Returns false if a run is
  // already in flight.
  function convert(mode) {
    if (root.busy) return false
    if (mode !== "selection" && mode !== "greedy" && mode !== "last-word") return false
    root.busy = true
    convertProc.mode = mode
    convertProc.exitCode = -99
    convertProc.command = [root.binPath, mode, "--layouts", root.layouts]
    convertProc.running = true
    watchdog.restart()
    return true
  }

  function statusObject() {
    return {
      id: root.pluginId,
      ready: root.ready,
      checking: root.checking,
      busy: root.busy,
      layouts: root.layouts,
      missing: root.missing,
      error: root.error,
      lastRun: root.lastRun
    }
  }

  Process {
    id: checkProc
    property string output: ""
    stdout: StdioCollector {
      onStreamFinished: checkProc.output = String(text || "")
    }
    onExited: function(code) {
      watchdog.stop()
      root.checking = false
      if (code !== 0) {
        root.ready = false
        root.error = "check_failed"
        return
      }
      try {
        var doc = JSON.parse(checkProc.output || "{}")
        root.missing = Array.isArray(doc.missing) ? doc.missing : []
        root.ready = doc.ok === true
        root.error = doc.ok === true ? "" : "missing_deps"
      } catch (e) {
        root.ready = false
        root.error = "invalid_response"
      }
    }
  }

  Process {
    id: convertProc
    property int exitCode: -99
    property string mode: ""
    onExited: function(code) {
      watchdog.stop()
      convertProc.exitCode = code
      // Exit 0 = converted, 2 = nothing that looks like a wrong layout
      // (not an error — the user just pressed the hotkey on normal text).
      root.lastRun = {
        mode: convertProc.mode,
        ok: code === 0,
        code: code,
        at: Date.now()
      }
      root.busy = false
    }
  }

  Timer {
    id: watchdog
    interval: 15000
    repeat: false
    onTriggered: {
      checkProc.running = false
      convertProc.running = false
      root.checking = false
      root.busy = false
      if (!root.ready) root.error = "timeout"
    }
  }

  Component.onCompleted: root.check()
}
