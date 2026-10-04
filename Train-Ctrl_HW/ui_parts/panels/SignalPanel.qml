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

    SignalHead {
        Layout.alignment: Qt.AlignHCenter
        Layout.fillHeight: true
        Layout.preferredWidth: 92
        aspectIndex: root.s.signal_index
    }

    Text {
        Layout.fillWidth: true
        horizontalAlignment: Text.AlignHCenter
        text: root.s.next_signal
        color: theme.text_primary
        font.family: theme.mono_family
        font.pixelSize: theme.size_h2
        font.weight: theme.weight_bold
    }

    HelperText {
        Layout.fillWidth: true
        Layout.preferredHeight: 34
        horizontalAlignment: Text.AlignHCenter
        text: root.s.signal_text
    }
}