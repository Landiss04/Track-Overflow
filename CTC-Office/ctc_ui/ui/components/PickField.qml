// A SelectField that shows only what the dispatcher picked.
//
// A ComboBox selects its first option whenever its model is filled or
// replaced, so a dependent select (a block after a line is chosen) would
// arrive pre-filled with a value nobody chose, and enable the action
// behind it. This keeps the dispatcher's pick by value instead: after
// every model change it re-selects that value, or nothing at all.
import QtQuick
import "../../../../ui"

SelectField {
    id: root

    // The value the dispatcher picked; undefined until they pick.
    property var picked: undefined
    // The picked value, or "" when nothing is picked.
    readonly property string value: root.currentIndex >= 0
        ? String(root.currentValue ?? "") : ""

    function valueAt(index) {
        const item = model[index];
        return item !== null && typeof item === "object" ? item.value : item;
    }

    function restore() {
        let index = -1;
        if (root.picked !== undefined) {
            for (let i = 0; i < (model ? model.length : 0); ++i) {
                if (root.valueAt(i) === root.picked) {
                    index = i;
                    break;
                }
            }
        }
        if (currentIndex !== index)
            currentIndex = index;
    }

    // Forget the pick (e.g. after the action it was for).
    function clear() {
        root.picked = undefined;
        root.restore();
    }

    currentIndex: -1
    onCommitted: function (value) { root.picked = value; }
    onModelChanged: Qt.callLater(root.restore)
    // Qt may select index 0 after the model change; undo it.
    onCurrentIndexChanged: if (currentIndex >= 0 && picked === undefined)
        Qt.callLater(root.restore)
}
