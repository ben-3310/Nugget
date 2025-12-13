from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Qt


class MultiComboBox(QComboBox):
    def __init__(self, parent=None, updateAction=lambda x: None):
        super().__init__(parent)
        self.setEditable(True)
        if self.lineEdit() is not None:  # type: ignore
            self.lineEdit().setReadOnly(True)  # type: ignore
        self.setModel(QStandardItemModel(self))
        self.updateAction = updateAction
        self.noneText = "None"

        # Connect to the dataChanged signal to update the text
        self.model().dataChanged.connect(self.updateText)

    def addItem(self, text: str, data=None):
        item = QStandardItem()
        item.setText(text)
        item.setData(data)
        item.setEnabled(True)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        self.model().appendRow(item)  # type: ignore

    def addItems(self, items_list: list):
        for text in items_list:
            self.addItem(text)

    def deselectAll(self):
        for i in range(self.model().rowCount()):
            self.model().item(i).setCheckState(Qt.CheckState.Unchecked)  # type: ignore

    def selectIndices(self, indices: list[int]):
        for idx in indices:
            self.model().item(idx).setCheckState(Qt.CheckState.Checked)  # type: ignore

    def updateText(self):
        selected_items = [self.model().item(i).text() for i in range(self.model().rowCount())  # type: ignore
                          if self.model().item(i).checkState() == Qt.CheckState.Checked]  # type: ignore
        selected_data  = [self.model().item(i).data() for i in range(self.model().rowCount())  # type: ignore
                          if self.model().item(i).checkState() == Qt.CheckState.Checked]  # type: ignore
        if len(selected_items) == 0:
            if self.lineEdit() is not None:  # type: ignore
                self.lineEdit().setText(self.noneText)  # type: ignore
        elif len(selected_items) == 1:
            if self.lineEdit() is not None:  # type: ignore
                self.lineEdit().setText(f"  {selected_items[0]}")  # type: ignore
        else:
            if self.lineEdit() is not None:  # type: ignore
                self.lineEdit().setText(f"  ({len(selected_items)})")  # type: ignore
        if self.updateAction != None:
            self.updateAction(selected_data)

    def showPopup(self):
        super().showPopup()
        # Set the state of each item in the dropdown
        for i in range(self.model().rowCount()):
            item = self.model().item(i)  # type: ignore
            combo_box_view = self.view()
            combo_box_view.setRowHidden(i, False)  # type: ignore
            check_box = combo_box_view.indexWidget(item.index())  # type: ignore
            if check_box:
                check_box.setChecked(item.checkState() == Qt.CheckState.Checked)  # type: ignore

    def hidePopup(self):
        # Update the check state of each item based on the checkbox state
        for i in range(self.model().rowCount()):
            item = self.model().item(i)  # type: ignore
            combo_box_view = self.view()
            check_box = combo_box_view.indexWidget(item.index())  # type: ignore
            if check_box:
                item.setCheckState(Qt.CheckState.Checked if check_box.isChecked() else Qt.CheckState.Unchecked)  # type: ignore
        super().hidePopup()
