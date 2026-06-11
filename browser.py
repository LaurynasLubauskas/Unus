import sys
import os
import re
from groq import Groq
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

  def __init__(self, messages, system=None):
    super().__init__()
    self.messages = messages
    self.system = system or "You are helpful assistant built into a web browser. Be concise"

  def run(self):
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": self.system},
                *self.messages
            ]
        )
        self.response_ready.emit(response.choices[0].message.content)
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
  message_sent = pyqtSignal(str)

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setObjectName("aiPopup")
    self.setFixedWidth(380)
    self.setFixedHeight(420)

    layout = QVBoxLayout(self)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(8)

    header = QHBoxLayout()
    title = QLabel("AI Assistant")
    title.setObjectName("aiTitle")
    header.addWidget(title)
    header.addStretch()
    close_btn = QPushButton("x")
    close_btn.setObjectName("aiClose")
    close_btn.setFixedSize(20, 20)
    close_btn.clicked.connect(self.hide)
    header.addWidget(close_btn)
    layout.addLayout(header)

    self.chat_area = QScrollArea()
    self.chat_area.setObjectName("aiChatArea")
    self.chat_area.setWidgetResizable(True)
    self.chat_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    self.chat_container = QWidget()
    self.chat_container.setObjectName("aiChatContainer")
    self.chat_layout = QVBoxLayout(self.chat_container)
    self.chat_layout.setContentsMargins(4, 4, 4, 4)
    self.chat_layout.setSpacing(8)
    self.chat_layout.addStretch()

    self.chat_area.setWidget(self.chat_container)
    layout.addWidget(self.chat_area, 1)

    input_row = QHBoxLayout()
    input_row.setSpacing(6)

    self.input = QLineEdit()
    self.input.setObjectName("aiInput")
    self.input.setPlaceholderText("Reply...")
    self.input.returnPressed.connect(self._send)

    send_btn = QPushButton("Send")
    send_btn.setObjectName("aiSend")
    send_btn.clicked.connect(self._send)

    input_row.addWidget(self.input)
    input_row.addWidget(send_btn)
    layout.addLayout(input_row)

    self.hide()

  def _send(self):
      text = self.input.text().strip()
      if not text:
        return
      self.input.clear()
      self.add_message(text, is_user=True)
      self.message_sent.emit(text)

  def add_message(self, text, is_user=False):
      bubble = QLabel(text)
      bubble.setWordWrap(True)
      bubble.setObjectName("aiUserBubble" if is_user else "aiAssistantBubble")
      bubble.setMaximumWidth(360)
      self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
      self._scroll_to_bottom()

  def set_thinking(self):
      self.add_message("Thinking...", is_user=False)
      self._thinking_label = self.chat_layout.itemAt(self.chat_layout.count() - 2).widget()

  def replace_thinking(self, text):
      if hasattr(self, "_thinking_label") and self._thinking_label:
        self._thinking_label.setText(text)
        self._thinking_label = None
      self._scroll_to_bottom()

  def _scroll_to_bottom(self):
      from PyQt6.QtCore import QTimer
      QTimer.singleShot(50, lambda: self.chat_area.verticalScrollBar().setValue(
        self.chat_area.verticalScrollBar().maximum()
      ))

  def show_question(self, question):
      self.add_message(question, is_user=True)
      self.set_thinking()
      self.show()

  def show_answer(self, answer):
      self.replace_thinking(answer)

