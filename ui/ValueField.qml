// Labeled input with typed commits; validation never sends partial numbers.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string label: ""
<<<<<<< HEAD
    // Clear where the surrounding row already names the field; the label
    // is still used as the accessible name.
    property bool labelVisible: true
    property string kind: "string" // int | float | string
    property alias text: editor.text
    // Host value to show. Bind this instead of text when the host can change
    // the value while the user types: a new host value replaces the text only
    // when the field holds no unsent edit, so typing is never overwritten.
    // Escape drops the edit and shows the host value again.
    property var modelValue: undefined
    function showModelValue() {
        if (modelValue === undefined)
            return;
        editor.text = modelValue === null ? "" : String(modelValue);
        editor.dirty = false;
    }
    onModelValueChanged: if (!editor.dirty) showModelValue()
    Component.onCompleted: showModelValue()
    readonly property bool valid: kind === "string"
        || (editor.acceptableInput && (kind !== "int" || isWholeNumber(editor.text)))
    // An untouched empty field is not an error yet: the error appears once
    // the field holds text or the user has edited it. A refused keystroke
    // or paste is shown too, so a rejection is never silent.
    readonly property bool showError: editor.rejectedInput !== ""
        || (!valid && (editor.text !== "" || editor.userEdited))
    // Lowest accepted number. At 0 or above a typed minus sign is refused.
    property real minimum: -Infinity
    property string errorMessage: kind === "int"
        ? (minimum >= 0 ? qsTr("Enter a whole number, 0 or more.")
            : qsTr("Enter a whole number."))
        : (minimum >= 0 ? qsTr("Enter a number, 0 or more.")
            : qsTr("Enter a number."))
    signal committed(var value)

    // An IntValidator silently drops a typed decimal point ("2.5" -> "25"),
    // so int fields filter keystrokes like float fields and reject the
    // fraction here, where the error message can say why. The range is
    // the one IntValidator enforced.
    function isWholeNumber(text) {
        if (text.indexOf(".") >= 0) return false;
        const value = Number.fromLocaleString(Qt.locale("C"), text);
        return value >= -2147483648 && value <= 2147483647;
    }

=======
    property string kind: "string" // int | float | string
    property alias text: editor.text
    readonly property bool valid: kind === "string" || editor.acceptableInput
    property string errorMessage: kind === "int"
        ? qsTr("Enter a whole number.") : qsTr("Enter a number.")
    signal committed(var value)

>>>>>>> origin/Train_Ctrl_integration
    spacing: theme.space_1
    opacity: enabled ? 1.0 : 0.42

    FieldLabel {
        Layout.fillWidth: true
        text: root.label.toUpperCase()
<<<<<<< HEAD
        visible: root.labelVisible && root.label !== ""
=======
        visible: root.label !== ""
>>>>>>> origin/Train_Ctrl_integration
    }

    TextField {
        id: editor
        objectName: "valueEditor"
        Layout.fillWidth: true
        implicitHeight: theme.control_h_md
        leftPadding: theme.space_3
        rightPadding: theme.space_3
        color: theme.text_primary
        font.family: theme.mono_family
        font.pixelSize: theme.size_small
        selectByMouse: true
        Accessible.name: root.label
<<<<<<< HEAD
        validator: root.kind === "int" || root.kind === "float"
            ? doubleValidator : null

=======
        validator: root.kind === "int" ? intValidator
            : root.kind === "float" ? doubleValidator : null

        IntValidator { id: intValidator; locale: "C" }
>>>>>>> origin/Train_Ctrl_integration
        DoubleValidator {
            id: doubleValidator
            locale: "C"
            notation: DoubleValidator.StandardNotation
<<<<<<< HEAD
            bottom: root.minimum
        }

        // The validator drops a refused keystroke without a trace ("12a"
        // stays "12"). Note what it refused and keep the note for the rest
        // of the edit, so a refusal mid-word ("1e3") still shows. A new edit
        // (focus returning), clearing the field, a kind change or a host-set
        // value clears it.
        property string rejectedInput: ""
        onActiveFocusChanged: if (activeFocus) rejectedInput = ""
        onValidatorChanged: rejectedInput = ""
        onTextChanged: if (!activeFocus || text === "") rejectedInput = ""
        Keys.onPressed: function (event) {
            if (validator === null)
                return;
            const code = event.text.length === 1 ? event.text.charCodeAt(0) : 0;
            const paste = event.matches(StandardKey.Paste);
            const typed = code >= 32 && code !== 127
                && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier));
            // Retyping the selected character changes nothing but is not refused.
            if ((!paste && !typed) || (typed && selectedText === event.text))
                return;
            const before = text;
            const refused = paste ? qsTr("Pasted text")
                : event.text === " " ? qsTr("Space") : "“" + event.text + "”";
            // The editor handles the key after this handler returns.
            Qt.callLater(function () {
                if (text === before)
                    rejectedInput = refused;
            });
=======
>>>>>>> origin/Train_Ctrl_integration
        }

        background: Rectangle {
            radius: theme.radius_md
            color: theme.bg_sunken
<<<<<<< HEAD
            border.color: root.showError ? theme.danger
=======
            border.color: !root.valid ? theme.danger
>>>>>>> origin/Train_Ctrl_integration
                : editor.activeFocus ? theme.accent : theme.border_strong
            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                radius: theme.radius_md + 4
                visible: editor.activeFocus
                color: "transparent"
                border.width: 2
                border.color: theme.focus_ring
            }
        }

<<<<<<< HEAD
        property bool userEdited: false
        // dirty is the user-command half of editingFinished: it only goes
        // true from onTextEdited and clears after a commit, so passing
        // through an untouched field never echoes its text back as input.
        property bool dirty: false

        onTextEdited: {
            userEdited = true;
            dirty = true;
        }
        Keys.onEscapePressed: function (event) {
            if (!dirty || root.modelValue === undefined) {
                event.accepted = false;
                return;
            }
            root.showModelValue();
        }

        onEditingFinished: {
            if (!root.valid || !dirty) return;
            if (root.kind === "string") {
                dirty = false;
=======
        // editingFinished fires on Return and again on focus loss; only
        // commit text that has not already been committed.
        property var lastCommittedText: undefined
        onTextChanged: if (text !== lastCommittedText) lastCommittedText = undefined

        onEditingFinished: {
            if (!root.valid || text === lastCommittedText) return;
            if (root.kind === "string") {
                lastCommittedText = text;
>>>>>>> origin/Train_Ctrl_integration
                root.committed(text);
            } else {
                const value = Number.fromLocaleString(Qt.locale("C"), text);
                if (Number.isFinite(value)) {
<<<<<<< HEAD
                    dirty = false;
=======
                    lastCommittedText = text;
>>>>>>> origin/Train_Ctrl_integration
                    root.committed(value);
                }
            }
        }
    }

    HelperText {
        Layout.fillWidth: true
<<<<<<< HEAD
        visible: root.showError
        text: editor.rejectedInput === "" ? root.errorMessage
            : qsTr("%1 ignored. %2").arg(editor.rejectedInput).arg(root.errorMessage)
=======
        visible: !root.valid
        text: root.errorMessage
>>>>>>> origin/Train_Ctrl_integration
        color: theme.danger
    }
}
