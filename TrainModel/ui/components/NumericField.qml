import QtQuick

// Numeric entry field (Style Guide §6.2): sunken well, strong border,
// radius-md, mono face. `allowDecimals` selects the int/float validator —
// input is filtered as typed and the commit is refused unless it parses to
// the declared type; an invalid attempt turns the border --danger.
// `sourceText` is the external value (Python-formatted); the field resyncs
// from it whenever it changes while unfocused (covers RESET MODULE).
Item {
    id: root

    property string sourceText: ""
    property bool allowDecimals: false
    property bool enabled_: true    // underscored: `enabled` is reserved by Item

    signal commit(string value)

    readonly property bool invalid: _invalid
    property bool _invalid: false

    implicitWidth: widthPx
    property int widthPx: theme.field_narrow_width
    implicitHeight: theme.field_height

    onSourceTextChanged: {
        if (!field.activeFocus && field.text !== sourceText)
            field.text = sourceText
    }

    Rectangle {
        anchors.fill: parent
        color: theme.bg_sunken
        border.width: 1
        border.color: root._invalid ? theme.danger : theme.border_strong
        radius: theme.radius_md
        opacity: root.enabled_ ? 1.0 : theme.disabled_opacity
    }

    TextInput {
        id: field
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: theme.space_3
        anchors.verticalCenter: parent.verticalCenter
        text: root.sourceText
        clip: true
        selectByMouse: true
        activeFocusOnPress: true
        font.family: theme.mono_family
        font.pixelSize: theme.font_body
        color: theme.text_primary

        onTextChanged: {
            // Filter as typed: digits, one optional leading minus, and a
            // single decimal point when floats are allowed.
            var cleaned = text.replace(/[^0-9.\-]/g, "")
            if (!root.allowDecimals)
                cleaned = cleaned.replace(/\./g, "")
            if (cleaned !== text)
                field.text = cleaned
        }

        function commitValue() {
            var value = field.text.trim()
            if (value.length === 0 || value === "-" || value === ".") {
                root._invalid = true
                return
            }
            var parsed = Number(value)
            if (isNaN(parsed)) {
                root._invalid = true
                return
            }
            if (!root.allowDecimals && parsed !== Math.trunc(parsed)) {
                root._invalid = true
                return
            }
            root._invalid = false
            root.commit(value)
        }

        onAccepted: commitValue()
        onActiveFocusChanged: if (!activeFocus) commitValue()
    }

    // Focus ring (2 px, 2 px offset), keyboard focus only.
    Rectangle {
        visible: field.activeFocus
        anchors.fill: parent
        anchors.margins: -theme.focus_ring_offset
        color: "transparent"
        border.width: theme.focus_ring_width
        border.color: theme.focus_ring
        radius: theme.radius_md
    }

    // Error message beneath the field (Style Guide §6.2).
    Text {
        anchors.top: parent.bottom
        anchors.topMargin: theme.space_1
        anchors.left: parent.left
        text: root._invalid ? "Invalid number" : ""
        font.family: theme.ui_family
        font.pixelSize: theme.font_small
        color: theme.danger
    }
}
