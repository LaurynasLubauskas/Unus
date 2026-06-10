import sys
import os
import re
import google.generativeai as genai
from PyQt6.QtWidgets import (QApplication, QMainWindow, QToolBar, QLineEdit, QTabWidget, QWidget, QStatusBar, QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QLabel, QScrollArea, QSizePolicy, QMenu)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWebEngineCore import QWebEngineScript

def load_styles():
  style_path = os.path.join(os.path.dirname(__file__), "style.qss")
  with open(style_path, "r") as f:
    return f.read()
  
def is_question(text):
  question_words = ["what", "who", "where", "when", "why", "how", "is", "are", "can", "does", "do", "should", "would", "could", "which"]
  lowered = text.lower().strip()
  if lowered.endswith("?"):
    return True
  if any(lowered.startswith(w + " ") for w in question_words):
    return True
  if " " in text and "." not in text:
    return True
  return False

def clean_title(title):
  separators = [" - ", " | ", " — ", " :: "]
  for sep in separators:
    if sep in title:
      title = title.split(sep)[0]
    return title.strip()
  
class AIWorker(QThread):
  response_ready = pyqtSignal(str)
  error = pyqtSignal(str)

  def __init__(self, prompt, system=None):
    super().__init__()
    self.system = system or "You are helpful assistant built into a web browser."

  def run(self):
    try:
      genai.configure(api_key=os.environ.get("GEMINI_API_KEY", " "))
      model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=self.system
      )
      response = model.generate_content(self.prompt)
      self.response_ready.emit(response.text)
    except Exception as e:
      self.error.emit(str(e))


class SidebarTab(QFrame):
  clicked = pyqtSignal()
  close_requested = pyqtSignal()

  def __init__(self, title="New Tab", parent=None):
    super().__init__(parent)
    self.setObjectName("sidebarTab")
    self.setCursor(Qt.CursorShape.PointingHandCursor)
    self.setFixedHeight(40)
    self._active = False

    layout = QHBoxLayout(self)
    layout.setContentsMargins(12, 0, 8, 0)
    layout.setSpacing(8)

    self.favicon = QLabel("*")
    self.favicon.setFixedSize(18, 18)
    self.favicon.setObjectName("tabFavicon")

    self.title_label = QLabel(title)
    self.title_label.setObjectName("tabTitle")
    self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    self.title_label.setMaximumWidth(160)

    self.close_btn = QPushButton("x")
    self.close_btn.setObjectName("tabClose")
    self.close_btn.setFixedSize(18, 18)
    self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.close_btn.clicked.connect(self.close_requested.emit)
    self.close_btn.hide()

    layout.addWidget(self.favicon)
    layout.addWidget(self.title_label)
    layout.addWidget(self.close_btn)

  def set_title(self, title):
    short = title[:22] + "..." if len(title) > 22 else title
    self.title_label.setText(short)
    self.title_label.setToolTip(title)

  def set_active(self, active):
    self._active = active
    self.setProperty("active", active)
    self.style().unpolish(self)
    self.style().polish(self)

  def enterEvent(self, event):
    self.close_btn.show()
    super().enterEvent(event)

  def leaveEvent(self, event):
    self.close_btn.hide()
    super().leaveEvent(event)

  def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      self.clicked.emit()
    super().mousePressEvent(event)

