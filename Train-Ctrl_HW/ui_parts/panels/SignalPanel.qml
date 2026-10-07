// The aspect the driver is running towards. The lamp position, the word
// and the sentence all carry the state, so colour is never carrying it
// alone (guide 2 and 8).
import QtQuick
import QtQuick.Layouts
import "../../../ui"
import "../components"

Panel {
    id: root

    readonly property var s: controller.snapshot

    title: qsTr("Next signal")

    // Signal pickup failure: the track signal cannot be read, so the
    // aspect is unknown and the controller stops the train.
    Callout {
        Layout.fillWidth: true
        visible: root.s.fault_pickup
        variant: "warning"
        heading: qsTr("Signal pickup failure")
        body: qsTr("Speed and authority cannot be read. The train is "
                   + "being stopped.")
    }

    SignalHead {
        Layout.alignment: Qt.AlignHCenter
        Layout.fillHeight: true
        Layout.preferredWidth: 92
        aspectIndex: root.s.fault_pickup ? -1 : root.s.signal_index
    }

    Text {
        Layout.fillWidth: true
        horizontalAlignment: Text.AlignHCenter
        text: root.s.fault_pickup ? qsTr("UNKNOWN") : root.s.next_signal
        color: theme.text_primary
        font.family: theme.mono_family
        font.pixelSize: theme.size_h2
        font.weight: theme.weight_bold
    }

    // Two lines of room while there is a sentence to show; none while
    // pickup has failed, so the head gets the space the notice took.
    HelperText {
        Layout.fillWidth: true
        Layout.preferredHeight: text === "" ? 0 : 34
        horizontalAlignment: Text.AlignHCenter
        text: root.s.fault_pickup ? "" : root.s.signal_text
    }
}