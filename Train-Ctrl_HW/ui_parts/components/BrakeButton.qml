// Brake control, guide 7: at least 44 by 200, uppercase with 0.05em
// tracking, and no confirmation step. Neither brake confirms here —
// the emergency brake is the exception the guide names, and the
// service brake is a routine stop a driver makes at every station.
//
// A shared AppButton underneath, so hover, press, disabled and focus
// behave like every other button. Two things differ and are why this
// is not SafetyButton: the label wraps instead of eliding, because
// "Release emergency brake" does not fit a quarter of the canvas on
// one line, and the service brake is amber rather than red.
import QtQuick
import "../../../ui"

AppButton {
    id: button

    property bool applied: false
    property string releaseLabel: ""
    // emergency | service
    property string tone: "emergency"

    readonly property bool amber: tone === "service"
    readonly property color face: amber ? theme.brake_service : theme.danger
    readonly property color faceActive: amber ? theme.brake_service_active
                                              : theme.danger_active
    readonly property color ink: amber ? theme.text_primary
                                       : theme.text_inverse

    size: "large"
    implicitHeight: theme.safety_min_height
    implicitWidth: theme.safety_min_width
    Accessible.name: text

    background: Rectangle {
        radius: theme.radius_md
        color: button.pressed ? button.faceActive
            : button.hovered ? button.faceActive
            : button.applied ? button.faceActive : button.face
        border.width: button.applied ? 3 : 0
        border.color: button.ink

        Rectangle {
            anchors.fill: parent
            anchors.margins: -4
            visible: button.visualFocus
            color: "transparent"
            radius: theme.radius_md + 4
            border.width: 2
            border.color: theme.focus_ring
        }
    }

    contentItem: Text {
        text: button.text.toUpperCase()
        color: button.ink
        font.family: theme.ui_family
        font.pixelSize: theme.size_h3
        font.weight: theme.weight_bold
        font.letterSpacing: theme.safety_letter_spacing
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