class Sidebar(QFrame):
  new_tab_requested = pyqtSignal()
  tab_selected = pyqtSignal(int)
  tab_closed = pyqtSignal(int)

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setObjectName("sidebar")
    self.setFixedWidth(240)
    self._tab_widgets = []

    outer = QVBoxLayout(self)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    top = QFrame()
    top.setObjectName("sidebarTop")
    top_layout = QHBoxLayout(top)
    top_layout.setContentsMargins(16, 16, 16, 16)

    logo = QLabel("Unus")
    logo.setObjectName("brandLogo")
    top_layout.addWidget(logo)
    top_layout.addStretch()

    outer.addWidget(top)

    url_frame = QFrame()
    url_frame.setObjectName("urlFrame")
    url_layout = QHBoxLayout(url_frame)
    url_layout.setContentsMargins(12, 8, 12, 8)

    self.url_bar = QLineEdit()
    self.url_bar.setObjectName("urlBar")
    self.url_bar.setPlaceholderText("Search or type a URL...")
    url_layout.addWidget(self.url_bar)

    outer.addWidget(url_frame)

    nav_frame = QFrame()
    nav_frame.setObjectName("navFrame")
    nav_layout = QHBoxLayout(nav_frame)
    nav_layout.setContentsMargins(12, 4, 12, 4)
    nav_layout.setSpacing(6)

    self.back_btn = QPushButton("<")
    self.back_btn.setObjectName("navBtn")
    self.forward_btn = QPushButton(">")
    self.forward_btn.setObjectName("navBtn")
    self.reload_btn = QPushButton("R")
    self.reload_btn.setObjectName("navBtn")
    self.home_btn = QPushButton("H")
    self.home_btn.setObjectName("navBtn")

    for btn in [self.back_btn, self.forward_btn, self.reload_btn, self.home_btn]:
      btn.setFixedSize(34, 34)
      btn.setCursor(Qt.CursorShape.PointingHandCursor)
      nav_layout.addWidget(btn)

    nav_layout.addStretch()
    outer.addWidget(nav_frame)

    div = QFrame()
    div.setObjectName("sidebarDivider")
    div.setFixedHeight(1)
    outer.addWidget(div)

    tabs_label = QLabel("SPACES")
    tabs_label.setObjectName("sectionLabel1")
    tabs_label.setContentsMargins(16, 12, 0, 6)
    outer.addWidget(tabs_label)

    scroll = QScrollArea()
    scroll.setObjectName("tabsScroll")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    self.tabs_container = QWidget()
    self.tabs_container.setObjectName("tabsContainer")
    self.tabs_layout = QVBoxLayout(self.tabs_container)
    self.tabs_layout.setContentsMargins(8, 0, 8, 8)
    self.tabs_layout.setSpacing(2)
    self.tabs_layout.addStretch()

    scroll.setWidget(self.tabs_container)
    outer.addWidget(scroll, 1)

    bottom = QFrame()
    bottom.setObjectName("sidebarBottom")
    bottom_layout = QHBoxLayout(bottom)
    bottom_layout.setContentsMargins(12, 12, 12, 16)

    new_tab_btn = QPushButton("+ New Tab")
    new_tab_btn.setObjectName("newTabBtn")
    new_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    new_tab_btn.clicked.connect(self.new_tab_requested.emit)
    bottom_layout.addWidget(new_tab_btn)

    outer.addWidget(bottom)

  def add_tab(self, title="New Tab"):
    tab = SidebarTab(title)
    idx = len(self._tab_widgets)
    tab.clicked.connect(lambda i=idx: self._on_tab_click(i))
    tab.close_requested.connect(lambda i=idx: self.tab_closed.emit(i))
    self._tab_widgets.append(tab)
    self.tabs_layout.insertWidget(self.tabs_layout.count() - 1, tab)
    self.set_active(idx)
    return idx
  
  def _on_tab_click(self, idx):
    for i, tw in enumerate(self._tab_widgets):
      if tw is self._tab_widgets[idx]:
        self.tab_selected.emit(i)
        break

  def set_active(self, index):
    for i, tab in enumerate(self._tab_widgets):
      tab.set_active(i == index)

  def update_title(self, index, title):
    if 0 <= index < len(self._tab_widgets):
      self._tab_widgets[index].set_title(title)

  def remove_tab(self, index):
    if 0 <= index < len(self._tab_widgets):
      tab = self._tab_widgets.pop(index)
      self.tabs_layout.removeWidget(tab)
      tab.deleteLater()
      for i, tw in enumerate(self._tab_widgets):
        try:
          tw.clicked.disconnect()
          tw.close_requested.disconnect()
        except Exception:
          pass
        tw.clicked.connect(lambda checked=False, idx=i: self.tab_selected.emit(idx))
        tw.close_requested.connect(lambda checked=False, idx=i: self.tab_closed.emit(idx))

  def count(self):
    return len(self._tab_widgets)
  
class AIPopup(QFrame):
  def __init__(self, parent=None):
    super()

