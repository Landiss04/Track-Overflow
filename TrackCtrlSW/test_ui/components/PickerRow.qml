// A labelled drop-down. The model is a stable list of strings; the
// current choice lives in the control, so the once-a-second snapshot
// never moves it.
//
// ``mirror`` is for pickers that must follow something outside the
// test UI, such as the line the programmer has selected: while it is
// zero or more the control tracks it, and a click still sends its
// signal first, so the two agree again as soon as the controller
// confirms.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../ui/components"

RowLayout {
    id: root

    property string label: ""
    property alias model: box.model
    property alias currentIndex: box.currentIndex
    property alias currentText: box.currentText
    property int mirror: -1
    property int labelWidth: 120
    readonly property int index: box.currentIndex
    signal picked(int index)

    spacing: theme.space_3

    FieldLabel {
        text: root.label
        visible: root.label !== ""
        Layout.preferredWidth: root.labelWidth
    }

    ComboBox {
        id: box
        Layout.fillWidth: true
        implicitHeight: theme.control_h_md
        enabled: root.enabled
        opacity: enabled ? 1.0 : 0.42
        font.family: theme.mono_family
        font.pixelSize: theme.size_small
        onActivated: function (index) { root.picked(index); }
    }

    Binding {
        target: box
        property: "currentIndex"
        value: root.mirror
        when: root.mirror >= 0
    }
}
