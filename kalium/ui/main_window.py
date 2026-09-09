"""Kalium main window (PyQt6)."""

from __future__ import annotations

import threading
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread, QUrl, QDir
from PyQt6.QtGui import QColor, QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from kalium import __version__
from kalium.config import AppConfig, ManagedPrefixes
from kalium.deps import check_command_available, ensure_cabextract, ensure_winetricks
from kalium.installers.mo2 import install_mo2, setup_existing_mo2
from kalium.installers.prefix_setup import apply_dpi
from kalium.installers.task import TaskContext
from kalium.logging_utils import init_logger, log_error, log_info, log_warning
from kalium.marketplace import (
    list_plugins,
    install_plugin_into_mo2,
    install_github_zip_into_mo2,
    install_nexus_url_into_mo2,
    PluginInfo,
)
from kalium.nxm import NxmHandler, activate_from_managed, activate_for_install, read_active
from kalium.steam import detect_steam_path_checked, find_steam_protons, get_steam_accounts
from kalium.ui.theme import STYLESHEET
from kalium.updater import check_for_updates, can_self_update




def _app_icon() -> QIcon:
    """Load bundled Kalium icon (works from source and AppImage)."""
    candidates = [
        Path(__file__).resolve().parent.parent / "resources" / "icons" / "kalium.png",
        Path(__file__).resolve().parent.parent.parent / "kalium.png",
        Path(__file__).resolve().parent / "kalium.png",
    ]
    for p in candidates:
        if p.is_file():
            return QIcon(str(p))
    return QIcon()


def _pick_directory(parent: QWidget, title: str, start: str = "") -> str:
    """Directory picker that shows hidden folders (.steam, .local, …)."""
    dlg = QFileDialog(parent, title)
    dlg.setFileMode(QFileDialog.FileMode.Directory)
    dlg.setOption(QFileDialog.Option.ShowDirsOnly, True)
    # Native portals often hide dotfiles; non-native Qt dialog can show them.
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setFilter(QDir.Filter.AllDirs | QDir.Filter.Hidden | QDir.Filter.NoDotAndDotDot)
    if start:
        dlg.setDirectory(start)
    else:
        dlg.setDirectory(str(Path.home()))
    if dlg.exec():
        selected = dlg.selectedFiles()
        if selected:
            return selected[0]
    return ""

class Page(Enum):
    FIRST_RUN = auto()
    GETTING_STARTED = auto()
    MO2 = auto()
    MARKETPLACE = auto()
    DIAGNOSTICS = auto()
    SETTINGS = auto()
    VERSION = auto()


class WorkerSignals(QObject):
    status = pyqtSignal(str)
    log = pyqtSignal(str)
    progress = pyqtSignal(float)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


