import sys
import json
import requests
import os
import ast
import threading
from PyQt5.QtWidgets import (QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QFileDialog, QLabel, QMessageBox,
                             QSplitter, QStatusBar, QAction, QTreeView, QFileSystemModel)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QModelIndex
from PyQt5.QtGui import QFont, QTextCharFormat, QColor, QSyntaxHighlighter, QTextCursor, QTextDocument, QTextOption
import time

# --- 1. The Worker Thread for API Calls ---
class CommentGeneratorWorker(QObject):
    finished_one = pyqtSignal(str, str)
    finished_all = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, code_blocks, parent=None):
        super().__init__(parent)
        self.code_blocks = code_blocks

    def run(self):
        try:
            status_url = 'http://127.0.0.1:5000/status'
            start_time = time.time()
            server_ready = False
            while time.time() - start_time < 30:
                try:
                    response = requests.get(status_url, timeout=5)
                    if response.status_code == 200 and response.json().get('status') == 'ready':
                        server_ready = True
                        break
                except requests.exceptions.RequestException:
                    pass
                time.sleep(1)
            
            if not server_ready:
                self.error.emit("Local server is not ready. Please ensure app.py is running.")
                return

            api_url = 'http://127.0.0.1:5000/generate-comment'
            headers = {'Content-Type': 'application/json'}
            
            for code_snippet in self.code_blocks:
                data = {'code': code_snippet}
                response = requests.post(api_url, json=data, headers=headers, timeout=60)
                response.raise_for_status()
                comments = response.json()
                if "comment" in comments:
                    self.finished_one.emit(code_snippet, comments['comment'])
                else:
                    self.error.emit(comments.get('error', 'Unknown API error'))
            
            self.finished_all.emit()

        except requests.exceptions.RequestException as e:
            self.error.emit(f"Failed to connect to local server: {e}")

