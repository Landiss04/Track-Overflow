// Window for the CTC Office test UI, a separate process started with
// ctc_ui/test_ui.py. Sizing and scaling come from the shared
// ui/ScaledWindow.qml; test_ui.py installs the matching aspect lock.
// `harness` is the CtcTestHarness context property set by test_ui.py.
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
        onSendInputsRequested: harness.send()
        onResetInputsRequested: harness.resetInputs()
    }
}
