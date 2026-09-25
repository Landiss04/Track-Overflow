import QtQuick
import QtQuick.Layouts
import "./components"

// Application shell: window chrome, the collapsed nav rail (page 3b), and
// a view loader that swaps between page 3a (MainView) and page 3b
// (TestView). The design width (1440) is held as the minimum; extra
// window width is shared by the two columns of each view.
Window {
    id: app

    title: "Train Model"
    visible: true
    width: theme.design_width
    height: theme.design_height
    minimumWidth: theme.design_width
    minimumHeight: theme.design_height
    color: theme.bg_app

    // Rail item 5 is the Test UI per the mockup; item 4 is the Main page.
    readonly property int mainIndex: 3
    readonly property int testIndex: 4

    property int activeView: app.testIndex

    RowLayout {
        anchors.fill: parent
        spacing: 0

        NavRail {
            Layout.preferredWidth: theme.nav_rail_width
            Layout.fillHeight: true
            activeIndex: app.activeView
            onActivated: function(index) {
                if (index === app.mainIndex || index === app.testIndex)
                    app.activeView = index
            }
        }

        Item {
            id: viewHost
            Layout.fillWidth: true
            Layout.fillHeight: true

            MainView {
                anchors.fill: parent
                visible: app.activeView === app.mainIndex
            }

            TestView {
                anchors.fill: parent
                visible: app.activeView === app.testIndex
            }
        }
    }
}
