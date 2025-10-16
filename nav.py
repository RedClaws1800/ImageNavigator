import sys, os, json
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *


# ---------- Button (rectangle) ----------
class ButtonItem(QGraphicsRectItem):
    def __init__(self, rect, target=None, editable=True):
        super().__init__(rect)
        self.target = target
        self.setPen(QPen(QColor(255, 0, 0), 3))
        self.setBrush(QColor(255, 0, 0, 100))
        self.setZValue(10)
        if editable:
            self.setFlags(
                ButtonItem.GraphicsItemFlag.ItemIsSelectable
                and ButtonItem.GraphicsItemFlag.ItemIsMovable
                and ButtonItem.GraphicsItemFlag.ItemSendsGeometryChanges
                and ButtonItem.GraphicsItemFlag.ItemIsFocusable
            )


# ---------- Zoomable view ----------
class ImageView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.mode = "pan"
        self.start_pos = None
        self.temp_rect = None
        self.parent_window = None  # link back to editor/viewer

    def wheelEvent(self, event):
        zoom = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(zoom, zoom)

    def mousePressEvent(self, e):
        if self.mode == "add_button" and e.button() == Qt.MouseButton.LeftButton:
            self.start_pos = self.mapToScene(e.position().toPoint())
            self.temp_rect = self.scene().addRect(
                QRectF(self.start_pos, self.start_pos),
                QPen(QColor("blue"), 2, Qt.PenStyle.DashLine)
            )
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.mode == "add_button" and self.temp_rect:
            pos = self.mapToScene(e.position().toPoint())
            rect = QRectF(self.start_pos, pos).normalized()
            self.temp_rect.setRect(rect)
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self.mode == "add_button" and self.temp_rect:
            rect = self.temp_rect.rect()
            self.scene().removeItem(self.temp_rect)
            self.temp_rect = None
            self.mode = "pan"
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            if self.parent_window:
                self.parent_window.finish_button(rect)
        else:
            super().mouseReleaseEvent(e)


# ---------- Shared Scene ----------
class ImageScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.image_item = None

    def load_image(self, path):
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(None, "Error", f"Could not load image: {path}")
            return
        self.clear()
        self.image_item = QGraphicsPixmapItem(pix)
        self.image_item.setZValue(0)
        self.addItem(self.image_item)
        self.setSceneRect(pix.rect())