class Browser(QMainWindow):

  def __init__(self):
    super().__init__()
    self.setWindowTitle("Unus")
    self.setMinimumSize(1200, 800)

    self._browsers = []
    self._current_index = -1

    central = QWidget()
    central.setObjectName("centralWidget")
    main_layout = QHBoxLayout(central)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)
    self.setCentralWidget(central)

    self.sidebar = Sidebar()
    self.sidebar.new_tab_requested.connect(lambda: self.new_tab())
    self.sidebar.tab_selected.connect(self.switch_tab)
    self.sidebar.tab_closed.connect(self.close_tab)
    self.sidebar.url_bar.returnPressed.connect(self.navigate)
    self.sidebar.back_btn.clicked.connect(lambda: self.current_browser().back())
    self.sidebar.forward_btn.clicked.connect(lambda: self.current_browser().forward())
    self.sidebar.reload_btn.clicked.connect(lambda: self.current_browser().reload())
    self.sidebar.home_btn.clicked.connect(self.go_home)
    main_layout.addWidget(self.sidebar)

    vdiv = QFrame()
    vdiv.setObjectName("verticalDivider")
    vdiv.setFixedWidth(1)
    main_layout.addWidget(vdiv)

    self.content_area = QFrame()
    self.content_area.setObjectName("contentArea")
    self.content_layout = QVBoxLayout(self.content_area)
    self.content_layout.setContentsMargins(0, 0, 0, 0)
    self.content_layout.setSpacing(0)
    main_layout.addWidget(self.content_area, 1)

    self.status = QStatusBar()
    self.status.setObjectName("statusBar")
    self.setStatusBar(self.status)

    QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self.new_tab())
    QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(lambda: self.close_tab(self._current_index))
    QShortcut(QKeySequence("Ctrl+Shift+R"), self).activated.connect(self.reload_styles)
    QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(lambda: self.sidebar.url_bar.setFocus())

    self.new_tab("https://google.com")

  def reload_styles(self):
    app.setStyleSheet(load_styles())
    self.status.showMessage("Style reloaded!")

  def new_tab(self, url="https://google.com"):
    browser = QWebEngineView()
    browser.setUrl(QUrl(url))
    browser.urlChanged.connect(self._on_url_changed)
    browser.titleChanged.connect(self._on_title_changed)
    browser.loadStarted.connect(lambda: self.status.showMessage("Loading..."))
    browser.loadFinished.connect(lambda ok: self.status.showMessage("Done" if ok else "Error", 2000))
    idx = len(self._browsers)
    self._browsers.append(browser)
    self.content_layout.addWidget(browser)
    self.sidebar.add_tab("New Tab")
    self.switch_tab(idx)

  def close_tab(self, index):
    if len(self._browsers) <= 1:
      return
    browser = self._browsers.pop(index)
    self.content_layout.removeWidget(browser)
    browser.deleteLater()
    self.sidebar.remove_tab(index)
    new_index = min(index, len(self._browsers) -1)
    self._current_index = -1
    self.switch_tab(new_index)

  def current_browser(self):
    if 0 <= self._current_index < len(self._browsers):
      return self._browsers[self._current_index]
    return None

  def navigate(self):
    text = self.sidebar.url_bar.text().strip()
    if not text:
      return
    if "." in text and " " not in text:
      if not text.startswith("http"):
        text = "https://" + text
      self.current_browser().setUrl(QUrl(text))
    else:
      self.current_browser().setUrl(QUrl(f"https://www.google.com/search?q={text}"))
    self.current_browser().setFocus()

  def go_home(self):
    self.current_browser().setUrl(QUrl("https://google.com"))

  def switch_tab(self, index):
    if index == self._current_index:
      return
    for i, b in enumerate(self._browsers):
      b.setVisible(i == index)
    self._current_index = index
    self.sidebar.set_active(index)
    if self.current_browser():
      self.sidebar.url_bar.setText(self.current_browser().url().toString())
      self.setWindowTitle(self.current_browser().title() or "Unus")

  def _on_url_changed(self, url):
    if self.sender() == self.current_browser():
      self.sidebar.url_bar.setText(url.toString())

  def _on_title_changed(self, title):
    sender_browser = self.sender()
    if sender_browser in self._browsers:
      idx = self._browsers.index(sender_browser)
      self.sidebar.update_title(idx, title)
      if sender_browser == self.current_browser():
        self.setWindowTitle(title or "Unus")

app = QApplication(sys.argv)
app.setApplicationName("Unus")
app.setStyleSheet(load_styles())
window = Browser()
window.show()
sys.exit(app.exec())