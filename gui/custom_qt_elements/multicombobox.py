from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Qt


class MultiComboBox(QComboBox):
    def __init__(self, parent=None, updateAction=lambda x: None):
        super().__init__(parent)
        self.setEditable(True)
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.setReadOnly(True)
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
        model = self.model()
        if isinstance(model, QStandardItemModel):
            model.appendRow(item)

    def addItems(self, items_list: list):
        for text in items_list:
            self.addItem(text)

    def deselectAll(self):
        model = self.model()
        if isinstance(model, QStandardItemModel):
            for i in range(model.rowCount()):
                item = model.item(i)
                if item is not None:
                    item.setCheckState(Qt.CheckState.Unchecked)

    def selectIndices(self, indices: list[int]):
        model = self.model()
        if isinstance(model, QStandardItemModel):
            for idx in indices:
                item = model.item(idx)
                if item is not None:
                    item.setCheckState(Qt.CheckState.Checked)

    def updateText(self):
        model = self.model()
        if not isinstance(model, QStandardItemModel):
            return
        selected_items = [model.item(i).text() for i in range(model.rowCount())
                          if (item := model.item(i)) is not None and item.checkState() == Qt.CheckState.Checked]
        selected_data  = [model.item(i).data() for i in range(model.rowCount())
                          if (item := model.item(i)) is not None and item.checkState() == Qt.CheckState.Checked]
        line_edit = self.lineEdit()
        if line_edit is not None:
            if len(selected_items) == 0:
                line_edit.setText(self.noneText)
            elif len(selected_items) == 1:
                line_edit.setText(f"  {selected_items[0]}")
            else:
                line_edit.setText(f"  ({len(selected_items)})")
        if self.updateAction != None:
            self.updateAction(selected_data)

    def showPopup(self):
        super().showPopup()
        # Set the state of each item in the dropdown
        model = self.model()
        if isinstance(model, QStandardItemModel):
            combo_box_view = self.view()
            if combo_box_view is not None:
                for i in range(model.rowCount()):
                    item = model.item(i)
                    if item is not None:
                        combo_box_view.setRowHidden(i, False)  # type: ignore
                        check_box = combo_box_view.indexWidget(item.index())
                        if check_box is not None:
                            check_box.setChecked(item.checkState() == Qt.CheckState.Checked)  # type: ignore

    def hidePopup(self):
        # Update the check state of each item based on the checkbox state
        model = self.model()
        if isinstance(model, QStandardItemModel):
            combo_box_view = self.view()
            if combo_box_view is not None:
                for i in range(model.rowCount()):
                    item = model.item(i)
                    if item is not None:
                        check_box = combo_box_view.indexWidget(item.index())
                        if check_box is not None:
                            item.setCheckState(Qt.CheckState.Checked if check_box.isChecked() else Qt.CheckState.Unchecked)  # type: ignore
        super().hidePopup()
