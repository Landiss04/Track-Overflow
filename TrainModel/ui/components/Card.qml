import QtQuick

// Panel (Style Guide §4.1/§5): white surface, 1 px border, --radius-lg,
// resting shadow approximated as a soft offset rectangle (--shadow-1 is a
// 1 px blur, which QML renders as a 1 px dark halo). Header strip carries
// the title (H3) and an optional status badge; body content goes in `body`.
// Rooted on an Item so the shadow/surface may anchor-fill behind the
// content Column (anchored children are not allowed inside a Column).
Item {
    id: root

    property string title: ""
    property alias badgeText: headerBadge.text
    property string badgeVariant: "idle"
    default property alias body: bodyColumn.data

    implicitHeight: content.implicitHeight

    // Resting shadow (--shadow-1, 1 px offset).
    Rectangle {
        z: -1
        anchors.fill: parent
        anchors.margins: -1
        anchors.topMargin: 0
        color: Qt.rgba(22 / 255, 32 / 255, 42 / 255, 0.08)
        radius: theme.radius_lg
    }

    // Surface.
    Rectangle {
        anchors.fill: parent
        color: theme.bg_surface
        border.width: 1
        border.color: theme.border
        radius: theme.radius_lg
    }

    Column {
        id: content
        width: root.width
        spacing: 0

        // Header strip.
        Item {
            width: parent.width
            height: theme.card_header_height

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: theme.border
            }

            Text {
                id: headerTitle
                anchors.left: parent.left
                anchors.leftMargin: theme.space_4
                anchors.verticalCenter: parent.verticalCenter
                text: root.title
                font.family: theme.ui_family
                font.pixelSize: theme.font_h3
                font.weight: Font.Bold
                color: theme.text_primary
            }

            Badge {
                id: headerBadge
                anchors.right: parent.right
                anchors.rightMargin: theme.space_4
                anchors.verticalCenter: parent.verticalCenter
                variant: root.badgeVariant
            }
        }

        Column {
            id: bodyColumn
            width: parent.width
            leftPadding: theme.space_4
            rightPadding: theme.space_4
            topPadding: theme.space_4
            bottomPadding: theme.space_5
            spacing: theme.space_4
        }
    }
}