# --- 2. Syntax Highlighter for Code Editor ---
class CodeHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for a Python code editor."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlight_rules = []
        self.keyword_format = QTextCharFormat()
        self.string_format = QTextCharFormat()
        self.number_format = QTextCharFormat()
        self.comment_format = QTextCharFormat()

        self.setup_formats()
        self.setup_rules()

    def setup_formats(self):
        self.keyword_format.setForeground(QColor('#569cd6'))
        self.keyword_format.setFontWeight(QFont.Bold)
        self.string_format.setForeground(QColor('#ce9178'))
        self.number_format.setForeground(QColor('#b5cea8'))
        self.comment_format.setForeground(QColor('#6a9955'))
        self.comment_format.setFontItalic(True)

    def setup_rules(self):
        keywords = ['class', 'def', 'return', 'if', 'else', 'elif', 'for', 'while', 'in',
                    'import', 'from', 'as', 'try', 'except', 'finally', 'with', 'as', 'None',
                    'True', 'False', 'and', 'or', 'not', 'is', 'lambda', 'yield', 'async', 'await']
        
        for word in keywords:
            pattern = fr'\b{word}\b'
            self.highlight_rules.append((pattern, self.keyword_format))

        self.highlight_rules.append((r'"[^"\\]*(\\.[^"\\]*)*"', self.string_format))
        self.highlight_rules.append((r"'[^'\\]*(\\.[^'\\]*)*'", self.string_format))
        self.highlight_rules.append((r'\b\d+(\.\d+)?\b', self.number_format))
        self.highlight_rules.append((r'#[^\n]*', self.comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlight_rules:
            expression = pattern
            index = text.find(expression)
            while index >= 0:
                length = len(expression)
                self.setFormat(index, length, format)
                index = text.find(expression, index + length)
        
        self.setCurrentBlockState(0)
        start = 0
        while start < len(text):
            triple_quote_start = text.find('"""', start)
            if triple_quote_start == -1:
                triple_quote_start = text.find("'''", start)
                if triple_quote_start == -1:
                    break
            
            triple_quote_end = text.find(text[triple_quote_start:triple_quote_start+3], triple_quote_start + 3)
            
            if triple_quote_end == -1:
                self.setFormat(triple_quote_start, len(text) - triple_quote_start, self.comment_format)
                self.setCurrentBlockState(1)
                break
            else:
                self.setFormat(triple_quote_start, triple_quote_end - triple_quote_start + 3, self.comment_format)
                start = triple_quote_end + 3
        
        if self.currentBlockState() == 1:
            self.setFormat(0, len(text), self.comment_format)

# --- 3. The Main PyQt5 GUI ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DocuCode - Code Comment Generator")
        self.setMinimumSize(1400, 800)
        self.current_file_path = None
        
        # Set a dark theme for the entire application
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #cccccc; }
            QWidget { background-color: #1e1e1e; color: #cccccc; }
            QTextEdit { background-color: #2b2b2b; color: #cccccc; border: 1px solid #555555; }
            QLabel { color: #cccccc; }
            QPushButton { background-color: #3e3e3e; color: #cccccc; border: 1px solid #555555; padding: 5px; border-radius: 3px; }
            QPushButton:hover { background-color: #505050; }
            QMenuBar { background-color: #2b2b2b; color: #cccccc; }
            QStatusBar { background-color: #2b2b2b; color: #cccccc; }
            QSplitter::handle { background-color: #3e3e3e; }
            QTreeView { background-color: #2b2b2b; color: #cccccc; border: 1px solid #555555; }
        """)

        self.create_menu_bar()

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)
        
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Panel 1: File System View
        self.file_model = QFileSystemModel()
        self.file_view = QTreeView()
        self.file_view.setModel(self.file_model)
        self.file_view.clicked.connect(self.on_file_selected)
        
        for i in range(1, self.file_model.columnCount()):
            self.file_view.hideColumn(i)
        
        # Panel 2: Code Editor
        self.code_editor = QTextEdit()
        self.code_editor.setFont(QFont('Consolas', 10))
        self.highlighter = CodeHighlighter(self.code_editor.document())
        self.code_editor.setWordWrapMode(QTextOption.NoWrap)
        
        # Panel 3: Generated Comment Display
        self.comment_display = QTextEdit()
        self.comment_display.setReadOnly(True)
        self.comment_display.setFont(QFont('Consolas', 10))
        self.comment_display.setWordWrapMode(QTextOption.NoWrap)
        
        self.splitter.addWidget(self.file_view)
        self.splitter.addWidget(self.code_editor)
        self.splitter.addWidget(self.comment_display)
        self.splitter.setSizes([300, 500, 600])
        
        self.button_layout = QHBoxLayout()
        self.open_btn = QPushButton("Open Folder")
        self.save_btn = QPushButton("Save Comment")
        self.generate_btn = QPushButton("Generate Comment")
        self.clear_btn = QPushButton("Clear All")
        
        self.button_layout.addWidget(self.open_btn)
        self.button_layout.addWidget(self.save_btn)
        self.button_layout.addWidget(self.generate_btn)
        self.button_layout.addWidget(self.clear_btn)
        
        self.layout.addWidget(self.splitter)
        self.layout.addLayout(self.button_layout)
        
        self.open_btn.clicked.connect(self.open_folder)
        self.save_btn.clicked.connect(self.save_comment)
        self.generate_btn.clicked.connect(self.generate_comment)
        self.clear_btn.clicked.connect(self.clear_all)
        
        self.comment_thread = None
        self.update_status("Ready")

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu('&File')
        file_menu.addAction(self.create_action("&Open File", self.open_file, "Ctrl+O", "Open a Python file"))
        file_menu.addAction(self.create_action("&Create File", self.create_file, "Ctrl+N", "Create a new Python file"))
        file_menu.addAction(self.create_action("Open &Folder", self.open_folder, "", "Open a folder for browsing"))
        file_menu.addAction(self.create_action("Create &Folder", self.create_folder, "", "Create a new folder"))
        file_menu.addSeparator()
        file_menu.addAction(self.create_action("&Exit", self.close, "Ctrl+Q", "Exit the application"))

        # Save Menu
        save_menu = menubar.addMenu('&Save')
        save_menu.addAction(self.create_action("Save &Inline", self.save_inline_comments, "Ctrl+I", "Save comments directly into the code"))
        save_menu.addAction(self.create_action("Save &Separate File", self.save_comment, "Ctrl+S", "Save comments to a separate file"))

        # Clear Menu
        clear_menu = menubar.addMenu('&Clear')
        clear_menu.addAction(self.create_action("Clear &Code", self.clear_program, "Ctrl+L", "Clear the code editor"))
        clear_menu.addAction(self.create_action("Clear &Comments", self.clear_comments, "Ctrl+E", "Clear the comments panel"))
        clear_menu.addAction(self.create_action("Clear &All", self.clear_all, "Ctrl+A", "Clear both panels"))

        # Settings Menu (Placeholder)
        settings_menu = menubar.addMenu('&Settings')
        settings_menu.addAction(self.create_action("&Placeholder", self.placeholder_action, "", "Placeholder for future settings"))
        
    def create_action(self, text, slot, shortcut="", tip=""):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.setStatusTip(tip)
        action.triggered.connect(slot)
        return action

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "Python Files (*.py);;All Files (*)")
        
        if file_path:
            self.current_file_path = file_path
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    self.code_editor.setPlainText(file.read())
                self.update_status(f"Opened file: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file: {str(e)}")

    def create_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Create File", "", "Python Files (*.py);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("# New Python File")
                self.update_status(f"Created file: {file_path}")
                self.code_editor.setPlainText("# New Python File")
                self.current_file_path = file_path
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create file: {str(e)}")
    
    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, "Open Folder", os.path.expanduser('~'))
        if folder_path:
            self.file_model.setRootPath(folder_path)
            self.file_view.setRootIndex(self.file_model.index(folder_path))
            self.update_status(f"Opened folder: {folder_path}")

    def create_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, "Create Folder In", os.path.expanduser('~'))
        if folder_path:
            new_folder_name, ok = QMessageBox.question(self, "Create Folder", "Enter new folder name:", QMessageBox.Yes)
            if ok and new_folder_name:
                try:
                    new_path = os.path.join(folder_path, new_folder_name)
                    os.makedirs(new_path)
                    self.update_status(f"Created folder: {new_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to create folder: {str(e)}")

    def save_inline_comments(self):
        code = self.code_editor.toPlainText()
        comments = self.comment_display.toPlainText()
        
        if not self.current_file_path:
            QMessageBox.warning(self, "Warning", "No file is open to save inline comments to.")
            return

        if not comments.strip():
            QMessageBox.warning(self, "Warning", "No comments to save inline.")
            return

        commented_code = ""
        # Simplified logic for demonstration: prepend a single comment
        comment_lines = comments.splitlines()
        commented_code += "# " + "\n# ".join(comment_lines) + "\n"
        commented_code += code
        
        try:
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                f.write(commented_code)
            self.update_status(f"Inline comments saved to {self.current_file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")

    def clear_program(self):
        self.code_editor.clear()
        self.update_status("Code editor cleared.")
        
    def clear_comments(self):
        self.comment_display.clear()
        self.update_status("Comments panel cleared.")
    
    def placeholder_action(self):
        QMessageBox.information(self, "Settings", "This is a placeholder for future settings.")

    def update_status(self, message):
        self.statusBar().showMessage(message)
    
    def on_file_selected(self, index):
        file_path = self.file_model.filePath(index)
        if os.path.isfile(file_path) and file_path.endswith('.py'):
            self.current_file_path = file_path
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    self.code_editor.setPlainText(file.read())
                self.update_status(f"Opened file: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file: {str(e)}")
        
    def save_comment(self):
        comment = self.comment_display.toPlainText()
        if not comment.strip():
            QMessageBox.warning(self, "Warning", "No comment to save.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Comment", "", "Text Files (*.txt);;All Files (*)")
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(comment)
                self.update_status(f"Comment saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
    
    def generate_comment(self):
        code_blocks = self.get_code_blocks(self.code_editor.toPlainText())

        if not code_blocks:
            QMessageBox.warning(self, "Warning", "No functions or classes found to comment.")
            return

        self.set_buttons_enabled(False)
        self.update_status(f"Found {len(code_blocks)} code blocks. Generating comments...")
        self.comment_display.setPlainText("")
        
        self.comment_thread = QThread()
        self.worker = CommentGeneratorWorker(code_blocks)
        self.worker.moveToThread(self.comment_thread)
        self.comment_thread.started.connect(self.worker.run)
        self.worker.finished_one.connect(self.on_comment_generated)
        self.worker.finished_all.connect(self.on_all_comments_generated)
        self.worker.error.connect(self.on_comment_error)
        self.comment_thread.start()

    def get_code_blocks(self, code):
        blocks = []
        try:
            tree = ast.parse(code)
            
            def find_blocks(node):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start_line = node.lineno - 1
                    end_line = getattr(node, 'end_lineno', len(code.splitlines()))
                    block_code = "\n".join(code.splitlines()[start_line:end_line])
                    blocks.append(block_code)
                for child in ast.iter_child_nodes(node):
                    find_blocks(child)
            
            find_blocks(tree)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse code: {str(e)}")
        return blocks

    def on_comment_generated(self, code, comment):
        html_comment = f"""
        <div style="background-color: #2b2b2b; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
            <p style="color: #cccccc; font-weight: bold;">Code Block:</p>
            <pre style="color: #cccccc; white-space: pre-wrap; font-family: Consolas;">{code}</pre>
            <p style="color: #569cd6; font-weight: bold;">Comment:</p>
            <p style="color: #b5cea8;">{comment}</p>
        </div>
        """
        self.comment_display.insertHtml(html_comment)

    def on_all_comments_generated(self):
        self.update_status("All comments generated successfully!")
        self.set_buttons_enabled(True)
        self.comment_thread.quit()
        self.comment_thread.wait()
    
    def on_comment_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)
        self.update_status("Error generating comment")
        self.set_buttons_enabled(True)
        self.comment_thread.quit()
        self.comment_thread.wait()
    
    def highlight_code(self, code):
        cursor = self.code_editor.document().find(code)
        if not cursor.isNull():
            extra_selections = []
            selection = QTextEdit.ExtraSelection()
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(QColor(255, 255, 0, 100))
            selection.format = highlight_format
            selection.cursor = cursor
            extra_selections.append(selection)
            self.code_editor.setExtraSelections(extra_selections)
            cursor = self.code_editor.textCursor()
            cursor.setPosition(selection.cursor.selectionStart())
            cursor.setPosition(selection.cursor.selectionEnd(), QTextCursor.KeepAnchor)
            self.code_editor.setTextCursor(cursor)
    
    def clear_all(self):
        self.code_editor.clear()
        self.comment_display.clear()
        self.update_status("Cleared all content")
    
    def set_buttons_enabled(self, enabled):
        self.open_btn.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        self.generate_btn.setEnabled(enabled)
        self.clear_btn.setEnabled(enabled)
    
    def closeEvent(self, event):
        if self.comment_thread and self.comment_thread.isRunning():
            reply = QMessageBox.question(
                self,
                'Comment Generation in Progress',
                'A comment is being generated. Are you sure you want to quit?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.comment_thread.terminate()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
