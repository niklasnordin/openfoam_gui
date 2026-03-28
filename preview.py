"""
Preview widget — displays generated OpenFOAM dictionary content with
basic syntax highlighting.
"""

from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont,
)
from PySide6.QtCore import QRegularExpression


class FoamHighlighter(QSyntaxHighlighter):
    """Simple syntax highlighter for OpenFOAM dictionaries."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._rules = []

        # Keywords
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#1565C0"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "FoamFile", "dimensions", "internalField", "boundaryField",
            "uniform", "type", "value", "solver", "smoother",
            "tolerance", "relTol", "true", "false", "on", "off",
            "yes", "no", "ascii", "binary",
        ]
        for word in keywords:
            pattern = QRegularExpression(rf"\b{word}\b")
            self._rules.append((pattern, kw_fmt))

        # Numbers
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#E65100"))
        self._rules.append((
            QRegularExpression(r"\b-?[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?\b"),
            num_fmt,
        ))

        # Comments
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6A9955"))
        self._rules.append((QRegularExpression(r"//[^\n]*"), comment_fmt))
        self._rules.append((QRegularExpression(r"/\*.*?\*/"), comment_fmt))

        # Braces
        brace_fmt = QTextCharFormat()
        brace_fmt.setForeground(QColor("#B71C1C"))
        brace_fmt.setFontWeight(QFont.Weight.Bold)
        self._rules.append((QRegularExpression(r"[{}()\[\]]"), brace_fmt))

        # Strings / patch names
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#6A1B9A"))
        self._rules.append((QRegularExpression(r'"[^"]*"'), str_fmt))

        # Header block
        header_fmt = QTextCharFormat()
        header_fmt.setForeground(QColor("#78909C"))
        self._rules.append((
            QRegularExpression(r"/\*[-\*\s\w|:\\/.=]*?\*/", QRegularExpression.PatternOption.DotMatchesEverythingOption),
            header_fmt,
        ))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

    def update_colours(self, settings):
        """Rebuild highlight rules from AppSettings and re-highlight."""
        self._rules.clear()

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor(settings.get("hl_keyword")))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "FoamFile", "dimensions", "internalField", "boundaryField",
            "uniform", "type", "value", "solver", "smoother",
            "tolerance", "relTol", "true", "false", "on", "off",
            "yes", "no", "ascii", "binary",
        ]
        for word in keywords:
            self._rules.append((QRegularExpression(rf"\b{word}\b"), kw_fmt))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor(settings.get("hl_number")))
        self._rules.append((
            QRegularExpression(r"\b-?[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?\b"),
            num_fmt,
        ))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor(settings.get("hl_comment")))
        self._rules.append((QRegularExpression(r"//[^\n]*"), comment_fmt))
        self._rules.append((QRegularExpression(r"/\*.*?\*/"), comment_fmt))

        brace_fmt = QTextCharFormat()
        brace_fmt.setForeground(QColor(settings.get("hl_brace")))
        brace_fmt.setFontWeight(QFont.Weight.Bold)
        self._rules.append((QRegularExpression(r"[{}()\[\]]"), brace_fmt))

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor(settings.get("hl_string")))
        self._rules.append((QRegularExpression(r'"[^"]*"'), str_fmt))

        header_fmt = QTextCharFormat()
        header_fmt.setForeground(QColor(settings.get("hl_header")))
        self._rules.append((
            QRegularExpression(r"/\*[-\*\s\w|:\\/.=]*?\*/",
                               QRegularExpression.PatternOption.DotMatchesEverythingOption),
            header_fmt,
        ))

        self.rehighlight()


class PreviewWidget(QPlainTextEdit):
    """Read-only text view with OpenFOAM syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        font = QFont("Monospace", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._highlighter = FoamHighlighter(self.document())

    def set_content(self, text: str):
        self.setPlainText(text)
