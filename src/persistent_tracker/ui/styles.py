APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0c0f15;
    color: #d5dae2;
    font-family: "Segoe UI";
    font-size: 13px;
}
QFrame#header, QFrame#panel, QFrame#controls {
    background-color: #121721;
    border: 1px solid #202735;
    border-radius: 8px;
}
QLabel#title {
    font-size: 20px;
    font-weight: 600;
    color: #f1f4f8;
}
QLabel#subtitle {
    color: #8e99aa;
}
QLabel#section {
    color: #f1f4f8;
    font-size: 12px;
    font-weight: 600;
}
QLabel#metricName {
    color: #7f8a9b;
}
QLabel#metricValue {
    color: #e2e7ee;
    font-weight: 500;
}
QPushButton {
    background-color: #1a2130;
    border: 1px solid #2a3446;
    border-radius: 5px;
    color: #dbe1e9;
    min-height: 30px;
    padding: 0 12px;
}
QPushButton:hover {
    background-color: #222c3d;
    border-color: #3c4b63;
}
QPushButton:pressed {
    background-color: #151c28;
}
QPushButton:disabled {
    color: #596273;
    background-color: #121720;
    border-color: #202735;
}
QPushButton#primary {
    background-color: #1d5f78;
    border-color: #267b99;
    color: #f3fbff;
}
QPushButton#danger {
    background-color: #4f2630;
    border-color: #78404c;
}
QSplitter::handle {
    background-color: #0c0f15;
    width: 6px;
}
QStatusBar {
    background-color: #0b0e13;
    color: #8e99aa;
}
"""