# ---------- Editor ----------
class Editor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Navigator - Editor")
        self.scene = ImageScene()
        self.view = ImageView(self.scene)
        self.view.parent_window = self
        self.setCentralWidget(self.view)

        self.project = {"scenes": {}}
        self.current_scene = None
        self.scene_history = []  # stack for Back button
        self.create_toolbar()

    def create_toolbar(self):
        tb = QToolBar(); self.addToolBar(tb)
        load_scene = QAction("Load Scene Image", self)
        load_scene.triggered.connect(self.load_scene_image)
        tb.addAction(load_scene)

        add_btn = QAction("Add Button", self)
        add_btn.triggered.connect(self.enable_add_mode)
        tb.addAction(add_btn)

        back_btn = QAction("Back", self)
        back_btn.triggered.connect(self.go_back)
        tb.addAction(back_btn)

        save_proj = QAction("Save Project", self)
        save_proj.triggered.connect(self.save_project)
        tb.addAction(save_proj)

        load_proj = QAction("Load Project", self)
        load_proj.triggered.connect(self.load_project)
        tb.addAction(load_proj)

    def load_scene_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Scene Image", "", "Images (*.png *.jpg *.jpeg)")
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0]
        self.scene.load_image(path)
        self.current_scene = name
        if name not in self.project["scenes"]:
            self.project["scenes"][name] = {"background": path, "buttons": []}
        self.display_buttons(name)

    def enable_add_mode(self):
        if not self.current_scene:
            QMessageBox.warning(self, "No Scene", "Load a scene image first.")
            return
        self.view.mode = "add_button"
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        QMessageBox.information(self, "Add Button Mode",
                                "Drag a rectangle on the image to make a button.")

    def finish_button(self, rect):
        # After drawing, choose the target image
        target_path, _ = QFileDialog.getOpenFileName(
            self, "Select Target Image", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not target_path:
            return
        target_name = os.path.splitext(os.path.basename(target_path))[0]
        # Make sure target scene exists
        if target_name not in self.project["scenes"]:
            self.project["scenes"][target_name] = {"background": target_path, "buttons": []}
        # Add button to current scene
        self.project["scenes"][self.current_scene]["buttons"].append({
            "coords": [rect.x(), rect.y(), rect.width(), rect.height()],
            "target": target_name
        })
        # Draw it visually
        btn = self.create_button_item(rect, target_name)
        self.scene.addItem(btn)

    def create_button_item(self, rect, target_name):
        btn = ButtonItem(rect, target_name)
        def open_target(target=target_name):
            self.open_scene(target)
        btn.mouseDoubleClickEvent = open_target
        return btn

    def display_buttons(self, scene_name):
        self.scene.clear()
        data = self.project["scenes"][scene_name]
        self.scene.load_image(data["background"])
        for b in data["buttons"]:
            rect = QRectF(b["coords"])
            btn = self.create_button_item(rect, b["target"])
            self.scene.addItem(btn)

    def open_scene(self, name):
        if name not in self.project["scenes"]:
            QMessageBox.warning(self, "Missing Scene", f"Scene '{name}' not found.")
            return
        if self.current_scene:
            self.scene_history.append(self.current_scene)
        self.current_scene = name
        self.display_buttons(name)

    def go_back(self):
        if not self.scene_history:
            QMessageBox.information(self, "Back", "No previous scene.")
            return
        prev = self.scene_history.pop()
        self.current_scene = prev
        self.display_buttons(prev)

    def save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON (*.json)")
        if not path:
            return
        with open(path, "w") as f:
            json.dump(self.project, f, indent=2)
        QMessageBox.information(self, "Saved", f"Project saved to {path}")

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON (*.json)")
        if not path:
            return
        with open(path, "r") as f:
            self.project = json.load(f)
        first_scene = next(iter(self.project["scenes"]))
        self.open_scene(first_scene)


# ---------- Viewer ----------
class Viewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Navigator - Viewer")
        self.scene = ImageScene()
        self.view = ImageView(self.scene)
        self.setCentralWidget(self.view)
        self.project = None
        self.current_scene = None

        tb = QToolBar(); self.addToolBar(tb)
        load_proj = QAction("Load Project", self)
        load_proj.triggered.connect(self.load_project)
        tb.addAction(load_proj)

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON (*.json)")
        if not path:
            return
        with open(path, "r") as f:
            self.project = json.load(f)
        first_scene = next(iter(self.project["scenes"]))
        self.load_scene(first_scene)

    def load_scene(self, name):
        data = self.project["scenes"][name]
        self.current_scene = name
        self.scene.load_image(data["background"])
        for b in data["buttons"]:
            rect = QRectF(b["coords"])
            btn = ButtonItem(rect, b["target"], editable=False)
            btn.setBrush(QColor(255, 0, 0, 80))
            self.scene.addItem(btn)
            def handle_click(target=b["target"]):
                self.load_scene(target)
            btn.mousePressEvent = handle_click


# ---------- Main ----------
def main():
    app = QApplication(sys.argv)

    # Loop forever until user cancels
    while True:
        mode, ok = QInputDialog.getItem(None, "Choose Mode", "Mode:", ["Editor", "Viewer"], 0, False)
        if not ok:
            break  # user pressed Cancel → exit program

        window = Editor() if mode == "Editor" else Viewer()
        window.resize(1200, 800)
        window.show()

        # Run until this window closes
        app.exec()

        # When window closes, loop back and ask again
        # (press Cancel in the dialog to fully exit)
        

if __name__ == "__main__":
    main()