class InstallWorker(QThread):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        ctx = TaskContext(
            status_callback=lambda m: self.signals.status.emit(m),
            log_callback=lambda m: self.signals.log.emit(m),
            progress_callback=lambda p: self.signals.progress.emit(p),
            cancel_flag=lambda: self._cancel,
        )
        try:
            result = self.fn(*self.args, ctx=ctx, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kalium")
        icon = _app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.setMinimumSize(1200, 700)
        self.config = AppConfig.load()
        self.config.ensure_dirs()
        self.steam_path = detect_steam_path_checked()
        self.steam_detected = self.steam_path is not None
        self.protons = find_steam_protons()
        self.missing_deps: list[str] = []
        if not check_command_available("curl") and not check_command_available("wget"):
            self.missing_deps.append("curl or wget")
        self.worker: Optional[InstallWorker] = None
        self.wizard_step = 0
        self.install_type = "New"
        self._build_ui()
        # Plugin install status must hop to the GUI thread (WorkerSignals)
        self._plugin_bus = WorkerSignals()
        self._plugin_bus.status.connect(self._set_plugin_status)
        self._plugin_bus.error.connect(self._set_plugin_status)
        self._plugin_bus.finished.connect(self._on_plugin_finished)
        self._goto(Page.GETTING_STARTED if self.config.first_run_completed else Page.FIRST_RUN)
        # Background setup
        threading.Thread(target=self._bg_setup, daemon=True).start()

    def _bg_setup(self) -> None:
        try:
            ensure_cabextract()
        except Exception as e:
            log_warning(str(e))
            self.missing_deps.append("cabextract")
        try:
            ensure_winetricks()
        except Exception as e:
            log_warning(str(e))
        try:
            NxmHandler.setup()
        except Exception as e:
            log_warning(f"NXM setup: {e}")

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(180)
        sb = QVBoxLayout(self.sidebar)
        title = QLabel("Kalium")
        title.setObjectName("title")
        sb.addWidget(title)
        self.steam_label = QLabel()
        self.steam_label.setObjectName("muted")
        self.steam_label.setWordWrap(True)
        sb.addWidget(self.steam_label)
        self._update_steam_label()

        self.nav_group = QButtonGroup(self)
        self.nav_buttons: dict[Page, QPushButton] = {}
        for page, text in (
            (Page.GETTING_STARTED, "Getting Started"),
            (Page.MO2, "MO2"),
            (Page.MARKETPLACE, "Marketplace"),
            (Page.DIAGNOSTICS, "Diagnostics"),
            (Page.SETTINGS, "Settings"),
            (Page.VERSION, "Version"),
        ):
            btn = QPushButton(text)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, p=page: self._goto(p))
            self.nav_group.addButton(btn)
            self.nav_buttons[page] = btn
            sb.addWidget(btn)
        sb.addStretch()
        ver = QLabel(f"v{__version__}")
        ver.setObjectName("muted")
        sb.addWidget(ver)
        layout.addWidget(self.sidebar)

        # Content
        content = QWidget()
        cl = QVBoxLayout(content)
        self.install_banner = QFrame()
        self.install_banner.setVisible(False)
        ib = QVBoxLayout(self.install_banner)
        self.install_status = QLabel("Installation in Progress...")
        self.install_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.install_progress = QProgressBar()
        self.install_progress.setRange(0, 100)
        ib.addWidget(self.install_status)
        ib.addWidget(self.install_progress)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("danger")
        cancel.clicked.connect(self._cancel_install)
        ib.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.install_banner)

        self.stack = QStackedWidget()
        self.pages: dict[Page, QWidget] = {}
        self.pages[Page.FIRST_RUN] = self._page_first_run()
        self.pages[Page.GETTING_STARTED] = self._page_getting_started()
        self.pages[Page.MO2] = self._page_mo2()
        self.pages[Page.MARKETPLACE] = self._page_marketplace()
        self.pages[Page.DIAGNOSTICS] = self._page_diagnostics()
        self.pages[Page.SETTINGS] = self._page_settings()
        self.pages[Page.VERSION] = self._page_version()
        for p in Page:
            self.stack.addWidget(self.pages[p])
        cl.addWidget(self.stack)
        layout.addWidget(content, stretch=1)

    def _update_steam_label(self) -> None:
        if self.steam_detected:
            self.steam_label.setText(f"Steam: {self.steam_path}\nProton: {len(self.protons)} found")
        else:
            self.steam_label.setText("STEAM NOT DETECTED")
            self.steam_label.setObjectName("error")

    def _goto(self, page: Page) -> None:
        self.stack.setCurrentWidget(self.pages[page])
        for p, btn in self.nav_buttons.items():
            btn.setChecked(p == page)
        self.sidebar.setVisible(page != Page.FIRST_RUN)
        if page == Page.SETTINGS:
            self._refresh_prefixes()
            self._refresh_nxm_instance_list()
        if page == Page.GETTING_STARTED:
            self._refresh_nxm_status_widgets()
        if page == Page.MARKETPLACE:
            self._refresh_plugins()
        if page == Page.DIAGNOSTICS:
            self._run_diagnostics_ui()

    # ----- Pages -----
    def _wrap_scroll(self, inner: QWidget) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        return scroll

    def _page_first_run(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t = QLabel("Welcome to Kalium!")
        t.setObjectName("title")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        s = QLabel("Linux Modding Helper — by Bobby Comet\nInspired by the archived NaK project.")
        s.setObjectName("muted")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(s)
        info = QLabel(
            "Kalium installs MO2 as a non-Steam game, configures Proton,\n"
            "installs Windows dependencies, registers games, and handles NXM links."
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(info)
        steam_ok = QLabel(
            f"Steam: {'OK' if self.steam_detected else 'NOT FOUND'}  |  "
            f"Proton: {'OK (' + str(len(self.protons)) + ')' if self.protons else 'NOT FOUND'}"
        )
        steam_ok.setObjectName("success" if self.steam_detected and self.protons else "error")
        steam_ok.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(steam_ok)
        btn = QPushButton("Get Started")
        btn.setObjectName("primary")
        btn.clicked.connect(self._finish_first_run)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return self._wrap_scroll(w)

    def _finish_first_run(self) -> None:
        self.config.first_run_completed = True
        self.config.save()
        self._goto(Page.GETTING_STARTED)

    def _page_getting_started(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        t = QLabel("Welcome to Kalium!")
        t.setObjectName("section")
        lay.addWidget(t)
        lay.addWidget(QLabel("Kalium makes it easy to run Windows modding tools on Linux using Proton."))
        btn = QPushButton("Install MO2")
        btn.setObjectName("primary")
        btn.clicked.connect(lambda: self._goto(Page.MO2))
        lay.addWidget(btn)
        lay.addWidget(QLabel("• Create a Steam shortcut for MO2\n• Configure Proton automatically\n• Install Windows dependencies\n• NXM + Collections plugin support"))
        self.gs_nxm_status = QLabel(self._nxm_status_text())
        self.gs_nxm_status.setWordWrap(True)
        self.gs_nxm_status.setStyleSheet(
            "padding: 8px; border-radius: 6px; background: #1e2430; margin-top: 8px;"
        )
        lay.addWidget(self.gs_nxm_status)
        gs_nxm_btn = QPushButton("Open NXM settings")
        gs_nxm_btn.clicked.connect(lambda: self._goto(Page.SETTINGS))
        lay.addWidget(gs_nxm_btn)

        lay.addStretch()
        return self._wrap_scroll(w)

    def _page_mo2(self) -> QWidget:
        w = QWidget()
        self.mo2_layout = QVBoxLayout(w)
        lbl = QLabel("MO2 Installation")
        lbl.setObjectName("section")
        self.mo2_layout.addWidget(lbl)
        self.mo2_stack = QStackedWidget()
        self.mo2_layout.addWidget(self.mo2_stack)
        # Step 0 selection
        s0 = QWidget()
        l0 = QVBoxLayout(s0)
        l0.addWidget(QLabel("Install or set up an existing MO2 installation."))
        row = QHBoxLayout()
        b_new = QPushButton("Install New MO2")
        b_new.setObjectName("primary")
        b_new.clicked.connect(lambda: self._mo2_select("New"))
        b_ex = QPushButton("Setup Existing MO2")
        b_ex.clicked.connect(lambda: self._mo2_select("Existing"))
        row.addWidget(b_new)
        row.addWidget(b_ex)
        l0.addLayout(row)
        self.mo2_stack.addWidget(s0)
        # Step 1 name
        s1 = QWidget()
        l1 = QVBoxLayout(s1)
        l1.addWidget(QLabel("Step 1: Instance Name"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My MO2 Instance")
        l1.addWidget(self.name_edit)
        r1 = QHBoxLayout()
        back1 = QPushButton("Back")
        back1.clicked.connect(lambda: self.mo2_stack.setCurrentIndex(0))
        next1 = QPushButton("Next")
        next1.setObjectName("primary")
        next1.clicked.connect(self._mo2_to_path)
        r1.addWidget(back1)
        r1.addWidget(next1)
        l1.addLayout(r1)
        self.mo2_stack.addWidget(s1)
        # Step 2 path
        s2 = QWidget()
        l2 = QVBoxLayout(s2)
        l2.addWidget(QLabel("Step 2: Install Location"))
        row2 = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/home/user/MO2")
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_path)
        row2.addWidget(self.path_edit)
        row2.addWidget(browse)
        l2.addLayout(row2)
        self.force_check = QCheckBox("I acknowledge this folder is not empty")
        l2.addWidget(self.force_check)
        r2 = QHBoxLayout()
        back2 = QPushButton("Back")
        back2.clicked.connect(lambda: self.mo2_stack.setCurrentIndex(1))
        next2 = QPushButton("Next")
        next2.setObjectName("primary")
        next2.clicked.connect(self._mo2_to_game)
        r2.addWidget(back2)
        r2.addWidget(next2)
        l2.addLayout(r2)
        self.mo2_stack.addWidget(s2)
        # Step 3 managed game (required for portable instance ini)
        s_game = QWidget()
        lg = QVBoxLayout(s_game)
        lg.addWidget(QLabel("Step 3: Game to manage"))
        lg.addWidget(
            QLabel(
                "Portable MO2 needs gameName + gamePath in ModOrganizer.ini. "
                "Pick a detected install or a known game and browse to its folder."
            )
        )
        self.game_list = QListWidget()
        self._mo2_game_choices = []
        self.game_list.currentRowChanged.connect(self._on_mo2_game_row)
        lg.addWidget(self.game_list)
        refresh_games = QPushButton("Refresh detected games")
        refresh_games.clicked.connect(self._refresh_mo2_game_list)
        lg.addWidget(refresh_games)
        lg.addWidget(QLabel("Game folder (contains the game .exe):"))
        grow = QHBoxLayout()
        self.game_path_edit = QLineEdit()
        self.game_path_edit.setPlaceholderText("/path/to/Skyrim Special Edition")
        gbrowse = QPushButton("Browse")
        gbrowse.clicked.connect(self._browse_game_path)
        grow.addWidget(self.game_path_edit)
        grow.addWidget(gbrowse)
        lg.addLayout(grow)
        self.game_skip = QCheckBox("Skip for now (not recommended — instance may fail to open)")
        lg.addWidget(self.game_skip)
        rg = QHBoxLayout()
        back_g = QPushButton("Back")
        back_g.clicked.connect(lambda: self.mo2_stack.setCurrentIndex(2))
        next_g = QPushButton("Next")
        next_g.setObjectName("primary")
        next_g.clicked.connect(self._mo2_to_proton)
        rg.addWidget(back_g)
        rg.addWidget(next_g)
        lg.addLayout(rg)
        self.mo2_stack.addWidget(s_game)
        # Step 4 proton
        s3 = QWidget()
        l3 = QVBoxLayout(s3)
        l3.addWidget(QLabel("Step 4: Select Proton Version"))
        self.proton_list = QListWidget()
        for p in self.protons:
            self.proton_list.addItem(QListWidgetItem(p.name))
        if self.protons:
            self.proton_list.setCurrentRow(0)
        l3.addWidget(self.proton_list)
        self.usvfs_check = QCheckBox(
            "Update USVFS to 0.5.7.2 (recommended — fixes slow launches on Wine/Proton 10.20+)"
        )
        self.usvfs_check.setChecked(True)
        self.usvfs_check.setToolTip(
            "MO2 2.5.2 ships usvfs 0.5.6.x, which can duplicate virtual folders on "
            "Wine 10.20–11.0-rc3 and roughly triple Skyrim SE boot time. "
            "0.5.7.2 from upstream fixes this. Uncheck to keep the stock binaries."
        )
        l3.addWidget(self.usvfs_check)
        r3 = QHBoxLayout()
        back3 = QPushButton("Back")
        back3.clicked.connect(lambda: self.mo2_stack.setCurrentIndex(3))
        start = QPushButton("Start Installation")
        start.setObjectName("primary")
        start.clicked.connect(self._start_mo2_install)
        r3.addWidget(back3)
        r3.addWidget(start)
        l3.addLayout(r3)
        self.mo2_stack.addWidget(s3)
        # Step 5 done
        s4 = QWidget()
        l4 = QVBoxLayout(s4)
        self.done_label = QLabel("Installation Successful!")
        self.done_label.setObjectName("success")
        self.done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l4.addWidget(self.done_label)
        self.done_detail = QLabel("Restart Steam and launch MO2 from Non-Steam Games.")
        self.done_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l4.addWidget(self.done_detail)
        again = QPushButton("Return to Menu")
        again.setObjectName("primary")
        again.clicked.connect(lambda: self.mo2_stack.setCurrentIndex(0))
        l4.addWidget(again, alignment=Qt.AlignmentFlag.AlignCenter)
        self.mo2_stack.addWidget(s4)
        return self._wrap_scroll(w)

    def _mo2_select(self, kind: str) -> None:
        self.install_type = kind
        self.mo2_stack.setCurrentIndex(1)

    def _mo2_to_path(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Kalium", "Please enter an instance name.")
            return
        self.mo2_stack.setCurrentIndex(2)

    def _browse_path(self) -> None:
        d = _pick_directory(self, "Select folder")
        if d:
            self.path_edit.setText(d)

    def _mo2_to_game(self) -> None:
        if not self.path_edit.text().strip():
            QMessageBox.warning(self, "Kalium", "Please choose an install path.")
            return
        self._refresh_mo2_game_list()
        self.mo2_stack.setCurrentIndex(3)

    def _refresh_mo2_game_list(self) -> None:
        self.game_list.clear()
        self._mo2_game_choices = []
        try:
            from kalium.installers.mo2_game import detect_managed_game_choices

            self._mo2_game_choices = detect_managed_game_choices()
        except Exception as e:
            log_warning(f"Game list failed: {e}")
            try:
                from kalium.installers.mo2_game import list_known_game_templates

                self._mo2_game_choices = list_known_game_templates()
            except Exception:
                self._mo2_game_choices = []
        for c in self._mo2_game_choices:
            self.game_list.addItem(c.display_name)
        if self._mo2_game_choices:
            self.game_list.setCurrentRow(0)

    def _on_mo2_game_row(self, row: int) -> None:
        if row < 0 or row >= len(getattr(self, "_mo2_game_choices", [])):
            return
        choice = self._mo2_game_choices[row]
        if choice.install_path:
            self.game_path_edit.setText(str(choice.install_path))

    def _browse_game_path(self) -> None:
        d = _pick_directory(self, "Select game install folder")
        if d:
            self.game_path_edit.setText(d)

    def _mo2_to_proton(self) -> None:
        if not self.game_skip.isChecked():
            row = self.game_list.currentRow()
            if row < 0 or row >= len(getattr(self, "_mo2_game_choices", [])):
                QMessageBox.warning(
                    self,
                    "Kalium",
                    "Select a game from the list (or check Skip for now).",
                )
                return
            gpath = self.game_path_edit.text().strip()
            if not gpath or not Path(gpath).is_dir():
                QMessageBox.warning(
                    self,
                    "Kalium",
                    "Set a valid game folder (Browse to the folder that contains the game .exe).",
                )
                return
        self.mo2_stack.setCurrentIndex(4)

    def _start_mo2_install(self) -> None:
        if not self.protons:
            QMessageBox.warning(self, "Kalium", "No Proton 10+ found.")
            return
        idx = max(0, self.proton_list.currentRow())
        proton = self.protons[idx]
        name = self.name_edit.text().strip()
        path = Path(self.path_edit.text().strip())
        update_usvfs = self.usvfs_check.isChecked() if hasattr(self, "usvfs_check") else True
        game_name = None
        game_path = None
        if not (hasattr(self, "game_skip") and self.game_skip.isChecked()):
            row = self.game_list.currentRow()
            if 0 <= row < len(getattr(self, "_mo2_game_choices", [])):
                game_name = self._mo2_game_choices[row].mo2_game_name
            gpath = self.game_path_edit.text().strip()
            if gpath:
                game_path = Path(gpath)
        self.install_banner.setVisible(True)
        if self.install_type == "New":
            self.worker = InstallWorker(
                install_mo2,
                name,
                path,
                proton,
                update_usvfs=update_usvfs,
                game_name=game_name,
                game_path=game_path,
            )
        else:
            self.worker = InstallWorker(
                setup_existing_mo2,
                name,
                path,
                proton,
                update_usvfs=update_usvfs,
                game_name=game_name,
                game_path=game_path,
            )
        self.worker.signals.status.connect(self.install_status.setText)
        self.worker.signals.progress.connect(lambda p: self.install_progress.setValue(int(p * 100)))
        self.worker.signals.finished.connect(self._on_install_done)
        self.worker.signals.error.connect(self._on_install_error)
        self.worker.start()

    def _cancel_install(self) -> None:
        if self.worker:
            self.worker.cancel()

    def _on_install_done(self, result) -> None:
        self.install_banner.setVisible(False)
        self.done_label.setText("Installation Successful!")
        self.done_label.setObjectName("success")
        nxm_line = self._nxm_status_text()
        self.done_detail.setText(
            f"AppID {result.app_id}\nPrefix: {result.prefix_path}\n\n"
            f"{nxm_line}\n\n"
            "Fully exit Steam (Steam → Exit), wait a few seconds, then open Steam again "
            "so the non-Steam game appears.\n\n"
            "In your browser, choose “Kalium NXM Handler” for nxm:// links "
            "(not the main Kalium window)."
        )
        self.mo2_stack.setCurrentIndex(5)
        self._refresh_nxm_status_widgets()

    def _on_install_error(self, msg: str) -> None:
        self.install_banner.setVisible(False)
        self.done_label.setText("Installation Failed")
        self.done_label.setObjectName("error")
        self.done_detail.setText(msg)
        self.mo2_stack.setCurrentIndex(5)
        log_error(msg)

    def _page_marketplace(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        t = QLabel("Marketplace")
        t.setObjectName("section")
        lay.addWidget(t)
        lay.addWidget(
            QLabel(
                "Install MO2 plugins from Nexus (API key) or from a GitHub release .zip URL."
            )
        )

        # --- Nexus API key ---
        lay.addWidget(QLabel("Nexus API key"))
        key_row = QHBoxLayout()
        self.nexus_key_edit = QLineEdit(self.config.nexus_api_key)
        self.nexus_key_edit.setPlaceholderText("Paste your Nexus API key here")
        self.nexus_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self.nexus_key_edit)
        save_key = QPushButton("Save Key")
        save_key.clicked.connect(self._save_nexus_key)
        key_row.addWidget(save_key)
        lay.addLayout(key_row)

        api_link = QLabel(
            '<a href="https://www.nexusmods.com/settings/api-keys">'
            "Get a free Nexus API key → nexusmods.com/settings/api-keys</a>"
        )
        api_link.setOpenExternalLinks(True)
        api_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        lay.addWidget(api_link)
        tip = QLabel(
            "Required for Nexus-hosted plugins (e.g. MO2 Collections Support #1541). "
            "Keep your key private."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #9aa0a6;")
        lay.addWidget(tip)

        # --- MO2 path ---
        lay.addWidget(QLabel("MO2 install folder (contains ModOrganizer.exe)"))
        path_row = QHBoxLayout()
        self.mo2_plugin_path = QLineEdit()
        self.mo2_plugin_path.setPlaceholderText("/home/user/MO2")
        path_row.addWidget(self.mo2_plugin_path)
        browse = QPushButton("Browse MO2")
        browse.clicked.connect(self._browse_mo2_for_plugin)
        path_row.addWidget(browse)
        lay.addLayout(path_row)

        # --- Built-in / registry plugins (Nexus etc.) ---
        lay.addWidget(QLabel("Nexus / catalog plugins"))
        self.plugin_list = QListWidget()
        self.plugin_list.currentRowChanged.connect(self._on_plugin_selected)
        lay.addWidget(self.plugin_list)
        self.plugin_detail = QLabel("")
        self.plugin_detail.setWordWrap(True)
        lay.addWidget(self.plugin_detail)
        install_btn = QPushButton("Install Selected Plugin into MO2")
        install_btn.clicked.connect(self._install_selected_plugin)
        lay.addWidget(install_btn)

        # --- Any Nexus mod page URL ---
        sep_nx = QFrame()
        sep_nx.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep_nx)
        nx_title = QLabel("Install from Nexus mod link")
        nx_title.setObjectName("section")
        lay.addWidget(nx_title)
        nx_help = QLabel(
            "Paste any Nexus Mods page URL for an MO2 plugin. Kalium resolves the latest "
            "file via the Nexus API (requires your API key above) and extracts it into "
            "MO2/plugins/.\n"
            "Examples:\n"
            "https://www.nexusmods.com/site/mods/1899\n"
            "https://www.nexusmods.com/skyrimspecialedition/mods/47325"
        )
        nx_help.setWordWrap(True)
        nx_help.setStyleSheet("color: #9aa0a6;")
        lay.addWidget(nx_help)
        self.nexus_mod_url = QLineEdit()
        self.nexus_mod_url.setPlaceholderText(
            "https://www.nexusmods.com/<game>/mods/<id>"
        )
        lay.addWidget(self.nexus_mod_url)
        nx_btn = QPushButton("Download & Install Nexus Plugin")
        nx_btn.clicked.connect(self._install_nexus_url_plugin)
        lay.addWidget(nx_btn)

        # --- GitHub zip URL ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)
        gh_title = QLabel("Install from GitHub release .zip")
        gh_title.setObjectName("section")
        lay.addWidget(gh_title)
        gh_help = QLabel(
            "Right-click a release asset on GitHub → Copy link address, then paste it below. "
            "Example:\n"
            "https://github.com/Kezyma/ModOrganizer-Plugins/releases/download/"
            "listexporter/listexporter.2.0.0.zip\n"
            "Kalium downloads the zip and extracts the plugin folder into MO2/plugins/."
        )
        gh_help.setWordWrap(True)
        gh_help.setStyleSheet("color: #9aa0a6;")
        lay.addWidget(gh_help)
        self.github_zip_url = QLineEdit()
        self.github_zip_url.setPlaceholderText(
            "https://github.com/.../releases/download/.../plugin.zip"
        )
        lay.addWidget(self.github_zip_url)
        gh_btn = QPushButton("Download & Install GitHub Plugin")
        gh_btn.clicked.connect(self._install_github_plugin)
        lay.addWidget(gh_btn)

        self.plugin_status = QLabel("")
        self.plugin_status.setWordWrap(True)
        lay.addWidget(self.plugin_status)

        self._plugins: list[PluginInfo] = []
        self._refresh_plugins()
        return self._wrap_scroll(w)

    def _refresh_plugins(self) -> None:
        self.plugin_list.clear()
        self._plugins = list_plugins()
        for p in self._plugins:
            self.plugin_list.addItem(f"{p.name} — {p.description[:80]}")

    def _on_plugin_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._plugins):
            return
        p = self._plugins[row]
        self.plugin_detail.setText(
            f"{p.name}\nAuthor: {p.author}\nVersion: {p.version}\nSource: {p.source}\n\n{p.description}"
        )

    def _browse_mo2_for_plugin(self) -> None:
        d = _pick_directory(self, "Select MO2 folder")
        if d:
            self.mo2_plugin_path.setText(d)

    def _save_nexus_key(self) -> None:
        self.config.nexus_api_key = self.nexus_key_edit.text().strip()
        self.config.save()
        QMessageBox.information(self, "Kalium", "Nexus API key saved.")

    def _set_plugin_status(self, msg: str) -> None:
        if hasattr(self, "plugin_status") and self.plugin_status is not None:
            self.plugin_status.setText(msg)

    def _on_plugin_finished(self, result) -> None:
        if result is None:
            return
        if hasattr(result, "message"):
            self._set_plugin_status(f"✓ {result.message}")
        else:
            self._set_plugin_status(f"✓ Installed into {result}")

    def _install_selected_plugin(self) -> None:
        row = self.plugin_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Kalium", "Select a plugin.")
            return
        mo2 = Path(self.mo2_plugin_path.text().strip())
        if not (mo2 / "ModOrganizer.exe").exists():
            QMessageBox.warning(self, "Kalium", "ModOrganizer.exe not found at that path.")
            return
        plugin = self._plugins[row]
        self.plugin_status.setText(f"Installing {plugin.name}…")
        key = self.nexus_key_edit.text().strip() or self.config.nexus_api_key

        def work():
            try:
                result = install_plugin_into_mo2(plugin, mo2, api_key=key)
                msg = getattr(result, "message", None) or (
                    f"Installed {plugin.name} into {mo2 / 'plugins'}"
                )
                self._plugin_bus.status.emit(f"✓ {msg}")
                self._plugin_bus.finished.emit(result)
            except Exception as e:
                self._plugin_bus.error.emit(f"✗ {plugin.name} failed: {e}")
                log_error(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _install_github_plugin(self) -> None:
        url = self.github_zip_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Kalium", "Paste a GitHub release .zip URL first.")
            return
        mo2 = Path(self.mo2_plugin_path.text().strip())
        if not (mo2 / "ModOrganizer.exe").exists():
            QMessageBox.warning(self, "Kalium", "ModOrganizer.exe not found at that path.")
            return
        self.plugin_status.setText("Downloading GitHub plugin…")

        def work():
            try:
                dest = install_github_zip_into_mo2(url, mo2)
                msg = getattr(dest, "message", None) or f"Installed into {dest}"
                self._plugin_bus.status.emit(f"✓ {msg}")
                self._plugin_bus.finished.emit(dest)
            except Exception as e:
                self._plugin_bus.error.emit(f"✗ GitHub plugin failed: {e}")
                log_error(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _install_nexus_url_plugin(self) -> None:
        url = self.nexus_mod_url.text().strip() if hasattr(self, "nexus_mod_url") else ""
        if not url:
            QMessageBox.warning(
                self,
                "Kalium",
                "Paste a Nexus Mods page URL first.\n"
                "Example: https://www.nexusmods.com/site/mods/1899",
            )
            return
        mo2 = Path(self.mo2_plugin_path.text().strip())
        if not (mo2 / "ModOrganizer.exe").exists():
            QMessageBox.warning(self, "Kalium", "ModOrganizer.exe not found at that path.")
            return
        key = self.nexus_key_edit.text().strip() or self.config.nexus_api_key
        if not key:
            QMessageBox.warning(
                self,
                "Kalium",
                "A Nexus API key is required to download from Nexus.\n"
                "Paste it above and click Save Key.",
            )
            return
        self.plugin_status.setText("Resolving & downloading Nexus plugin…")

        def work():
            try:
                dest = install_nexus_url_into_mo2(url, mo2, api_key=key)
                msg = getattr(dest, "message", None) or f"Installed Nexus plugin into {dest}"
                self._plugin_bus.status.emit(f"✓ {msg}")
                self._plugin_bus.finished.emit(dest)
            except Exception as e:
                self._plugin_bus.error.emit(f"✗ Nexus plugin failed: {e}")
                log_error(str(e))

        threading.Thread(target=work, daemon=True).start()


    def _page_diagnostics(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        t = QLabel("Diagnostics")
        t.setObjectName("section")
        lay.addWidget(t)
        help_lbl = QLabel(
            "Health check for Steam, libraries, Skyrim SE, every managed MO2 instance "
            "(ModOrganizer.exe, USVFS, LOOT, gameName), Proton, and NXM. "
            "If auto-detect misses your install, browse to the MO2 folder below."
        )
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet("color: #9aa0a6;")
        lay.addWidget(help_lbl)

        lay.addWidget(QLabel("MO2 folder (optional — contains ModOrganizer.exe):"))
        mo2_row = QHBoxLayout()
        self.diag_mo2_path = QLineEdit()
        self.diag_mo2_path.setPlaceholderText("/path/to/MO2 or …/ModOrganizer.exe")
        mo2_browse = QPushButton("Browse MO2")
        mo2_browse.clicked.connect(self._browse_diag_mo2)
        mo2_row.addWidget(self.diag_mo2_path)
        mo2_row.addWidget(mo2_browse)
        lay.addLayout(mo2_row)

        self.diag_summary = QLabel("Click Refresh to run checks.")
        self.diag_summary.setObjectName("muted")
        self.diag_summary.setWordWrap(True)
        lay.addWidget(self.diag_summary)

        self.diag_list = QListWidget()
        self.diag_list.setMinimumHeight(280)
        lay.addWidget(self.diag_list)

        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("primary")
        refresh.clicked.connect(self._run_diagnostics_ui)
        save = QPushButton("Save report for GitHub")
        save.clicked.connect(self._save_diagnostics_report)
        row.addWidget(refresh)
        row.addWidget(save)
        lay.addLayout(row)

        self.diag_path_label = QLabel("")
        self.diag_path_label.setWordWrap(True)
        self.diag_path_label.setStyleSheet("color: #9aa0a6;")
        lay.addWidget(self.diag_path_label)
        lay.addStretch()
        return self._wrap_scroll(w)

    def _browse_diag_mo2(self) -> None:
        d = _pick_directory(self, "MO2 folder (contains ModOrganizer.exe)")
        if d:
            self.diag_mo2_path.setText(d)

    def _diag_extra_mo2_paths(self) -> list:
        paths = []
        if hasattr(self, "diag_mo2_path"):
            raw = self.diag_mo2_path.text().strip()
            if raw:
                paths.append(Path(raw))
        # Also include managed install paths from Settings list if loaded
        for attr in ("_prefixes", "_nxm_instances"):
            for p in getattr(self, attr, None) or []:
                try:
                    ip = getattr(p, "install_path", None)
                    if ip:
                        paths.append(Path(ip))
                except Exception:
                    pass
        return paths

    def _run_diagnostics_ui(self) -> None:
        if not hasattr(self, "diag_list"):
            return
        self.diag_list.clear()
        self.diag_summary.setText("Running checks…")
        try:
            from kalium.diagnostics import run_diagnostics

            report = run_diagnostics(extra_mo2_paths=self._diag_extra_mo2_paths())
            self._last_diag_report = report
            for c in report.checks:
                item = QListWidgetItem(c.line())
                if c.status.value == "ok":
                    item.setForeground(QColor("#64c864"))
                elif c.status.value == "warn":
                    item.setForeground(QColor("#e6b800"))
                elif c.status.value == "fail":
                    item.setForeground(QColor("#ff6464"))
                self.diag_list.addItem(item)
            self.diag_summary.setText(report.summary)
            if report.overall_ok() and "healthy" in report.summary.lower():
                self.diag_summary.setObjectName("success")
            elif not report.overall_ok():
                self.diag_summary.setObjectName("error")
            else:
                self.diag_summary.setObjectName("muted")
            self.diag_summary.style().unpolish(self.diag_summary)
            self.diag_summary.style().polish(self.diag_summary)
        except Exception as e:
            self.diag_summary.setText(f"Diagnostics failed: {e}")
            log_error(str(e))

    def _save_diagnostics_report(self) -> None:
        try:
            from kalium.diagnostics import run_diagnostics, write_report

            report = getattr(self, "_last_diag_report", None) or run_diagnostics(
                extra_mo2_paths=self._diag_extra_mo2_paths()
            )
            path = write_report(report)
            self._last_diag_report = report
            msg = f"Report saved to:\n{path}\n\nPaste that file into a GitHub issue."
            if hasattr(self, "diag_path_label"):
                self.diag_path_label.setText(f"Report: {path}")
            QMessageBox.information(self, "Kalium Diagnostics", msg)
        except Exception as e:
            QMessageBox.warning(self, "Kalium", f"Could not write report: {e}")
            log_error(str(e))

    def _page_settings(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        t = QLabel("Settings")
        t.setObjectName("section")
        lay.addWidget(t)
        self.prefix_list = QListWidget()
        lay.addWidget(self.prefix_list)
        row = QHBoxLayout()
        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(self._open_prefix_folder)
        del_btn = QPushButton("Delete Prefix")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete_prefix)
        usvfs_btn = QPushButton("Update USVFS 0.5.7.2")
        usvfs_btn.setToolTip(
            "Overwrite usvfs DLLs/exes in the selected MO2 folder with upstream 0.5.7.2. "
            "Fixes virtual-folder duplication and slow boots on Wine/Proton 10.20+. "
            "Close MO2 before running."
        )
        usvfs_btn.clicked.connect(self._update_usvfs_for_selected)
        vfs_mem_btn = QPushButton("Set VFS max_memory = 2 GB")
        vfs_mem_btn.setToolTip(
            "Write [vfs] max_memory=2147483648 into ModOrganizer.ini for the selected "
            "instance. Prevents USVFS shared-memory tree exhaustion under Wine/Proton. "
            "Close MO2 before applying; requires ModOrganizer.ini (launch MO2 once first)."
        )
        vfs_mem_btn.clicked.connect(self._set_vfs_max_memory_for_selected)
        loot_btn = QPushButton("Install LOOT")
        loot_btn.setToolTip(
            "Download portable LOOT, register LOOT.exe with --game= in arguments, "
            "then run winetricks -q vcrun2022 in this instance’s Wine prefix. "
            "Close MO2 before running."
        )
        loot_btn.clicked.connect(self._install_loot_for_selected)
        vcrun_btn = QPushButton("Ensure vcrun2022")
        vcrun_btn.setToolTip(
            "Run: WINEPREFIX=<this instance pfx> winetricks -q vcrun2022\n"
            "Targets the managed Proton prefix so LOOT can start. Safe to re-run."
        )
        vcrun_btn.clicked.connect(self._ensure_vcrun_for_selected)
        row.addWidget(open_btn)
        row.addWidget(del_btn)
        row.addWidget(usvfs_btn)
        row.addWidget(vfs_mem_btn)
        row.addWidget(loot_btn)
        row.addWidget(vcrun_btn)
        lay.addLayout(row)
        self.usvfs_status = QLabel("")
        self.usvfs_status.setWordWrap(True)
        lay.addWidget(self.usvfs_status)
        # Steam path override
        lay.addWidget(QLabel("Custom Steam path (optional):"))
        steam_row = QHBoxLayout()
        self.custom_steam = QLineEdit(self.config.custom_steam_path)
        steam_browse = QPushButton("Browse")
        steam_browse.clicked.connect(self._browse_steam)
        steam_save = QPushButton("Save")
        steam_save.clicked.connect(self._save_steam_path)
        steam_row.addWidget(self.custom_steam)
        steam_row.addWidget(steam_browse)
        steam_row.addWidget(steam_save)
        lay.addLayout(steam_row)

        # --- NXM handler ---
        nxm_title = QLabel("NXM download handler")
        nxm_title.setObjectName("section")
        lay.addWidget(nxm_title)

        self.nxm_banner = QLabel(self._nxm_status_text())
        self.nxm_banner.setWordWrap(True)
        self.nxm_banner.setObjectName("status")
        self.nxm_banner.setStyleSheet(
            "padding: 10px; border-radius: 8px; background: #1e2430; border: 1px solid #3d4a63;"
        )
        lay.addWidget(self.nxm_banner)
        self.nxm_status = self.nxm_banner  # alias used by older handlers

        nxm_help = QLabel(
            "When NXM is on, Nexus “Download with Manager” links open in the MO2 instance below "
            "(same Proton prefix). This is turned on automatically when you finish MO2 setup.\n\n"
            "First time in the browser: choose “Kalium NXM Handler”, not the main Kalium app."
        )
        nxm_help.setWordWrap(True)
        nxm_help.setStyleSheet("color: #9aa0a6;")
        lay.addWidget(nxm_help)

        lay.addWidget(QLabel("Select instance to receive NXM downloads:"))
        self.nxm_instance_list = QListWidget()
        self.nxm_instance_list.setMinimumHeight(100)
        lay.addWidget(self.nxm_instance_list)

        nxm_row = QHBoxLayout()
        self.nxm_toggle_btn = QPushButton("Turn NXM on for selected instance")
        self.nxm_toggle_btn.clicked.connect(self._enable_nxm)
        reg_nxm = QPushButton("Re-register browser handler")
        reg_nxm.clicked.connect(self._reregister_nxm)
        nxm_row.addWidget(self.nxm_toggle_btn)
        nxm_row.addWidget(reg_nxm)
        lay.addLayout(nxm_row)

        # Multi-game Steam depot backpatch
        bp_title = QLabel("Game backpatch (Steam depots)")
        bp_title.setObjectName("section")
        lay.addWidget(bp_title)
        bp_help = QLabel(
            "Pin a game to a historical Steam depot build (downpatch). "
            "Pick the game, then the target version — download_depot commands update automatically.\n\n"
            "Skyrim SE apply/merge is fully automated. For other games, use Copy commands → "
            "Steam Console → Apply already-downloaded depots when content folders are ready.\n\n"
            "Optional DLC depots are listed only when relevant; only download DLC you own."
        )
        bp_help.setWordWrap(True)
        bp_help.setStyleSheet("color: #9aa0a6;")
        lay.addWidget(bp_help)

        lay.addWidget(QLabel("Game:"))
        self.bp_game = QComboBox()
        self._bp_game_ids: list[str] = []
        try:
            from kalium.tools.game_depots import list_games
            for g in list_games():
                self.bp_game.addItem(g.name)
                self._bp_game_ids.append(g.id)
        except Exception:
            self.bp_game.addItem("Skyrim Special Edition")
            self._bp_game_ids = ["skyrim-se"]
        self.bp_game.currentIndexChanged.connect(self._on_bp_game_changed)
        lay.addWidget(self.bp_game)

        lay.addWidget(QLabel("Target version:"))
        self.bp_version = QComboBox()
        self.bp_version.currentIndexChanged.connect(self._on_bp_version_changed)
        lay.addWidget(self.bp_version)

        self.bp_cmds_preview = QLabel("")
        self.bp_cmds_preview.setWordWrap(True)
        self.bp_cmds_preview.setStyleSheet(
            "font-family: monospace; color: #c9d1d9; background: #161b22; padding: 8px; border-radius: 6px;"
        )
        lay.addWidget(self.bp_cmds_preview)

        lay.addWidget(QLabel("Game folder (contains the game .exe):"))
        bp_row = QHBoxLayout()
        self.bp_game_path = QLineEdit()
        self.bp_game_path.setPlaceholderText("/path/to/game")
        bp_browse = QPushButton("Browse")
        bp_browse.clicked.connect(self._browse_bp_game)
        bp_row.addWidget(self.bp_game_path)
        bp_row.addWidget(bp_browse)
        lay.addLayout(bp_row)
        lay.addWidget(QLabel("Steam content / app_<id> folder (from download_depot output):"))
        bp_c = QHBoxLayout()
        self.bp_content_path = QLineEdit()
        self.bp_content_path.setPlaceholderText(
            "e.g. ~/.steam/steam/steamapps/content/app_489830"
        )
        bp_cb = QPushButton("Browse")
        bp_cb.clicked.connect(self._browse_bp_content)
        bp_c.addWidget(self.bp_content_path)
        bp_c.addWidget(bp_cb)
        lay.addLayout(bp_c)
        lay.addWidget(QLabel("Steam username (only for steamcmd method):"))
        self.bp_steam_user = QLineEdit()
        self.bp_steam_user.setPlaceholderText("Optional if using Steam Console mode")
        lay.addWidget(self.bp_steam_user)
        self.bp_backup = QCheckBox("Save OLD binaries to a backup folder (not the patch itself)")
        self.bp_backup.setChecked(True)
        lay.addWidget(self.bp_backup)
        self.bp_status = QLabel("")
        self.bp_status.setWordWrap(True)
        lay.addWidget(self.bp_status)
        bp_btns = QHBoxLayout()
        bp_auto = QPushButton("Backpatch to selected version")
        bp_auto.clicked.connect(lambda: self._run_backpatch("auto"))
        bp_console = QPushButton("Steam Console + wait")
        bp_console.clicked.connect(lambda: self._run_backpatch("console"))
        bp_apply = QPushButton("Apply already-downloaded depots")
        bp_apply.clicked.connect(lambda: self._run_backpatch("apply-only"))
        bp_btns.addWidget(bp_auto)
        bp_btns.addWidget(bp_console)
        bp_btns.addWidget(bp_apply)
        lay.addLayout(bp_btns)
        bp_cmds = QPushButton("Copy download_depot commands")
        bp_cmds.clicked.connect(self._copy_bp_commands)
        lay.addWidget(bp_cmds)
        bp_diag = QPushButton("Diagnose (compare game vs depot exe)")
        bp_diag.clicked.connect(self._diagnose_backpatch)
        lay.addWidget(bp_diag)

        self._on_bp_game_changed()
        self._refresh_nxm_instance_list()
        return self._wrap_scroll(w)

    def _refresh_prefixes(self) -> None:
        self.prefix_list.clear()
        self._prefixes = ManagedPrefixes.load()
        for p in self._prefixes:
            exists = Path(p.prefix_path).exists()
            self.prefix_list.addItem(
                f"{p.manager_type}: {p.name}  |  AppID {p.app_id}  |  "
                f"{'OK' if exists else 'MISSING'}  |  {p.prefix_path}"
            )

    def _open_prefix_folder(self) -> None:
        row = self.prefix_list.currentRow()
        if row < 0:
            return
        p = Path(self._prefixes[row].prefix_path)
        if p.exists():
            import subprocess
            subprocess.Popen(["xdg-open", str(p)])

    def _delete_prefix(self) -> None:
        row = self.prefix_list.currentRow()
        if row < 0:
            return
        p = self._prefixes[row]
        r = QMessageBox.question(
            self,
            "Delete Prefix?",
            f"Permanently delete prefix for {p.name}? This cannot be undone.",
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            ManagedPrefixes.delete_prefix(p.app_id)
            self._refresh_prefixes()
        except Exception as e:
            QMessageBox.warning(self, "Kalium", str(e))

    def _update_usvfs_for_selected(self) -> None:
        row = self.prefix_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Kalium", "Select a managed prefix first.")
            return
        p = self._prefixes[row]
        install_path = Path(p.install_path)
        if not (install_path / "ModOrganizer.exe").exists():
            QMessageBox.warning(
                self, "Kalium", f"ModOrganizer.exe not found in:\n{install_path}"
            )
            return
        self.usvfs_status.setText(
            f"Updating USVFS to 0.5.7.2 in {install_path}… (close MO2 first)"
        )

        def work():
            try:
                from kalium.installers.usvfs import install_usvfs

                install_usvfs(install_path, backup=True)
                self.usvfs_status.setText(
                    f"USVFS 0.5.7.2 installed into {install_path}\n"
                    "Previous binaries backed up under .kalium_usvfs_backup_0.5.7.2"
                )
            except Exception as e:
                self.usvfs_status.setText(f"USVFS update failed: {e}")
                log_error(str(e))

        threading.Thread(target=work, daemon=True).start()


    def _set_vfs_max_memory_for_selected(self) -> None:
        row = self.prefix_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Kalium", "Select a managed prefix first.")
            return
        p = self._prefixes[row]
        install_path = Path(p.install_path)
        try:
            from kalium.installers.ini_paths import set_vfs_max_memory, DEFAULT_VFS_MAX_MEMORY

            ok = set_vfs_max_memory(install_path, DEFAULT_VFS_MAX_MEMORY)
            if ok:
                mb = DEFAULT_VFS_MAX_MEMORY // (1024 * 1024)
                self.usvfs_status.setText(
                    f"[vfs] max_memory={DEFAULT_VFS_MAX_MEMORY} ({mb} MiB) "
                    f"written to {install_path / 'ModOrganizer.ini'}\n"
                    "Close MO2 completely, then relaunch for it to take effect."
                )
            else:
                self.usvfs_status.setText(
                    "ModOrganizer.ini not found yet — launch MO2 once so it creates "
                    "the ini, then click this button again."
                )
        except Exception as e:
            self.usvfs_status.setText(f"Failed to set max_memory: {e}")
            log_error(str(e))



    def _install_loot_for_selected(self) -> None:
        row = self.prefix_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Kalium", "Select a managed prefix first.")
            return
        p = self._prefixes[row]
        install_path = Path(p.install_path)
        if not (install_path / "ModOrganizer.exe").exists():
            QMessageBox.warning(
                self, "Kalium", f"ModOrganizer.exe not found in:\n{install_path}"
            )
            return
        self.usvfs_status.setText(
            f"Installing LOOT into {install_path}… (close MO2 first)\n"
            "Will also run winetricks -q vcrun2022 on this instance’s prefix."
        )

        def work():
            try:
                from kalium.installers.loot import install_and_register_loot

                launcher = install_and_register_loot(install_path, ensure_vcrun=True)
                if launcher:
                    bat = Path(launcher).parent / "run_loot.bat"
                    self.usvfs_status.setText(
                        f"LOOT ready → {launcher}\n"
                        "Custom executable points at LOOT.exe with --game= in arguments.\n"
                        f"Recovery one-shot bat (optional): {bat}\n"
                        f"vcrun2022 targeted at prefix: {p.prefix_path}\n"
                        "Close MO2 if open, then relaunch and select LOOT."
                    )
                else:
                    self.usvfs_status.setText(
                        "LOOT install finished with warnings — check the Kalium log. "
                        "If ModOrganizer.ini was missing, launch MO2 once and click again."
                    )
            except Exception as e:
                self.usvfs_status.setText(f"LOOT install failed: {e}")
                log_error(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _ensure_vcrun_for_selected(self) -> None:
        """WINEPREFIX=<instance pfx> winetricks -q vcrun2022 — same as terminal."""
        row = self.prefix_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Kalium", "Select a managed prefix first.")
            return
        p = self._prefixes[row]
        prefix = Path(p.prefix_path)
        if prefix.name != "pfx" and (prefix / "pfx").is_dir():
            prefix = prefix / "pfx"
        if not prefix.is_dir():
            QMessageBox.warning(
                self,
                "Kalium",
                f"Prefix not found:\n{prefix}\n\nLaunch MO2 once via Steam so the prefix is created.",
            )
            return
        self.usvfs_status.setText(
            f"Running (same as terminal):\n"
            f'WINEPREFIX="{prefix}" winetricks -q vcrun2022\n'
            f"AppID {p.app_id} — can take several minutes…"
        )

        def work():
            try:
                from kalium.installers.loot_vcrun import run_vcrun2022_for_prefix

                def st(msg: str) -> None:
                    # Prefer signal so the label updates on the GUI thread
                    if hasattr(self, "_plugin_bus"):
                        self._plugin_bus.status.emit(msg)
                    try:
                        self.usvfs_status.setText(msg)
                    except Exception:
                        pass

                if hasattr(self, "_plugin_bus"):
                    try:
                        self._plugin_bus.status.disconnect()
                    except Exception:
                        pass
                    self._plugin_bus.status.connect(
                        lambda m: self.usvfs_status.setText(m)
                    )
                    self._plugin_bus.error.connect(
                        lambda m: self.usvfs_status.setText(m)
                    )

                run_vcrun2022_for_prefix(
                    prefix,
                    proton_config_name=p.proton_config_name,
                    status=st,
                )
                done = (
                    f"✓ vcrun2022 OK for AppID {p.app_id}\n"
                    f'WINEPREFIX="{prefix}"'
                )
                st(done)
            except Exception as e:
                err = f"✗ vcrun2022 failed:\n{e}"
                if hasattr(self, "_plugin_bus"):
                    self._plugin_bus.error.emit(err)
                try:
                    self.usvfs_status.setText(err)
                except Exception:
                    pass
                log_error(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _browse_steam(self) -> None:
        d = _pick_directory(self, "Steam folder", str(Path.home() / ".steam"))
        if d:
            self.custom_steam.setText(d)

    def _save_steam_path(self) -> None:
        self.config.custom_steam_path = self.custom_steam.text().strip()
        self.config.save()
        self.steam_path = detect_steam_path_checked()
        self.steam_detected = self.steam_path is not None
        self.protons = find_steam_protons()
        self._update_steam_label()
        QMessageBox.information(self, "Kalium", "Steam path saved.")

    def _page_version(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        t = QLabel("Version")
        t.setObjectName("section")
        lay.addWidget(t)
        lay.addWidget(QLabel(f"Kalium v{__version__} — by Bobby Comet"))
        lay.addWidget(QLabel("Inspired by archived NaK (SulfurNitride). MIT licensed."))
        self.update_label = QLabel("Click Check for Updates.")
        lay.addWidget(self.update_label)
        self.release_notes = QTextEdit()
        self.release_notes.setReadOnly(True)
        self.release_notes.setMaximumHeight(160)
        lay.addWidget(self.release_notes)
        check = QPushButton("Check for Updates")
        check.clicked.connect(self._check_updates)
        lay.addWidget(check)
        return self._wrap_scroll(w)

    def _check_updates(self) -> None:
        self.update_label.setText("Checking...")
        try:
            info = check_for_updates()
            if info.is_update_available:
                self.update_label.setText(
                    f"Update available: v{info.latest_version} (current v{info.current_version})"
                )
            else:
                self.update_label.setText(f"You're up to date! (v{info.current_version})")
            self.release_notes.setPlainText(info.release_notes)
        except Exception as e:
            self.update_label.setText(f"Update check failed: {e}")



    def _nxm_status_text(self) -> str:
        try:
            active = read_active()
        except Exception:
            active = None
        if not active:
            return "NXM handler: OFF — no instance selected. Choose an MO2 install below and turn NXM on."
        name = active.get("name") or "MO2"
        return (
            f"NXM handler is ACTIVE for “{name}”\n"
            f"Downloads go to: {active.get('exe')}\n"
            f"Prefix: {active.get('prefix')}"
        )

    def _refresh_nxm_status_widgets(self) -> None:
        text = self._nxm_status_text()
        if hasattr(self, "nxm_banner") and self.nxm_banner is not None:
            self.nxm_banner.setText(text)
        if hasattr(self, "nxm_status") and self.nxm_status is not None:
            self.nxm_status.setText(text)
        if hasattr(self, "gs_nxm_status") and self.gs_nxm_status is not None:
            self.gs_nxm_status.setText(text)

    def _refresh_nxm_instance_list(self) -> None:
        if not hasattr(self, "nxm_instance_list"):
            return
        self.nxm_instance_list.clear()
        self._nxm_instances = ManagedPrefixes.load()
        active = read_active() or {}
        active_id = int(active.get("app_id") or 0)
        for p in self._nxm_instances:
            mark = "  ✓ NXM active" if p.app_id == active_id else ""
            self.nxm_instance_list.addItem(
                f"{p.name}  (AppID {p.app_id}){mark}"
            )
            if p.app_id == active_id:
                self.nxm_instance_list.setCurrentRow(self.nxm_instance_list.count() - 1)
        self._refresh_nxm_status_widgets()

    def _enable_nxm(self) -> None:
        """Turn NXM on for the selected managed instance (or last MO2)."""
        try:
            NxmHandler.setup()
            prefixes = getattr(self, "_nxm_instances", None) or ManagedPrefixes.load()
            row = -1
            if hasattr(self, "nxm_instance_list"):
                row = self.nxm_instance_list.currentRow()
            if row < 0 and hasattr(self, "prefix_list"):
                row = self.prefix_list.currentRow()
                prefixes = getattr(self, "_prefixes", prefixes)

            if row >= 0 and row < len(prefixes):
                p = prefixes[row]
                from kalium.nxm import resolve_proton_path
                proton = resolve_proton_path(p.proton_config_name)
                if not proton:
                    QMessageBox.warning(self, "Kalium", "No Proton found on this system.")
                    return
                activate_for_install(p.install_path, p.prefix_path, proton, p.app_id, p.name)
                name = p.name
            else:
                if not activate_from_managed():
                    QMessageBox.warning(
                        self,
                        "Kalium",
                        "No MO2 instance found.\nFinish MO2 setup on the MO2 tab first.",
                    )
                    return
                active = read_active() or {}
                name = active.get("name") or "MO2"

            self._refresh_nxm_instance_list()
            self._refresh_nxm_status_widgets()
            QMessageBox.information(
                self,
                "Kalium",
                f"NXM handler is active for “{name}”.\n\n"
                "In your browser, pick “Kalium NXM Handler” for nxm:// links "
                "(not the main Kalium app).",
            )
        except Exception as e:
            QMessageBox.critical(self, "Kalium", str(e))

    def _reregister_nxm(self) -> None:
        try:
            NxmHandler.setup()
            self._refresh_nxm_status_widgets()
            QMessageBox.information(
                self,
                "Kalium",
                "Browser handler re-registered.\n"
                "Default: x-scheme-handler/nxm → kalium-nxm-handler.desktop",
            )
        except Exception as e:
            QMessageBox.critical(self, "Kalium", str(e))








    def _bp_selected_game_id(self) -> str:
        ids = getattr(self, "_bp_game_ids", ["skyrim-se"])
        i = self.bp_game.currentIndex() if hasattr(self, "bp_game") else 0
        if 0 <= i < len(ids):
            return ids[i]
        return "skyrim-se"

    def _on_bp_game_changed(self, *_args) -> None:
        if not hasattr(self, "bp_version"):
            return
        try:
            from kalium.tools.game_depots import get_game
            game = get_game(self._bp_selected_game_id())
            self.bp_version.blockSignals(True)
            self.bp_version.clear()
            for t in game.targets:
                self.bp_version.addItem(t.label, t.id)
            # select default
            default = game.default_target
            for i in range(self.bp_version.count()):
                if self.bp_version.itemData(i) == default:
                    self.bp_version.setCurrentIndex(i)
                    break
            self.bp_version.blockSignals(False)
            if hasattr(self, "bp_game_path"):
                self.bp_game_path.setPlaceholderText(game.folder_hint)
            self._on_bp_version_changed()
        except Exception as e:
            log_error(str(e))

    def _on_bp_version_changed(self, *_args) -> None:
        if not hasattr(self, "bp_cmds_preview"):
            return
        try:
            from kalium.tools.game_depots import steam_console_commands
            game_id = self._bp_selected_game_id()
            ver = self.bp_version.currentData() or self.bp_version.currentText()
            cmds = steam_console_commands(game_id, str(ver), include_optional=True)
            self.bp_cmds_preview.setText(cmds)
        except Exception as e:
            self.bp_cmds_preview.setText(str(e))

    def _diagnose_backpatch(self) -> None:
        path = self.bp_game_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Kalium", "Set the game folder first.")
            return
        content = self.bp_content_path.text().strip() if hasattr(self, "bp_content_path") else ""
        self.bp_status.setText("Diagnosing…")

        def work():
            try:
                from kalium.tools.skyrim_backpatch import diagnose
                report = diagnose(path, content or None)
                self.bp_status.setText(report)
            except Exception as e:
                self.bp_status.setText(f"Diagnose failed: {e}")
                log_error(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _browse_bp_content(self) -> None:

        d = _pick_directory(self, "Steam content or app_489830 folder", str(Path.home() / ".steam"))
        if d:
            self.bp_content_path.setText(d)

    def _browse_bp_game(self) -> None:
        d = _pick_directory(self, "Skyrim Special Edition folder")
        if d:
            self.bp_game_path.setText(d)

    def _copy_bp_commands(self) -> None:
        from kalium.tools.game_depots import steam_console_commands
        from kalium.tools.skyrim_backpatch import copy_to_clipboard, open_steam_console
        game_id = self._bp_selected_game_id() if hasattr(self, "_bp_selected_game_id") else "skyrim-se"
        ver = (
            self.bp_version.currentData()
            if hasattr(self, "bp_version") and self.bp_version.currentData()
            else (self.bp_version.currentText() if hasattr(self, "bp_version") else "1.6.1170")
        )
        cmds = steam_console_commands(game_id, str(ver), include_optional=True)
        ok = copy_to_clipboard(cmds)
        open_steam_console()
        QMessageBox.information(
            self,
            "Kalium",
            ("Commands copied to clipboard.\n\n" if ok else "")
            + f"Paste into Steam Console ({game_id} → {ver}):\n\n"
            + cmds,
        )

    def _run_backpatch(self, method: str) -> None:
        path = self.bp_game_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Kalium", "Select the game install folder.")
            return
        game_id = self._bp_selected_game_id() if hasattr(self, "_bp_selected_game_id") else "skyrim-se"
        try:
            from kalium.tools.game_depots import get_game
            gmeta = get_game(game_id)
            exes = gmeta.exe_names
        except Exception:
            exes = ("SkyrimSE.exe",)
        if not any((Path(path) / name).is_file() for name in exes):
            QMessageBox.warning(
                self,
                "Kalium",
                f"None of {', '.join(exes)} found in:\n{path}\n\n"
                "Apply/auto merge is fully supported for Skyrim SE; "
                "for other games use Copy commands + Apply after depots finish downloading.",
            )
            if game_id == "skyrim-se":
                return
        if method == "auto" and not self.bp_steam_user.text().strip():
            method = "console"
        self.bp_status.setText(f"Backpatch running ({method})…")

        def work():
            try:
                from kalium.tools.skyrim_backpatch import run_backpatch
                ver = self.bp_version.currentText() if hasattr(self, "bp_version") else "1.6.1170"
                content = self.bp_content_path.text().strip() if hasattr(self, "bp_content_path") else ""
                result = run_backpatch(
                    path,
                    version=ver,
                    method=method,
                    steam_user=self.bp_steam_user.text().strip(),
                    content_dir=content or None,
                    backup=self.bp_backup.isChecked(),
                    status=lambda m: self.bp_status.setText(m),
                )
                self.bp_status.setText(
                    f"Done → {result.version}\nGame: {result.game_dir}\n"
                    f"Method: {result.method}\n"
                    + (f"Backup: {result.backup_dir}" if result.backup_dir else "")
                )
            except Exception as e:
                self.bp_status.setText(f"Backpatch failed: {e}")
                log_error(str(e))

        threading.Thread(target=work, daemon=True).start()

def run_app() -> None:
    init_logger()
    log_info("Kalium GUI starting...")
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("Kalium")
    app.setOrganizationName("Bobby Comet")
    _icon = _app_icon()
    if not _icon.isNull():
        app.setWindowIcon(_icon)
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
