// Window for the CTC Office test UI, a separate process started with
// ctc_ui/test_ui.py. Sizing and scaling come from the shared
// ui/ScaledWindow.qml; test_ui.py installs the matching aspect lock.
// `harness` is the CtcTestHarness context property set by test_ui.py, and
// `ctcClock` the ClockLinkClient that controls the running CTC Office's
// simulation clock.
import QtQuick
import "../../../../ui"

ScaledWindow {
    title: qsTr("CTC Office — Test harness")

    TestHarnessView {
        anchors.fill: parent
        inputs: harness.inputs
        dispatcherInputs: harness.dispatcherInputs
        outputs: harness.outputs
        connected: harness.connected
        status: harness.status
        statusIsError: harness.statusIsError
        onInputEdited: function (name, value) {
            harness.setInput(name, value);
        }
        lineNames: harness.lineNames
        layoutOptions: harness.layoutOptions
        onEntryAddRequested: function (name) { harness.addEntry(name); }
        onEntryRemoveRequested: function (name, index) {
            harness.removeEntry(name, index);
        }
        onEntryFieldEdited: function (name, index, key, value) {
            harness.setEntryField(name, index, key, value);
        }
        onSendInputsRequested: harness.send()
        onInputChoiceEdited: function (name, choice) {
            harness.setInputChoice(name, choice);
        }
        onResetInputsRequested: harness.resetInputs()
        clockConnected: ctcClock.connected
        clockTime: ctcClock.timeText
        clockPaused: ctcClock.paused
        clockSpeed: ctcClock.speed
        onClockPauseRequested: ctcClock.pause()
        onClockResumeRequested: ctcClock.resume()
        onClockSpeedRequested: function (speed) { ctcClock.setSpeed(speed); }
    }
}
