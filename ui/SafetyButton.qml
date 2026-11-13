// Safety-critical control, style guide 7. Minimum 44 px by 200 px, --danger
// fill, uppercase label with 0.05em tracking, and an explicit confirmation
// step. Only the Train Controller emergency brake is unconfirmed, so the
// Train Model's passenger brake confirms.
import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string label: ""
    property string releaseLabel: "Release emergency brake"
    property bool applied: false         // engaged state: shows the darker
                                         // release control instead of apply
    property string confirmLabel: "Confirm"
    property string cancelLabel: "Cancel"
    property string tooltip: ""          // optional hover text (native ToolTip)
    // Set false only for the Train Controller emergency brake (guide 7).
    property bool confirmationRequired: true
    signal confirmed()

    property bool armed: false
    onAppliedChanged: armed = false
    onEnabledChanged: if (!enabled) armed = false
    onVisibleChanged: if (!visible) armed = false
    // Disarm when focus leaves the prompt, so a later stray click cannot
    // confirm a prompt nobody is looking at.
    readonly property bool promptFocused: confirmButton.activeFocus
        || cancelButton.activeFocus
    onPromptFocusedChanged: if (!promptFocused) armed = false

    implicitHeight: theme.safety_min_height
    // Fit the longer of the apply and release labels, so the control does
    // not change width when it is applied or released.
    implicitWidth: Math.max(theme.safety_min_width, row.implicitWidth,
        Math.ceil(Math.max(applyMetrics.advanceWidth, releaseMetrics.advanceWidth))
            + 2 * applyButton.hPadding)

    TextMetrics {
        id: applyMetrics
        font: (applyButton.contentItem as Text).font
        text: root.label.toUpperCase()
    }

    TextMetrics {
        id: releaseMetrics
        font: (applyButton.contentItem as Text).font
        text: root.releaseLabel.toUpperCase()
    }

    AppButton {
        id: applyButton
        anchors.fill: parent
        visible: !root.armed
        variant: "danger"
        active: root.applied
        size: "large"
        text: (root.applied ? root.releaseLabel : root.label).toUpperCase()
        tooltip: root.tooltip
        font.letterSpacing: theme.safety_letter_spacing
        onClicked: {
            if (root.confirmationRequired) {
                root.armed = true;
                confirmButton.forceActiveFocus();
            } else {
                root.confirmed();
            }
        }
    }

    RowLayout {
        id: row
        anchors.fill: parent
        visible: root.armed
        spacing: theme.space_3

        AppButton {
            id: confirmButton
            Layout.fillWidth: true
            Layout.fillHeight: true
            variant: "danger"
            size: "large"
            text: root.confirmLabel.toUpperCase()
            font.letterSpacing: theme.safety_letter_spacing
            onClicked: {
                root.armed = false;
                root.confirmed();
            }
        }

        AppButton {
            id: cancelButton
            Layout.fillHeight: true
            variant: "ghost"
            size: "large"
            text: root.cancelLabel
            onClicked: root.armed = false
        }
    }
}
