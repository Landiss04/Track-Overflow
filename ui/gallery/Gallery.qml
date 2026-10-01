// Component gallery: every shared ui/ component in every variant and state.
// Interactive signals are written to the event log on the right; the host
// counts QML warnings live so a broken binding shows up immediately.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."

ApplicationWindow {
    id: gallery

    width: 1440
    height: 900
    visible: true
    title: "Shared UI Component Gallery"
    color: theme.bg_app

    // Host-owned state the components bind to.
    property int navIndex: 0
    property bool faulted: false
    property bool brakeApplied: false
    property bool tcBrakeApplied: false
    property int toggle2: 0
    property int toggle3: 1
    property int toggleLong: 0
    property int railIndex: 0
    property int tableIndex: -1
    property bool editBool: true
    property var editFloat: 118000.5
    property var editInt: 12
    property string editString: "GREEN M"
    property real liveValue: 0
    property string clockText: Qt.formatTime(new Date(), "hh:mm:ss")

    property int eventCount: 0
    property int errorCount: 0
    property var eventLines: []

    function log(message) {
        eventCount += 1;
        if (message.indexOf("ERROR") === 0)
            errorCount += 1;
        eventLines = eventLines.concat([message]);
        logModel.insert(0, {
            stamp: Qt.formatTime(new Date(), "hh:mm:ss"),
            message: message
        });
    }

    Timer {
        interval: 250
        running: true
        repeat: true
        onTriggered: {
            gallery.liveValue = (gallery.liveValue + 3.7) % 120;
            gallery.clockText = Qt.formatTime(new Date(), "hh:mm:ss");
        }
    }

    ListModel { id: logModel }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ModuleHeader {
            Layout.fillWidth: true
            moduleName: "Component Gallery"
            instance: "TRN-014"
            mode: "Automatic"
            line: "Green Line"
            clock: gallery.clockText
            faulted: gallery.faulted
            navigationEntries: ["Overview", "Controls", "Data"]
            currentNavigationIndex: gallery.navIndex
            onNavigationActivated: function (index) {
                gallery.navIndex = index;
                gallery.log("ModuleHeader navigationActivated(" + index + ")");
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            ScrollView {
                id: scroller
                objectName: "galleryScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth

                ColumnLayout {
                    id: content
                    objectName: "galleryContent"
                    width: scroller.availableWidth
                    spacing: theme.space_5

                    // ---------------- Left column ----------------
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                        Layout.margins: theme.space_5
                        Layout.bottomMargin: 0
                        spacing: theme.space_5

                        Card {
                            Layout.fillWidth: true
                            title: "AppButton"
                            statusLabel: "5 variants × 3 sizes"
                            statusVariant: "info"

                            Repeater {
                                model: ["primary", "secondary", "ghost", "danger", "success"]

                                delegate: RowLayout {
                                    id: variantRow
                                    required property string modelData
                                    Layout.fillWidth: true
                                    spacing: theme.space_3

                                    FieldLabel {
                                        Layout.preferredWidth: 120
                                        text: variantRow.modelData.toUpperCase()
                                    }

                                    Repeater {
                                        model: ["small", "medium", "large"]

                                        delegate: AppButton {
                                            required property string modelData
                                            variant: variantRow.modelData
                                            size: modelData
                                            text: modelData.charAt(0).toUpperCase()
                                                + modelData.slice(1)
                                            onClicked: gallery.log("AppButton "
                                                + variant + "/" + size + " clicked")
                                        }
                                    }

                                    AppButton {
                                        variant: variantRow.modelData
                                        text: "Disabled"
                                        enabled: false
                                        onClicked: gallery.log("ERROR: disabled "
                                            + variant + " button clicked")
                                    }
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: theme.space_3

                                AppButton {
                                    variant: "danger"
                                    active: true
                                    text: "Danger (active)"
                                    onClicked: gallery.log("AppButton danger active clicked")
                                }

                                AppButton {
                                    variant: "secondary"
                                    text: "Hover for tooltip"
                                    tooltip: "Native ToolTip from AppButton.tooltip"
                                    onClicked: gallery.log("AppButton tooltip clicked")
                                }

                                // Too narrow for its label on purpose: the text
                                // must end in "…" inside the button, not spill out.
                                AppButton {
                                    objectName: "elideButton"
                                    Layout.preferredWidth: 220
                                    variant: "primary"
                                    text: "Long label cut off with an ellipsis when the button is too narrow"
                                    onClicked: gallery.log("AppButton narrow (elided) clicked")
                                }
                            }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "SafetyButton"
                            statusLabel: gallery.brakeApplied ? "Applied" : "Released"
                            statusVariant: gallery.brakeApplied ? "fault" : "ok"

                            HelperText {
                                Layout.fillWidth: true
                                text: "Confirmed: press, then CONFIRM or Cancel. "
                                    + "Unconfirmed (Train Controller only) acts immediately."
                            }

                            SafetyButton {
                                Layout.fillWidth: true
                                label: "Apply emergency brake"
                                applied: gallery.brakeApplied
                                tooltip: "Confirmation is required."
                                onConfirmed: {
                                    gallery.brakeApplied = !gallery.brakeApplied;
                                    gallery.log("SafetyButton confirmed → applied="
                                        + gallery.brakeApplied);
                                }
                            }

                            SafetyButton {
                                Layout.fillWidth: true
                                label: "Train Controller e-brake"
                                confirmationRequired: false
                                applied: gallery.tcBrakeApplied
                                onConfirmed: {
                                    gallery.tcBrakeApplied = !gallery.tcBrakeApplied;
                                    gallery.log("SafetyButton (unconfirmed) → applied="
                                        + gallery.tcBrakeApplied);
                                }
                            }

                            SafetyButton {
                                Layout.fillWidth: true
                                label: "Disabled safety control"
                                enabled: false
                                onConfirmed: gallery.log("ERROR: disabled SafetyButton confirmed")
                            }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "SegmentedToggle"

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: theme.space_3

                                SegmentedToggle {
                                    options: ["True", "False"]
                                    currentIndex: gallery.toggle2
                                    onActivated: function (index) {
                                        gallery.toggle2 = index;
                                        gallery.log("SegmentedToggle[2] activated(" + index + ")");
                                    }
                                }

                                SegmentedToggle {
                                    options: ["Auto", "Manual", "Maintenance"]
                                    currentIndex: gallery.toggle3
                                    onActivated: function (index) {
                                        gallery.toggle3 = index;
                                        gallery.log("SegmentedToggle[3] activated(" + index + ")");
                                    }
                                }

                                SegmentedToggle {
                                    options: ["On", "Off"]
                                    currentIndex: 0
                                    enabled: false
                                    onActivated: gallery.log("ERROR: disabled toggle activated")
                                }
                            }

                            SegmentedToggle {
                                Layout.fillWidth: true
                                options: ["Run", "Hold"]
                                currentIndex: gallery.toggleLong
                                onActivated: function (index) {
                                    gallery.toggleLong = index;
                                    gallery.log("SegmentedToggle[fill] activated(" + index + ")");
                                }
                            }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "NavRail · ModuleHeader (empty states)"

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: theme.space_4

                                NavRail {
                                    Layout.preferredHeight: 190
                                    entries: ["Overview", "Test harness", "Blocks", "Log"]
                                    currentIndex: gallery.railIndex
                                    onActivated: function (index) {
                                        gallery.railIndex = index;
                                        gallery.log("NavRail activated(" + index + ")");
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.alignment: Qt.AlignTop
                                    spacing: theme.space_3

                                    FieldLabel { text: "HEADER — NO INSTANCE, NAV OR LINE" }
                                    ModuleHeader {
                                        Layout.fillWidth: true
                                        moduleName: "Track Model"
                                        clock: "07:30:00"
                                    }

                                    FieldLabel { text: "HEADER — FAULTED" }
                                    ModuleHeader {
                                        Layout.fillWidth: true
                                        moduleName: "Train Controller"
                                        instance: "TRN-002"
                                        mode: "Manual"
                                        clock: "07:30:00"
                                        faulted: true
                                    }

                                    AppButton {
                                        variant: "secondary"
                                        size: "small"
                                        text: gallery.faulted
                                            ? "Clear top header fault" : "Fault top header"
                                        onClicked: {
                                            gallery.faulted = !gallery.faulted;
                                            gallery.log("Top header faulted=" + gallery.faulted);
                                        }
                                    }
                                }
                            }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "ValueField · SelectField"

                            GridLayout {
                                Layout.fillWidth: true
                                columns: 2
                                columnSpacing: theme.space_4
                                rowSpacing: theme.space_3

                                ValueField {
                                    Layout.fillWidth: true
                                    label: "Integer (kind int)"
                                    kind: "int"
                                    text: "42"
                                    onCommitted: function (v) {
                                        gallery.log("ValueField int committed "
                                            + v + " (" + typeof v + ")");
                                    }
                                }

                                ValueField {
                                    Layout.fillWidth: true
                                    label: "Float (kind float)"
                                    kind: "float"
                                    text: "12.5"
                                    onCommitted: function (v) {
                                        gallery.log("ValueField float committed "
                                            + v + " (" + typeof v + ")");
                                    }
                                }

                                ValueField {
                                    Layout.fillWidth: true
                                    label: "String (kind string)"
                                    text: "001"
                                    onCommitted: function (v) {
                                        gallery.log("ValueField string committed \""
                                            + v + "\" (" + typeof v + ")");
                                    }
                                }

                                ValueField {
                                    Layout.fillWidth: true
                                    label: "Invalid float (shows error)"
                                    kind: "float"
                                    text: "-"
                                    onCommitted: function (v) {
                                        gallery.log("ValueField invalid committed " + v);
                                    }
                                }

                                ValueField {
                                    Layout.fillWidth: true
                                    label: "Disabled"
                                    kind: "int"
                                    text: "7"
                                    enabled: false
                                }

                                ValueField {
                                    Layout.fillWidth: true
                                    kind: "string"
                                    text: "No label (label hidden)"
                                }

                                SelectField {
                                    Layout.fillWidth: true
                                    label: "Train (object model)"
                                    model: [
                                        { label: "TRN-001 · Green", id: "001" },
                                        { label: "TRN-002 · Red", id: "002" },
                                        { label: "TRN-014 · Green", id: "014" }
                                    ]
                                    textRole: "label"
                                    valueRole: "id"
                                    onCommitted: function (v) {
                                        gallery.log("SelectField committed \"" + v + "\"");
                                    }
                                }

                                SelectField {
                                    Layout.fillWidth: true
                                    label: "Disabled select"
                                    model: [{ label: "Only option", id: "x" }]
                                    textRole: "label"
                                    valueRole: "id"
                                    enabled: false
                                }

                                // Narrow on purpose: long text must end in "…"
                                // before the arrow, never run underneath it.
                                SelectField {
                                    objectName: "elideSelect"
                                    Layout.preferredWidth: 220
                                    label: "Long option (elides)"
                                    model: [{
                                        label: "Green Line — Dormont to South Hills Junction",
                                        id: "long"
                                    }]
                                    textRole: "label"
                                    valueRole: "id"
                                }
                            }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "Disabled states (dimmed once, still legible)"

                            HelperText {
                                Layout.fillWidth: true
                                text: "Every control here is enabled: false and must look like "
                                    + "the disabled AppButton above: faded once, never twice."
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: theme.space_4

                                NavRail {
                                    Layout.preferredHeight: 130
                                    entries: ["Overview", "Test harness"]
                                    currentIndex: 0
                                    enabled: false
                                    onActivated: gallery.log("ERROR: disabled NavRail activated")
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.alignment: Qt.AlignTop
                                    spacing: theme.space_3

                                    ModuleHeader {
                                        Layout.fillWidth: true
                                        moduleName: "Disabled header"
                                        navigationEntries: ["One", "Two"]
                                        currentNavigationIndex: 0
                                        enabled: false
                                        onNavigationActivated: gallery.log(
                                            "ERROR: disabled ModuleHeader navigated")
                                    }

                                    SignalRow {
                                        Layout.fillWidth: true
                                        name: "disabled_bool"
                                        kind: "bool"
                                        value: true
                                        editable: true
                                        enabled: false
                                        onEdited: gallery.log("ERROR: disabled SignalRow edited")
                                    }

                                    SignalRow {
                                        Layout.fillWidth: true
                                        name: "disabled_float"
                                        kind: "float"
                                        value: 3.25
                                        editable: true
                                        enabled: false
                                        onEdited: gallery.log("ERROR: disabled SignalRow edited")
                                    }

                                    DataTable {
                                        Layout.fillWidth: true
                                        enabled: false
                                        columns: [
                                            { key: "id", label: "Train", mono: true },
                                            { key: "speed", label: "Speed", numeric: true }
                                        ]
                                        rows: [{ id: "001", speed: 12.5 }]
                                        onRowActivated: gallery.log("ERROR: disabled DataTable row activated")
                                    }
                                }
                            }
                        }
                    }

                    // ---------------- Right column ----------------
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.alignment: Qt.AlignTop
                        Layout.margins: theme.space_5
                        Layout.topMargin: 0
                        spacing: theme.space_5

                        Card {
                            Layout.fillWidth: true
                            title: "TableHeader · SignalRow"

                            TableHeader { Layout.fillWidth: true }

                            SignalRow { Layout.fillWidth: true; name: "bool_true"; kind: "bool"; value: true }
                            SignalRow { Layout.fillWidth: true; name: "bool_false"; kind: "bool"; value: false }
                            SignalRow { Layout.fillWidth: true; name: "int_value"; kind: "int"; value: 68; unit: "F" }
                            SignalRow { Layout.fillWidth: true; name: "float_value"; kind: "float"; value: 16.25; unit: "mph" }
                            SignalRow { Layout.fillWidth: true; name: "string_value"; kind: "string"; value: "Dormont" }
                            SignalRow { Layout.fillWidth: true; name: "null_value"; kind: "float"; value: null; unit: "ft" }
                            SignalRow { Layout.fillWidth: true; name: "empty_string"; kind: "string"; value: "" }

                            SignalRow {
                                Layout.fillWidth: true
                                name: "edit_bool"
                                kind: "bool"
                                value: gallery.editBool
                                editable: true
                                onEdited: function (v) {
                                    gallery.editBool = v;
                                    gallery.log("SignalRow edit_bool edited " + v);
                                }
                            }

                            SignalRow {
                                Layout.fillWidth: true
                                name: "edit_float"
                                kind: "float"
                                value: gallery.editFloat
                                unit: "W"
                                editable: true
                                onEdited: function (v) {
                                    gallery.editFloat = v;
                                    gallery.log("SignalRow edit_float edited " + v
                                        + " (" + typeof v + ")");
                                }
                            }

                            SignalRow {
                                Layout.fillWidth: true
                                name: "edit_int"
                                kind: "int"
                                value: gallery.editInt
                                editable: true
                                onEdited: function (v) {
                                    gallery.editInt = v;
                                    gallery.log("SignalRow edit_int edited " + v
                                        + " (" + typeof v + ")");
                                }
                            }

                            SignalRow {
                                Layout.fillWidth: true
                                name: "edit_string"
                                kind: "string"
                                value: gallery.editString
                                editable: true
                                onEdited: function (v) {
                                    gallery.editString = v;
                                    gallery.log("SignalRow edit_string edited \"" + v + "\"");
                                }
                            }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "DataTable"
                            statusLabel: gallery.tableIndex < 0
                                ? "No row selected" : "Row " + gallery.tableIndex
                            statusVariant: gallery.tableIndex < 0 ? "idle" : "info"

                            DataTable {
                                Layout.fillWidth: true
                                columns: [
                                    { key: "id", label: "Train", mono: true, width: 80 },
                                    { key: "line", label: "Line", width: 100 },
                                    { key: "speed", label: "Speed (mph)", numeric: true, width: 110 },
                                    { key: "block", label: "Block", mono: true, width: 80 }
                                ]
                                rows: [
                                    { id: "001", line: "Green", speed: 32.4, block: "A1" },
                                    { id: "002", line: "Red", speed: 0, block: "C12" },
                                    { id: "014", line: "Green", speed: null, block: "" },
                                    { id: "020", line: "", speed: 18.75 }
                                ]
                                currentIndex: gallery.tableIndex
                                onRowActivated: function (index, row) {
                                    gallery.tableIndex = index;
                                    gallery.log("DataTable rowActivated(" + index + ", "
                                        + JSON.stringify(row) + ")");
                                }
                            }

                            HelperText {
                                Layout.fillWidth: true
                                text: "Nulls, blanks and missing keys must render as an em dash."
                            }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "TrackBlock · StatusBadge"

                            FieldLabel { text: "TRACK BLOCK — ALL OCCUPANCY STATES" }
                            Flow {
                                Layout.fillWidth: true
                                spacing: theme.space_1

                                TrackBlock { blockId: "A1"; occupancy: "free" }
                                TrackBlock { blockId: "A2"; occupancy: "occupied" }
                                TrackBlock { blockId: "A3"; occupancy: "closed" }
                                TrackBlock { blockId: "A4"; occupancy: "failure" }
                                TrackBlock { blockId: "A5"; occupancy: "maintenance" }
                                TrackBlock { blockId: "A6"; occupancy: "bogus" }
                                TrackBlock { occupancy: "occupied" }
                            }

                            FieldLabel { text: "STATUS BADGE — ALL VARIANTS" }
                            Flow {
                                Layout.fillWidth: true
                                spacing: theme.space_2

                                StatusBadge { variant: "ok"; label: "Operational" }
                                StatusBadge { variant: "warning"; label: "Speed restricted" }
                                StatusBadge { variant: "fault"; label: "Broken rail" }
                                StatusBadge { variant: "info"; label: "Occupied" }
                                StatusBadge { variant: "idle"; label: "Offline" }
                                StatusBadge { variant: "unknown-variant"; label: "Fallback idle" }
                            }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "TelemetryReadout · UsageBar"

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: theme.space_3

                                TelemetryReadout {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    label: "Live speed"
                                    value: gallery.liveValue.toFixed(1)
                                    unit: "mph"
                                }
                                TelemetryReadout {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    label: "No unit"
                                    value: "12 / 222"
                                }
                                TelemetryReadout {
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    label: "Default value"
                                }
                            }

                            FieldLabel { text: "USAGE BAR — 0%, 35%, 100%, OVER CEILING, CEILING 0, LIVE" }
                            UsageBar { Layout.fillWidth: true; value: 0; ceiling: 480 }
                            UsageBar { Layout.fillWidth: true; value: 168; ceiling: 480 }
                            UsageBar { Layout.fillWidth: true; value: 480; ceiling: 480 }
                            UsageBar { Layout.fillWidth: true; value: 720; ceiling: 480 }
                            UsageBar { Layout.fillWidth: true; value: 10; ceiling: 0 }
                            UsageBar { Layout.fillWidth: true; value: gallery.liveValue; ceiling: 120 }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "Text components · Callout · Card"

                            FieldLabel { text: "FIELD LABEL" }
                            HelperText {
                                Layout.fillWidth: true
                                text: "HelperText wraps across lines when it is long enough to "
                                    + "exceed the card width, which this sentence deliberately is."
                            }
                            MonoText { text: "MonoText 0123456789 TRN-014 19:00:05" }

                            KeyValueRow { Layout.fillWidth: true; label: "KeyValueRow"; value: "410.0 ft" }
                            KeyValueRow { Layout.fillWidth: true; label: "Empty value → em dash"; value: "" }
                            KeyValueRow { Layout.fillWidth: true; label: "No rule below"; value: "rule: false"; rule: false }

                            Callout {
                                Layout.fillWidth: true
                                heading: "Callout with heading and body"
                                body: "The body is HelperText on the accent-subtle fill."
                            }

                            Callout {
                                Layout.fillWidth: true
                                heading: "Callout with heading only"
                            }

                            Callout {
                                Layout.fillWidth: true
                                variant: "warning"
                                heading: "Warning callout"
                                body: "variant: \"warning\" uses --warning on --warning-bg, "
                                    + "for caution states such as a maintenance mode."
                            }

                            Card {
                                Layout.fillWidth: true
                                title: "Nested framed card"
                                statusLabel: "Warning"
                                statusVariant: "warning"
                                HelperText { text: "Card content slot." }
                            }

                            Card {
                                Layout.fillWidth: true
                                framed: false
                                title: "Unframed card (flat section)"
                                HelperText { text: "No border, H2 title, no rule." }
                            }
                        }

                        Card {
                            Layout.fillWidth: true
                            title: "Panel · EmptyState · FormField · LabeledDivider"

                            Panel {
                                Layout.fillWidth: true
                                title: "Panel with header items"
                                headerItems: [
                                    StatusBadge { label: "Running"; variant: "ok" },
                                    AppButton {
                                        variant: "ghost"
                                        size: "small"
                                        text: "Clear"
                                        onClicked: gallery.log("Panel header button clicked")
                                    }
                                ]
                                HelperText {
                                    Layout.fillWidth: true
                                    text: "Body slot. Children land in the body column."
                                }
                            }

                            Panel {
                                Layout.fillWidth: true
                                title: "Panel with a very long title that should elide before it reaches the header items"
                                headerItems: [StatusBadge { label: "Idle" }]
                                HelperText { text: "Long title elides." }
                            }

                            Panel {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 200
                                title: "Panel with EmptyState"
                                Item {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    EmptyState {
                                        anchors.centerIn: parent
                                        heading: "Nothing to show"
                                        body: "EmptyState shrinks to fit a narrow parent."
                                    }
                                }
                            }

                            FormField {
                                Layout.fillWidth: true
                                label: "FormField around a toggle"
                                SegmentedToggle {
                                    options: ["Normal", "Reverse"]
                                    currentIndex: -1
                                    onActivated: function (index) {
                                        currentIndex = index;
                                        gallery.log("FormField toggle -> " + index);
                                    }
                                }
                            }

                            LabeledDivider {
                                Layout.fillWidth: true
                                text: "or labeled divider"
                            }
                        }
                    }
                }
            }

            // ---------------- Event log / warnings ----------------
            Rectangle {
                Layout.preferredWidth: 360
                Layout.fillHeight: true
                color: theme.bg_surface
                border.color: theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: theme.space_4
                    spacing: theme.space_3

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.space_2

                        Text {
                            Layout.fillWidth: true
                            text: "QML warnings"
                            color: theme.text_primary
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_h3
                            font.weight: theme.weight_bold
                        }

                        StatusBadge {
                            objectName: "warningBadge"
                            label: warningLog.warning_count === 0
                                ? "None" : warningLog.warning_count + " found"
                            variant: warningLog.warning_count === 0 ? "ok" : "fault"
                        }
                    }

                    Repeater {
                        model: warningLog.warnings
                        delegate: HelperText {
                            required property string modelData
                            Layout.fillWidth: true
                            text: modelData
                            color: theme.danger
                        }
                    }

                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.border }

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            Layout.fillWidth: true
                            text: "Event log"
                            color: theme.text_primary
                            font.family: theme.ui_family
                            font.pixelSize: theme.size_h3
                            font.weight: theme.weight_bold
                        }

                        AppButton {
                            variant: "ghost"
                            size: "small"
                            text: "Clear"
                            onClicked: logModel.clear()
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: logModel
                        spacing: theme.space_1
                        delegate: MonoText {
                            required property string stamp
                            required property string message
                            width: ListView.view.width
                            wrapMode: Text.WrapAnywhere
                            text: stamp + "  " + message
                            color: message.indexOf("ERROR") === 0
                                ? theme.danger : theme.text_primary
                        }
                    }
                }
            }
        }
    }
}
