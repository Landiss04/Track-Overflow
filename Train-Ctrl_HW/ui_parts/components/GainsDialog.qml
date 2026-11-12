// Engineer-only, and one-shot: the gains are commissioned once at
// start-up and frozen for the run. Opening and closing is state, not a
// call: the dialog is up exactly while the engineer is signed in, and
// the backend hands the console back to the driver once the gains are
// committed.
//
// Drawn as an overlay inside the scaled canvas rather than as a Popup,
// which would float at 1:1 over a scaled console.
import QtQuick
import QtQuick.Layouts
import "../../../ui"

Item {
    id: root

    readonly property var s: controller.snapshot

    function bumped(text, delta) {
        const value = Number(text);
        return String(Math.max(0, (isFinite(value) ? value : 0) + delta));
    }

    visible: s.operator === "engineer"

    Rectangle {
        anchors.fill: parent
        color: theme.text_primary
        opacity: 0.45

        // Swallow presses meant for the console behind the dialog.
        MouseArea { anchors.fill: parent }
    }

    Card {
        anchors.centerIn: parent
        width: 420
        title: qsTr("Control gains")

        HelperText {
            Layout.fillWidth: true
            text: qsTr("Set once at start-up. They cannot be changed "
                       + "afterwards.")
        }

        FormField {
            Layout.fillWidth: true
            label: qsTr("Proportional gain, Kp")

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                AppButton {
                    text: "\u2212"
                    onClicked: kp.text = root.bumped(kp.text, -2500)
                }

                ValueField {
                    id: kp
                    Layout.fillWidth: true
                    kind: "float"
                }

                AppButton {
                    text: "+"
                    onClicked: kp.text = root.bumped(kp.text, 2500)
                }
            }
        }

        FormField {
            Layout.fillWidth: true
            label: qsTr("Integral gain, Ki")

            RowLayout {
                Layout.fillWidth: true
                spacing: theme.space_2

                AppButton {
                    text: "\u2212"
                    onClicked: ki.text = root.bumped(ki.text, -500)
                }

                ValueField {
                    id: ki
                    Layout.fillWidth: true
                    kind: "float"
                }

                AppButton {
                    text: "+"
                    onClicked: ki.text = root.bumped(ki.text, 500)
                }
            }
        }

        Callout {
            Layout.fillWidth: true
            variant: "info"
            heading: qsTr("Braking is separate")
            body: qsTr("Gains change how quickly the train reaches its "
                       + "target speed. The brake path is independent, so "
                       + "they can never change whether it stops.")
        }

        // Whether the gains took, in the dialog itself, the moment the
        // train confirms them: the bar's badge is hidden behind this
        // dialog until it closes. Always laid out, a badge over one
        // line in every state, so the buttons never move when the
        // state changes.
        ColumnLayout {
            objectName: "gainsStatus"
            Layout.fillWidth: true
            spacing: theme.space_2

            StatusBadge {
                label: !root.s.has_train ? qsTr("No train")
                    : root.s.gains_locked ? qsTr("Gains set")
                    : root.s.gains_pending ? qsTr("Setting")
                    : qsTr("Not set")
                variant: root.s.gains_locked ? "ok"
                    : root.s.gains_pending ? "info"
                    : root.s.has_train && root.s.gains_note !== ""
                        ? "warning" : "idle"
            }

            HelperText {
                Layout.fillWidth: true
                wrapMode: Text.NoWrap
                elide: Text.ElideRight
                text: !root.s.has_train
                    ? qsTr("Waiting for a train to join.")
                    : root.s.gains_pending
                    ? qsTr("Sending them to %1…").arg(root.s.train_id)
                    : root.s.gains_note !== "" ? root.s.gains_note
                    : qsTr("Not sent yet.")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.space_2

            AppButton {
                variant: "ghost"
                text: qsTr("Back to driver")
                onClicked: controller.select_operator(0)
            }

            AppButton {
                objectName: "setGains"
                Layout.fillWidth: true
                variant: "primary"
                size: "large"
                text: root.s.gains_locked ? qsTr("Gains set")
                    : root.s.gains_pending ? qsTr("Setting gains…")
                    : qsTr("Set gains")
                enabled: root.s.has_train && !root.s.gains_locked
                    && !root.s.gains_pending && kp.valid && ki.valid
                onClicked: controller.commission_gains(Number(kp.text),
                                                      Number(ki.text))
            }
        }

        // Seeded once, not bound: a binding to the snapshot would
        // rewrite the fields underneath the engineer as they type.
        Component.onCompleted: {
            kp.text = String(Math.round(controller.snapshot.kp));
            ki.text = String(Math.round(controller.snapshot.ki));
        }
    }
}