class Browser(QMainWindow):

  def __init__(self):
    super().__init__()
    self.setWindowTitle("Unus")
    self.setMinimumSize(1200, 800)

    self._browsers = []
    self._current_index = -1
    self._ai_workers = []
    self._conversation_history = []
    self._conversation_system = ""

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
    self.ai_popup = AIPopup(self.content_area)
    self.ai_popup.message_sent.connect(self._on_ai_reply)
    self.ai_popup.raise_()

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
    browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    browser.customContextMenuRequested.connect(lambda pos, b=browser: self._show_context_menu(pos, b))
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
    if is_question(text):
      self._ask_ai(text)
      return
    if "." in text and " " not in text:
      if not text.startswith("http"):
        text = "https://" + text
      self.current_browser().setUrl(QUrl(text))
    else:
      self.current_browser().setUrl(QUrl(f"https://www.google.com/search?q={text}"))
    self.current_browser().setFocus()

  def ai_rename_tab(self, idx, title, url):
    prompt = (
      f"Page title: {title}\n"
      f"URL: {url}\n\n"
      f"Give me a short tab label for this page. Maximum 4 words. No punctuation. Just the label, nothing else."
    )
    worker = AIWorker(
      [{"role": "user", "content": prompt}],
      system="You generate very short browser tab labels. Respond with only the label, no explanation, no punctuation, maximum 4 words."
    )
    worker.response_ready.connect(lambda label, i=idx: self.sidebar.update_title(i, label.strip()))
    worker.start()
    self._ai_workers.append(worker)

  def _ask_ai(self, question, system=None):
    url = self.current_browser().url().toString() if self.current_browser() else ""
    page_title = self.current_browser().title() if self.current_browser() else ""
    self._conversation_system = system or (
      "You are a helpful assistant built into a web browser."
      "Be concise. Answer in 2-3 sentences max unless the question requires detail."
    )
    self._conversation_history = []
    self._conversation_history.append(
    {"role": "user", "content": f"Current page: {page_title} ({url})\n\nQuestion: {question}"}
    )
    self.ai_popup.show_question(question)
    self._position_popup()
    self._run_ai_worker()
    self.sidebar.url_bar.clear()

  def _position_popup(self):
    self.ai_popup.move(16, 16)
    self.ai_popup.raise_()

  def _show_context_menu(self, pos, browser):
    menu = QFrame(self)
    selected_action = menu.addAction("Ask AI about selection")
    summarize_action = menu.addAction("Summarize this page")
    action = menu.exec(browser.mapToGlobal(pos))
    if action == selected_action:
      browser.page().runJavaScript(
        "window.getSelection().toString()",
        lambda text: self._ask_ai_selection(text)
      )
    elif action == summarize_action:
      browser.page().runJavaScript(
        "document.body.innerText.slice(0, 3000)",
        lambda text: self._summarize_page(text)
      )

  def _ask_ai_selection(self, selected_text):
    if not selected_text or not selected_text.strip():
      self.status.showMessage("No text selected", 2000)
      return
    self._ask_ai(f'The user selected this text on webpage:\n\n"{selected_text}"\n\nExplain it clearly and concisely.')

  def _summarize_page(self, page_text):
    if not page_text or not page_text.strip():
      self.status.showMessage("Could not read page content", 2000)
      return
    title = self.current_browser().title() if self.current_browser() else "this page"
    self._ask_ai(f"Summarize this webpage titled '{title}' in 3-4 sentences:\n\n{page_text}")

  def _on_ai_reply(self, text):
    self._conversation_history.append({"role": "user", "content": text})
    self.ai_popup.set_thinking()
    self._run_ai_worker()

  def _run_ai_worker(self):
    worker = AIWorker(self._conversation_history, system=self._conversation_system)
    worker.response_ready.connect(self._on_ai_response)
    worker.error.connect(lambda e: self.ai_popup.replace_thinking(f"Error: {e}"))
    worker.start()
    self._ai_workers.append(worker)

  def _on_ai_response(self, text):
    self._conversation_history.append({"role": "assistant", "content": text})
    self.ai_popup.show_answer(text)

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
      cleaned = clean_title(title)
      self.sidebar.update_title(idx, cleaned)
      if sender_browser == self.current_browser():
        self.setWindowTitle(title or "Unus")
        self.ai_rename_tab(idx, title, self.current_browser().url().toString())

  def resizeEvent(self, event):
    super().resizeEvent(event)
    self._position_popup()

app = QApplication(sys.argv)
app.setApplicationName("Unus")
app.setStyleSheet(load_styles())
window = Browser()
window.show()
sys.exit(app.exec())