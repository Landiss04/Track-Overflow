import QtQuick

// Text entry field (Style Guide §6.2): sunken well, strong border,
// radius-md, mono face. Wide variant for string signals; commits on Enter
// or focus loss. `sourceText` is the external value; the field resyncs
// from it whenever it changes while unfocused (covers RESET MODULE).
Item {
    id: root

    property string sourceText: ""
    property bool enabled_: true    // underscored: `enabled` is reserved by Item

    signal commit(string value)

    implicitWidth: theme.field_wide_width
    implicitHeight: theme.field_height

    onSourceTextChanged: {
        if (!field.activeFocus && field.text !== sourceText)
            field.text = sourceText
    }

    Rectangle {
        anchors.fill: parent
        color: theme.bg_sunken
        border.width: 1
        border.color: theme.border_strong
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

        function commitValue() {
            var value = field.text.trim()
            if (value.length > 0)
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
}
