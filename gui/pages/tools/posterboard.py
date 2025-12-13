import webbrowser
import subprocess
import os
import uuid
import traceback
import json
import zipfile

from shutil import make_archive, rmtree, copy2
from PySide6 import QtCore, QtWidgets, QtGui

from ..page import Page
from qt.mainwindow_ui import Ui_Nugget
from gui.dialogs import PBHelpDialog
from gui.custom_qt_elements.multicombobox import MultiComboBox

from tweaks.tweaks import tweaks, TweakID

class PosterboardPage(Page, QtCore.QObject):
    def __init__(self, window, ui: Ui_Nugget):
        super().__init__()
        self.window = window
        self.ui = ui
        self.pb_mainLayout = None
        self.pb_templateLayout = None
        self._shown_video_crop_warning = False

        # set up the dropdown
        self.ui.resetPBDrp = MultiComboBox(self.ui.pbPagePicker, updateAction=self.on_update_picker)
        self.ui.resetPBDrp.noneText = "  " + self.window.noneText
        self.ui.resetPBDrp.setMinimumWidth(165)
        self.ui.resetPBDrp.setMinimumHeight(25)
        self.ui.resetPBDrp.setMaximumWidth(200)
        self.ui.resetPBDrp.setMaximumHeight(30)
        self.ui.resetPBDrp.addItem(self.tr("Collections"), "Collections")
        self.ui.resetPBDrp.addItem(self.tr("Suggested Photos"), "Suggested Photos")
        self.ui.resetPBDrp.addItem(self.tr("Gallery Cache"), "Gallery Cache")
        self.ui.resetPBDrp.lineEdit().setText(self.ui.resetPBDrp.noneText)
        self.ui.resetPBDrp.setStyleSheet("QWidget { background-color: #3b3b3b; border: 2px solid #3b3b3b; border-radius: 5px; }")# QAbstractItemView::indicator:checked { background-color: rgba(0, 0, 255, 0.3); border-radius: 4px; }")
        self.ui.pbPagePicker.layout().addWidget(self.ui.resetPBDrp)

        # Quick access "repair wizard" (no .ui changes required)
        self.ui.pbRepairWizardBtn = QtWidgets.QPushButton(self.tr("Repair Wizard…"), self.ui.pbPagePicker)
        self.ui.pbRepairWizardBtn.clicked.connect(self.on_pbRepairWizardBtn_clicked)
        self.ui.pbPagePicker.layout().addWidget(self.ui.pbRepairWizardBtn)

        self.ui.pbVideoThumbLbl.setText(QtCore.QCoreApplication.tr("Current Thumbnail: {0}").format(self.window.noneText))
        self.ui.pbVideoLbl.setText(QtCore.QCoreApplication.tr("Current Video: {0}").format(self.window.noneText))

    def on_update_picker(self, selected_items: list[str]):
        tweaks[TweakID.PosterBoard].resetModes = selected_items

    def load_page(self):
        self.ui.tendiesPageBtn.clicked.connect(self.on_tendiesPageBtn_clicked)
        self.ui.templatePageBtn.clicked.connect(self.on_templatePageBtn_clicked)
        self.ui.videoPageBtn.clicked.connect(self.on_videoPageBtn_clicked)

        self.ui.importTendiesBtn.clicked.connect(self.on_importTendiesBtn_clicked)

        self.ui.importTemplateBtn.clicked.connect(self.on_importTemplatesBtn_clicked)

        self.ui.chooseThumbBtn.clicked.connect(self.on_chooseThumbBtn_clicked)
        self.ui.chooseVideoBtn.clicked.connect(self.on_chooseVideoBtn_clicked)

        self.ui.caVideoChk.toggled.connect(self.on_caVideoChk_toggled)
        self.ui.reverseLoopChk.toggled.connect(self.on_reverseLoopChk_toggled)
        self.ui.useForegroundChk.toggled.connect(self.on_useForegroundChk_toggled)
        self.ui.calcModeDrp.activated.connect(self.on_calcModeDrp_activated)
        self.ui.exportPBVideoBtn.clicked.connect(self.on_exportPBVideoBtn_clicked)
        
        self.ui.findPBBtn.clicked.connect(self.on_findPBBtn_clicked)
        self.ui.pbHelpBtn.clicked.connect(self.on_pbHelpBtn_clicked)

        # load the pages if needed
        if len(tweaks[TweakID.PosterBoard].tendies) > 0:
            self.load_pb_tendies()
        # if len(tweaks[TweakID.PosterBoard].templates) > 0:
        #     self.load_pb_templates()

    # PosterBoard Repair Wizard
    def on_pbRepairWizardBtn_clicked(self):
        dialog = QtWidgets.QDialog(self.window)
        dialog.setWindowTitle(self.tr("PosterBoard Repair Wizard"))
        dialog.setMinimumWidth(520)

        layout = QtWidgets.QVBoxLayout(dialog)

        intro = QtWidgets.QLabel(
            self.tr(
                "Use this wizard to quickly reset PosterBoard caches and to backup/restore your local PosterBoard setup (tendies + video)."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addSpacing(8)

        # Reset modes
        reset_group = QtWidgets.QGroupBox(self.tr("Reset PosterBoard (recommended for gallery/cache issues)"))
        reset_layout = QtWidgets.QVBoxLayout(reset_group)

        cb_collections = QtWidgets.QCheckBox(self.tr("Collections"))
        cb_suggested = QtWidgets.QCheckBox(self.tr("Suggested Photos"))
        cb_gallery = QtWidgets.QCheckBox(self.tr("Gallery Cache"))

        reset_layout.addWidget(cb_collections)
        reset_layout.addWidget(cb_suggested)
        reset_layout.addWidget(cb_gallery)

        apply_reset_btn = QtWidgets.QPushButton(self.tr("Apply selection to Reset dropdown"))
        reset_layout.addWidget(apply_reset_btn)

        layout.addWidget(reset_group)

        # Backup/restore
        br_group = QtWidgets.QGroupBox(self.tr("Backup / Restore (local setup)"))
        br_layout = QtWidgets.QHBoxLayout(br_group)
        backup_btn = QtWidgets.QPushButton(self.tr("Backup…"))
        restore_btn = QtWidgets.QPushButton(self.tr("Restore…"))
        br_layout.addWidget(backup_btn)
        br_layout.addWidget(restore_btn)
        layout.addWidget(br_group)

        tips = QtWidgets.QLabel(
            self.tr(
                "Tip: Video wallpapers may appear zoomed/cropped depending on resolution/aspect ratio. If it looks wrong, try a different source video or re-export."
            )
        )
        tips.setWordWrap(True)
        layout.addWidget(tips)

        close_btn = QtWidgets.QPushButton(self.tr("Close"))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        def apply_reset_selection():
            self.ui.resetPBDrp.deselectAll()
            indices: list[int] = []
            if cb_collections.isChecked():
                indices.append(0)
            if cb_suggested.isChecked():
                indices.append(1)
            if cb_gallery.isChecked():
                indices.append(2)
            self.ui.resetPBDrp.selectIndices(indices)

        def do_backup():
            try:
                self._backup_posterboard_setup()
            except Exception as e:
                detailsBox = QtWidgets.QMessageBox()
                detailsBox.setIcon(QtWidgets.QMessageBox.Critical)
                detailsBox.setWindowTitle(self.tr("Error"))
                detailsBox.setText(type(e).__name__ + ": " + repr(e))
                detailsBox.setDetailedText("TRACEBACK:\n\n" + str(traceback.format_exc()))
                detailsBox.exec()

        def do_restore():
            try:
                self._restore_posterboard_setup()
                # Refresh UI list for any newly loaded tendies
                self.load_pb_tendies()
            except Exception as e:
                detailsBox = QtWidgets.QMessageBox()
                detailsBox.setIcon(QtWidgets.QMessageBox.Critical)
                detailsBox.setWindowTitle(self.tr("Error"))
                detailsBox.setText(type(e).__name__ + ": " + repr(e))
                detailsBox.setDetailedText("TRACEBACK:\n\n" + str(traceback.format_exc()))
                detailsBox.exec()

        apply_reset_btn.clicked.connect(apply_reset_selection)
        backup_btn.clicked.connect(do_backup)
        restore_btn.clicked.connect(do_restore)

        dialog.exec()

    def _backup_posterboard_setup(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self.window, self.tr("Select Backup Directory"), "", QtWidgets.QFileDialog.ShowDirsOnly
        )
        if not directory:
            return

        base = os.path.join(directory, f"Nugget-PosterBoard-Backup-{uuid.uuid4()}")
        tendies_dir = os.path.join(base, "tendies")
        video_dir = os.path.join(base, "video")
        os.makedirs(tendies_dir, exist_ok=True)
        os.makedirs(video_dir, exist_ok=True)

        # Copy tendies files
        tendies_paths: list[str] = []
        for tendie in tweaks[TweakID.PosterBoard].tendies:
            if not hasattr(tendie, "path"):
                continue
            src = tendie.path
            if not src or not os.path.exists(src):
                continue
            dst = os.path.join(tendies_dir, os.path.basename(src))
            copy2(src, dst)
            tendies_paths.append(os.path.basename(dst))

        # Copy video + thumbnail if present
        video_file = tweaks[TweakID.PosterBoard].videoFile
        video_thumb = tweaks[TweakID.PosterBoard].videoThumbnail
        video_name = None
        thumb_name = None
        if video_file and os.path.exists(video_file):
            video_name = os.path.basename(video_file)
            copy2(video_file, os.path.join(video_dir, video_name))
        if video_thumb and os.path.exists(video_thumb):
            thumb_name = os.path.basename(video_thumb)
            copy2(video_thumb, os.path.join(video_dir, thumb_name))

        manifest = {
            "version": 1,
            "resetModes": list(tweaks[TweakID.PosterBoard].resetModes),
            "tendies": tendies_paths,
            "video": {
                "file": video_name,
                "thumbnail": thumb_name,
                "loop_video": bool(tweaks[TweakID.PosterBoard].loop_video),
                "reverse_video": bool(tweaks[TweakID.PosterBoard].reverse_video),
                "use_foreground": bool(tweaks[TweakID.PosterBoard].use_foreground),
                "calculationMode": str(tweaks[TweakID.PosterBoard].calculationMode),
            },
        }

        with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Zip it up
        make_archive(base, "zip", base)
        backup_path = base + ".nuggetpb"
        os.rename(base + ".zip", backup_path)
        rmtree(base)

        # Reveal in file explorer
        if os.name == "nt":
            subprocess.Popen(f'explorer "{os.path.normpath(backup_path)}"')
        else:
            subprocess.call(["open", "-R", backup_path])

    def _restore_posterboard_setup(self):
        backup_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            self.tr("Select PosterBoard Backup"),
            "",
            self.tr("PosterBoard Backup (*.nuggetpb *.zip)"),
            options=QtWidgets.QFileDialog.ReadOnly,
        )
        if not backup_file:
            return

        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self.window, self.tr("Select Restore Directory"), "", QtWidgets.QFileDialog.ShowDirsOnly
        )
        if not out_dir:
            return

        dest = os.path.join(out_dir, f"Nugget-PosterBoard-Restore-{uuid.uuid4()}")
        os.makedirs(dest, exist_ok=True)

        with zipfile.ZipFile(backup_file, "r") as zf:
            zf.extractall(dest)

        manifest_path = os.path.join(dest, "manifest.json")
        if not os.path.exists(manifest_path):
            raise Exception("manifest.json not found in backup")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Reset modes
        reset_modes = manifest.get("resetModes", [])
        mode_to_index = {"Collections": 0, "Suggested Photos": 1, "Gallery Cache": 2}
        self.ui.resetPBDrp.deselectAll()
        indices = [mode_to_index[m] for m in reset_modes if m in mode_to_index]
        self.ui.resetPBDrp.selectIndices(indices)

        # Tendies
        tendies_folder = os.path.join(dest, "tendies")
        if os.path.isdir(tendies_folder):
            for name in sorted(os.listdir(tendies_folder)):
                if not name.lower().endswith(".tendies"):
                    continue
                tweaks[TweakID.PosterBoard].add_tendie(os.path.join(tendies_folder, name))

        # Video
        video_meta = (manifest.get("video") or {})
        video_folder = os.path.join(dest, "video")
        vfile = video_meta.get("file")
        vthumb = video_meta.get("thumbnail")
        if vfile:
            candidate = os.path.join(video_folder, vfile)
            if os.path.exists(candidate):
                tweaks[TweakID.PosterBoard].videoFile = candidate
                self.ui.pbVideoLbl.setText(
                    QtCore.QCoreApplication.tr("Current Video: {0}").format(candidate)
                )
        if vthumb:
            candidate = os.path.join(video_folder, vthumb)
            if os.path.exists(candidate):
                tweaks[TweakID.PosterBoard].videoThumbnail = candidate
                self.ui.pbVideoThumbLbl.setText(
                    QtCore.QCoreApplication.tr("Current Thumbnail: {0}").format(candidate)
                )

        # Video settings
        tweaks[TweakID.PosterBoard].loop_video = bool(video_meta.get("loop_video", True))
        tweaks[TweakID.PosterBoard].reverse_video = bool(video_meta.get("reverse_video", False))
        tweaks[TweakID.PosterBoard].use_foreground = bool(video_meta.get("use_foreground", False))
        tweaks[TweakID.PosterBoard].calculationMode = str(video_meta.get("calculationMode", "linear"))

        # Reflect settings in UI
        self.ui.caVideoChk.setChecked(bool(tweaks[TweakID.PosterBoard].loop_video))
        self.ui.reverseLoopChk.setChecked(bool(tweaks[TweakID.PosterBoard].reverse_video))
        self.ui.useForegroundChk.setChecked(bool(tweaks[TweakID.PosterBoard].use_foreground))
        self.ui.calcModeDrp.setCurrentIndex(
            0 if tweaks[TweakID.PosterBoard].calculationMode == "linear" else 1
        )

    ## ACTIONS
    def delete_pb_file(self, file, widget):
        if file in tweaks[TweakID.PosterBoard].tendies:
            tweaks[TweakID.PosterBoard].tendies.remove(file)
        widget.deleteLater()

    def create_title_widget(self, tendie, widget: QtWidgets.QWidget) -> QtWidgets.QToolButton:
        titleBtn = QtWidgets.QToolButton(widget)
        titleBtn.setIcon(QtGui.QIcon(tendie.get_icon()))
        titleBtn.setIconSize(QtCore.QSize(20, 20))
        titleBtn.setText(f"   {tendie.name}")
        titleBtn.setStyleSheet("QToolButton {\n    background-color: transparent;\n	icon-size: 20px;\n}")
        titleBtn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        titleBtn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        return titleBtn

    def load_pb_tendies(self):
        if len(tweaks[TweakID.PosterBoard].tendies) == 0:
            return
        
        if self.pb_mainLayout == None:
            # Create scroll layout
            self.pb_mainLayout = QtWidgets.QVBoxLayout()
            self.pb_mainLayout.setContentsMargins(0, 0, 0, 0)
            self.pb_mainLayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
            # Create a QWidget to act as the container for the scroll area
            scrollWidget = QtWidgets.QWidget()

            # Set the main layout (containing all the widgets) on the scroll widget
            scrollWidget.setLayout(self.pb_mainLayout)

            # Create a QScrollArea to hold the content widget (scrollWidget)
            scrollArea = QtWidgets.QScrollArea()
            scrollArea.setWidgetResizable(True)  # Allow the content widget to resize within the scroll area
            scrollArea.setFrameStyle(QtWidgets.QScrollArea.NoFrame)  # Remove the outline from the scroll area

            # Set the scrollWidget as the content widget of the scroll area
            scrollArea.setWidget(scrollWidget)

            # Set the size policy of the scroll area to expand in both directions
            scrollArea.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

            # Set the scroll area as the central widget of the main window
            scrollLayout = QtWidgets.QVBoxLayout()
            scrollLayout.setContentsMargins(0, 0, 0, 0)
            scrollLayout.addWidget(scrollArea)
            self.ui.pbFilesList.setLayout(scrollLayout)

        widgets = {}
        # Iterate through the files
        for tendie in tweaks[TweakID.PosterBoard].tendies:
            if tendie.loaded:
                continue
            widget = QtWidgets.QWidget()
            widgets[tendie] = widget

            # create the icon/label
            titleBtn = self.create_title_widget(tendie=tendie, widget=widget)

            delBtn = QtWidgets.QToolButton(widget)
            delBtn.setIcon(QtGui.QIcon(":/icon/trash.svg"))
            delBtn.clicked.connect(lambda _, file=tendie: (widgets[file].deleteLater(), tweaks[TweakID.PosterBoard].tendies.remove(file)))

            spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
            # main layout
            layout = QtWidgets.QHBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 3)
            layout.addWidget(titleBtn)
            layout.addItem(spacer)
            layout.addWidget(delBtn)
            # Add the widget to the mainLayout
            widget.setLayout(layout)
            self.pb_mainLayout.addWidget(widget)
            tendie.loaded = True

    def load_pb_templates(self):
        if len(tweaks[TweakID.PosterBoard].templates) == 0:
            return
        if self.pb_templateLayout == None:
            # Create scroll layout
            self.pb_templateLayout = QtWidgets.QVBoxLayout()
            self.pb_templateLayout.setContentsMargins(0, 0, 0, 0)
            self.pb_templateLayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
            # Create a QWidget to act as the container for the scroll area
            scrollWidget = QtWidgets.QWidget()

            # Set the main layout (containing all the widgets) on the scroll widget
            scrollWidget.setLayout(self.pb_templateLayout)

            # Create a QScrollArea to hold the content widget (scrollWidget)
            scrollArea = QtWidgets.QScrollArea()
            scrollArea.setWidgetResizable(True)  # Allow the content widget to resize within the scroll area
            scrollArea.setFrameStyle(QtWidgets.QScrollArea.NoFrame)  # Remove the outline from the scroll area

            # Set the scrollWidget as the content widget of the scroll area
            scrollArea.setWidget(scrollWidget)

            # Set the size policy of the scroll area to expand in both directions
            scrollArea.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

            # Set the scroll area as the central widget of the main window
            scrollLayout = QtWidgets.QVBoxLayout()
            scrollLayout.setContentsMargins(0, 0, 0, 0)
            scrollLayout.addWidget(scrollArea)
            self.ui.pbTemplatesList.setLayout(scrollLayout)
        
        widgets = {}
        # Iterate through the templates
        for template in tweaks[TweakID.PosterBoard].templates:
            template.create_ui(self.window, tweaks[TweakID.PosterBoard], widgets, self.pb_templateLayout)

    # PB Pages Selectors
    def on_tendiesPageBtn_clicked(self):
        self.ui.tendiesPageBtn.setChecked(True)
        self.ui.templatePageBtn.setChecked(False)
        self.ui.videoPageBtn.setChecked(False)
        self.ui.pbPages.setCurrentIndex(0)
    def on_templatePageBtn_clicked(self):
        self.ui.tendiesPageBtn.setChecked(False)
        self.ui.templatePageBtn.setChecked(True)
        self.ui.videoPageBtn.setChecked(False)
        self.ui.pbPages.setCurrentIndex(1)
    def on_videoPageBtn_clicked(self):
        self.ui.tendiesPageBtn.setChecked(False)
        self.ui.templatePageBtn.setChecked(False)
        self.ui.videoPageBtn.setChecked(True)
        self.ui.pbPages.setCurrentIndex(2)
    
    # Tendies Page
    def on_importTendiesBtn_clicked(self):
        selected_files, _ = QtWidgets.QFileDialog.getOpenFileNames(self.window, "Select PosterBoard Files", "", "Zip Files (*.tendies)", options=QtWidgets.QFileDialog.ReadOnly)
        self.ui.resetPBDrp.deselectAll()
        if selected_files != None and len(selected_files) > 0:
            # user selected files, add them
            for file in selected_files:
                if not self.window.device_manager.pref_manager.disable_tendies_limit and len(tweaks[TweakID.PosterBoard].tendies) >= 3:
                    # alert that there are too many tendies
                    detailsBox = QtWidgets.QMessageBox()
                    detailsBox.setIcon(QtWidgets.QMessageBox.Critical)
                    detailsBox.setWindowTitle(QtCore.QCoreApplication.tr("Error!"))
                    detailsBox.setText(QtCore.QCoreApplication.tr("You selected too many tendies files! The limit is 3.\n\nThis is for your safety. Please apply the rest separately."))
                    detailsBox.exec()
                    break
                if not tweaks[TweakID.PosterBoard].add_tendie(file):
                    # alert that there are too many
                    detailsBox = QtWidgets.QMessageBox()
                    detailsBox.setIcon(QtWidgets.QMessageBox.Critical)
                    detailsBox.setWindowTitle(QtCore.QCoreApplication.tr("Error!"))
                    detailsBox.setText(QtCore.QCoreApplication.tr("You selected too many descriptors! The limit is 10."))
                    detailsBox.exec()
                    break
            self.load_pb_tendies()

    # Templates Page
    def on_importTemplatesBtn_clicked(self):
        selected_files, _ = QtWidgets.QFileDialog.getOpenFileNames(self.window, "Select Nugget Template Files", "", "Zip Files (*.batter)", options=QtWidgets.QFileDialog.ReadOnly)
        self.ui.resetPBDrp.deselectAll()
        if selected_files != None and len(selected_files) > 0:
            # user selected files, add them
            for file in selected_files:
                if not tweaks[TweakID.PosterBoard].add_template(file, self.window.device_manager.data_singleton.current_device.version):
                    # alert that there are too many
                    detailsBox = QtWidgets.QMessageBox()
                    detailsBox.setIcon(QtWidgets.QMessageBox.Critical)
                    detailsBox.setWindowTitle(QtCore.QCoreApplication.tr("Error!"))
                    detailsBox.setText(QtCore.QCoreApplication.tr("You selected too many descriptors! The limit is 10."))
                    detailsBox.exec()
                    break
            self.load_pb_templates()
    
    # Video Page
    def on_chooseThumbBtn_clicked(self):
        selected_file, _ = QtWidgets.QFileDialog.getOpenFileName(self.window, "Select Image File", "", "Image Files (*.heic)", options=QtWidgets.QFileDialog.ReadOnly)
        self.ui.resetPBDrp.deselectAll()
        if selected_file != None and selected_file != "":
            tweaks[TweakID.PosterBoard].videoThumbnail = selected_file
            self.ui.pbVideoThumbLbl.setText(QtCore.QCoreApplication.tr("Current Thumbnail: {0}").format(selected_file))
        else:
            tweaks[TweakID.PosterBoard].videoThumbnail = None
            self.ui.pbVideoThumbLbl.setText(QtCore.QCoreApplication.tr("Current Thumbnail: {0}").format(self.window.noneText))
    def on_chooseVideoBtn_clicked(self):
        selected_file, _ = QtWidgets.QFileDialog.getOpenFileName(self.window, "Select Video File", "", "Video Files (*.mov *.mp4 *.mkv)", options=QtWidgets.QFileDialog.ReadOnly)
        self.ui.resetPBDrp.deselectAll()
        if selected_file != None and selected_file != "":
            if not self._shown_video_crop_warning:
                self._shown_video_crop_warning = True
                detailsBox = QtWidgets.QMessageBox()
                detailsBox.setIcon(QtWidgets.QMessageBox.Warning)
                detailsBox.setWindowTitle(QtCore.QCoreApplication.tr("Tip"))
                detailsBox.setText(
                    QtCore.QCoreApplication.tr(
                        "Video wallpapers may appear zoomed/cropped depending on resolution/aspect ratio. "
                        "If it looks wrong, try a different source video or re-export."
                    )
                )
                detailsBox.exec()
            tweaks[TweakID.PosterBoard].videoFile = selected_file
            self.ui.pbVideoLbl.setText(QtCore.QCoreApplication.tr("Current Video: {0}").format(selected_file))
            if tweaks[TweakID.PosterBoard].loop_video:
                self.ui.exportPBVideoBtn.show()
        else:
            tweaks[TweakID.PosterBoard].videoFile = None
            self.ui.pbVideoLbl.setText(QtCore.QCoreApplication.tr("Current Video: {0}").format(self.window.noneText))
            self.ui.exportPBVideoBtn.hide()
    def on_caVideoChk_toggled(self, checked: bool):
        tweaks[TweakID.PosterBoard].loop_video = checked
        # hide thumbnail button and label
        if checked:
            self.ui.chooseThumbBtn.hide()
            self.ui.pbVideoThumbLbl.hide()
            self.ui.reverseLoopChk.show()
            self.ui.useForegroundChk.show()
            if tweaks[TweakID.PosterBoard].videoFile != None:
                self.ui.exportPBVideoBtn.show()
        else:
            self.ui.chooseThumbBtn.show()
            self.ui.pbVideoThumbLbl.show()
            self.ui.reverseLoopChk.hide()
            self.ui.useForegroundChk.hide()
            self.ui.exportPBVideoBtn.hide()
    def on_reverseLoopChk_toggled(self, checked: bool):
        tweaks[TweakID.PosterBoard].reverse_video = checked
    def on_useForegroundChk_toggled(self, checked: bool):
        tweaks[TweakID.PosterBoard].use_foreground = checked

    def on_calcModeDrp_activated(self, index: int):
        # 0 = linear, 1 = discrete
        if index == 0:
            tweaks[TweakID.PosterBoard].calculationMode = 'linear'
        elif index == 1:
            tweaks[TweakID.PosterBoard].calculationMode = 'discrete'

    def on_exportPBVideoBtn_clicked(self):
        # Open the directory selection dialog
        directory = QtWidgets.QFileDialog.getExistingDirectory(self.window, "Select Directory", "", QtWidgets.QFileDialog.ShowDirsOnly)
        if directory:
            # export the video
            try:
                # create export folder
                path = os.path.join(directory, f"Nugget-Export-{uuid.uuid4()}")
                tweaks[TweakID.PosterBoard].create_video_loop_files(output_dir=path)
                # make it a zip
                zip_path = path + ".tendies"
                make_archive(path, 'zip', path)
                os.rename(path + '.zip', zip_path)
                rmtree(path)
                # show it in file explorer
                print(f"Created at {zip_path}")
                if os.name == 'nt':
                    subprocess.Popen(f'explorer "{os.path.normpath(zip_path)}"')
                else:
                    subprocess.call(["open", '-R', zip_path])
            except Exception as e:
                # show error
                detailsBox = QtWidgets.QMessageBox()
                detailsBox.setIcon(QtWidgets.QMessageBox.Critical)
                detailsBox.setWindowTitle("Error!")
                detailsBox.setText(type(e).__name__ + ": " + repr(e))
                detailsBox.setDetailedText("TRACEBACK:\n\n" + str(traceback.format_exc()))
                detailsBox.exec()

    def on_findPBBtn_clicked(self):
        webbrowser.open_new_tab("https://cowabun.ga/wallpapers")

    def on_pbHelpBtn_clicked(self):
        dialog = PBHelpDialog()
        dialog.exec()