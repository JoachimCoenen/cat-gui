from __future__ import annotations

import copy
import enum
from dataclasses import dataclass, field, replace
from math import log10
from typing import ItemsView, Iterable, Iterator, NamedTuple, NewType, Optional, Protocol, TYPE_CHECKING, Type, Union, final

from PyQt5 import Qsci, sip
from PyQt5.Qsci import QsciAPIs, QsciLexer, QsciScintilla
from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QMouseEvent
from PyQt5.QtWidgets import QShortcut

from ..utilities import connectOnlyOnce, connectSafe
from ...GUI.components.catWidgetMixins import CORNERS, CatFocusableMixin, CatFramedAbstractScrollAreaMixin, CatSizePolicyMixin, CatStyledWidgetMixin, UndoBlockableMixin, palettes
from ...utils import DocEnum, HTMLStr, override
from ...utils.collections_ import AddToDictDecorator, OrderedDict, Stack
from ...utils.profiling import logWarning
from ...utils.utils import CrashReportWrapped

if TYPE_CHECKING:
	from ...GUI import PythonGUI

_m_allLexers: dict[str, Type[QsciLexer]] = {}

getAllLanguages = _m_allLexers.keys
CodeEditorLexer = AddToDictDecorator(_m_allLexers)


def getLexer(language: str) -> Optional[Type[QsciLexer]]:
	return _m_allLexers.get(language)


@dataclass
class AutoCompletionTree:
	qName: str
	separator: str
	nextSeparators: set[str] = field(default_factory=set)
	_children: OrderedDict[str, AutoCompletionTree] = field(default_factory=OrderedDict)

	def add(self, childName: str, separator: str) -> AutoCompletionTree:
		qChildName = self.qName + self.separator + childName
		child = AutoCompletionTree(qChildName, separator)
		self._children[childName] = child
		if separator:
			self.nextSeparators.add(separator)
		return child

	def get(self, childName: str) -> Optional[AutoCompletionTree]:
		return self._children.get(childName, None)

	def getOrAdd(self, childName: str, separator: str) -> AutoCompletionTree:
		child = self.get(childName)
		if child is None:
			child = self.add(childName, separator)
		elif not child.separator:
			child.separator = separator
			if separator:
				self.nextSeparators.add(separator)
		return child

	def addTree(self, other: AutoCompletionTree):
		prefix = self.qName + self.separator
		childIterators: Stack[Iterator[ItemsView[str, AutoCompletionTree]]] = Stack()
		newChildrenStack: Stack[OrderedDict[str, AutoCompletionTree]] = Stack()
		prefixStack: Stack[str] = Stack()

		childIterators.push(iter(other._children.items()))
		newChildrenStack.push(self._children)
		prefixStack.push(prefix)
		while childIterators:
			nextTree = next(childIterators.peek(), None)
			if nextTree is None:
				childIterators.pop()
				newChildrenStack.pop()
				prefixStack.pop()
			else:
				prefix = prefixStack.peek()
				name, nextTree = nextTree
				nextTreeI = AutoCompletionTree(prefix + name, nextTree.separator)
				nextTreeI.separator = nextTree.separator
				nextTreeI.nextSeparators = nextTree.nextSeparators
				newChildrenStack.peek()[name] = nextTreeI
				childIterators.push(iter(nextTree._children.items()))
				newChildrenStack.push(nextTreeI._children)
				prefixStack.push(nextTreeI.qName + nextTreeI.separator)

		self.nextSeparators = {ch.separator for ch in self._children.values()}
		self.nextSeparators.discard('')

	def addTreeCopy(self, other: AutoCompletionTree) -> AutoCompletionTree:
		self = replace(self, nextSeparators=self.nextSeparators.copy(), _children=self._children.copy())
		# self = copy.copy(self)
		self.addTree(other)
		return self

	def memberNames(self) -> Iterable[str]:
		return self._children.keys()

	def members(self) -> Iterable[AutoCompletionTree]:
		return self._children.values()

	def memberItems(self) -> ItemsView[str, AutoCompletionTree]:
		return self._children.items()


def _buildSplitterRegex(delimiters: Iterable[str]):
	import re
	escaped = list(map(re.escape, delimiters))
	return re.compile('|'.join(escaped))


def buildSimpleAutoCompletionTree(allChoices: Iterable[str], separators: tuple[str, ...]) -> AutoCompletionTree:
	result: AutoCompletionTree = AutoCompletionTree('', '')

	splittingPattern = _buildSplitterRegex(separators)

	for choice in sorted(allChoices):
		separatorMatches = splittingPattern.finditer(choice)
		tree = result
		start = 0
		for separatorMatch in separatorMatches:
			end = separatorMatch.start(0)
			chunck = choice[start:end]
			start = separatorMatch.end(0)
			separator = choice[end:start]
			tree = tree.getOrAdd(chunck, separator)
		# the last section:
		tree.getOrAdd(choice[start:], '')

	return result


def choicesFromAutoCompletionTree_WRONG(tree: AutoCompletionTree, text: str) -> list[str]:
	remainder: str = text
	word: str = text

	currentTree: Optional[AutoCompletionTree] = None
	nextTree: Optional[AutoCompletionTree] = tree
	while nextTree is not None:
		currentTree = nextTree
		nSep = currentTree.separator
		word, sep, remainder = remainder.partition(nSep)
		if sep:
			nextTree = currentTree.get(word)

	lastWord = word
	if not lastWord:
		return [word for word in currentTree.memberNames()]
	else:
		lastWordLower = lastWord.lower()
		return [word for word in currentTree.memberNames() if word.lower().startswith(lastWordLower)]


def choicesFromAutoCompletionTree(tree: AutoCompletionTree, text: str, addSeparator: bool = True, *, includePrefixes: bool = True) -> list[str]:
	result: list[str] = []
	currentTrees: list[tuple[AutoCompletionTree, str]] = []
	nextTrees: list[tuple[AutoCompletionTree, str]] = [(tree, text)]
	while nextTrees:
		currentTrees = nextTrees
		nextTrees = []
		for currentTree, remainder in currentTrees:
			# if not remainder or not currentTree.nextSeparators:
			# 	result.extend(currentTree.memberNames())
			sepFound: bool = False
			for nSep in currentTree.nextSeparators:
				word, sep, nextRemainder = remainder.partition(nSep)
				if sep:
					sepFound = True
					if (nextTree := currentTree.get(word)) is not None:
						nextTrees.append((nextTree, nextRemainder))
						break
			else:
				if not sepFound:
					if addSeparator:
						if includePrefixes:
							result.extend(mb.qName + mb.separator for mb in currentTree.members())
						else:
							result.extend(name + mb.separator for name, mb in currentTree.memberItems())
					else:
						if includePrefixes:
							result.extend(mb.qName for mb in currentTree.members())
						else:
							result.extend(currentTree.memberNames())

	return result


# IndexSpan = tuple[int, int]
class IndexSpan(NamedTuple):
	start: int
	end: int


class CEPosition(NamedTuple):
	line: int
	column: int

	def __iter__(self):
		yield self.line
		yield self.column


class IndexedPosition(Protocol):
	line: int
	column: int
	index: int


class Error(Protocol):
	message: str
	position: IndexedPosition
	end: IndexedPosition
	style: str  # a key from errorIndicatorStyles dict (see below)


# ====== misc. Enums: ======

class QsciBraceMatch(DocEnum):
	NoBraceMatch = QsciScintilla.NoBraceMatch, "Brace matching is disabled."
	StrictBraceMatch = QsciScintilla.StrictBraceMatch, "Brace matching is enabled for a brace immediately before the current position."
	SloppyBraceMatch = QsciScintilla.SloppyBraceMatch, "Brace matching is enabled for a brace immediately before or after the current position."


class QsciEolMode(DocEnum):
	EolWindows = QsciScintilla.EolWindows, "A carriage return/line feed as used on Windows systems."
	EolUnix = QsciScintilla.EolUnix, "A line feed as used on Unix systems, including OS/X."
	EolMac = QsciScintilla.EolMac, "A carriage return as used on Mac systems prior to OS/X."


# ====== indicators: ======

QSciIndicatorStyle = QsciScintilla.IndicatorStyle
# class QSciIndicatorStyle(DocEnum):
# 	PlainIndicator = QsciScintilla.INDIC_PLAIN, "A single straight underline."
# 	SquiggleIndicator = QsciScintilla.INDIC_SQUIGGLE, "A squiggly underline that requires 3 pixels of descender space."
# 	TTIndicator = QsciScintilla.INDIC_TT, "A line of small T shapes."
# 	DiagonalIndicator = QsciScintilla.INDIC_DIAGONAL, "Diagonal hatching."
# 	StrikeIndicator = QsciScintilla.INDIC_STRIKE, "Strike out."
# 	HiddenIndicator = QsciScintilla.INDIC_HIDDEN, "An indicator with no visual appearence."
# 	BoxIndicator = QsciScintilla.INDIC_BOX, "A rectangle around the text."
# 	RoundBoxIndicator = QsciScintilla.INDIC_ROUNDBOX, "A rectangle with rounded corners around the text with the interior usually more transparent than the border."
# 	StraightBoxIndicator = QsciScintilla.INDIC_STRAIGHTBOX, "A rectangle around the text with the interior usually more transparent than the border.  It does not colour the top pixel of the line so that indicators on contiguous lines are visually distinct and disconnected."
# 	FullBoxIndicator = QsciScintilla.INDIC_FULLBOX, "A rectangle around the text with the interior usually more transparent than the border.  Unlike StraightBoxIndicator it covers the entire character area."
# 	DashesIndicator = QsciScintilla.INDIC_DASH, "A dashed underline."
# 	DotsIndicator = QsciScintilla.INDIC_DOTS, "A dotted underline."
# 	SquiggleLowIndicator = QsciScintilla.INDIC_SQUIGGLELOW, "A squiggly underline that requires 2 pixels of descender space and so will fit under smaller fonts."
# 	DotBoxIndicator = QsciScintilla.INDIC_DOTBOX, "A dotted rectangle around the text with the interior usually more transparent than the border."
# 	SquigglePixmapIndicator = QsciScintilla.INDIC_SQUIGGLEPIXMAP, "A version of SquiggleIndicator that uses a pixmap.  This is quicker but may be of lower quality."
# 	ThickCompositionIndicator = QsciScintilla.INDIC_COMPOSITIONTHICK, "A thick underline typically used for the target during Asian language input composition."
# 	ThinCompositionIndicator = QsciScintilla.INDIC_COMPOSITIONTHIN, "A thin underline typically used for non-target ranges during Asian language input composition."
# 	TextColorIndicator = QsciScintilla.INDIC_TEXTFORE, "The color of the text is set to the color of the indicator's foreground."
# 	TriangleIndicator = QsciScintilla.INDIC_POINT, "A triangle below the start of the indicator range."
# 	TriangleCharacterIndicator = QsciScintilla.INDIC_POINTCHARACTER, "A triangle below the centre of the first character in the indicator range."
# 	GradientIndicator = QsciScintilla.INDIC_GRADIENT, "A vertical gradient between the indicator's foreground colour at top to fully transparent at the bottom."
# 	CentreGradientIndicator = QsciScintilla.INDIC_GRADIENTCENTRE, "A vertical gradient with the indicator's foreground colour in the middle and fading to fully transparent at the top and bottom."


@dataclass
class IndicatorStyle:
	style:           QSciIndicatorStyle
	hoverStyle:      QSciIndicatorStyle
	drawUnder:       bool
	foreground:      QColor
	hoverForeground: QColor
	outline:         Optional[QColor]


class Indicator(enum.IntEnum):
	Error = 0
	Warning = 1
	Info = 2
	Fallback = 3
	SearchResult = 4
	MatchedBrace = 5
	Link = 6


DEFAULT_INDICATOR_STYLES = {
	Indicator.Error: IndicatorStyle(
		style=QSciIndicatorStyle.SquiggleIndicator,
		hoverStyle=QSciIndicatorStyle.SquiggleIndicator,
		drawUnder=True,
		foreground=     QColor(0xFF0000),
		hoverForeground=QColor(0xFF0000),
		outline=None
	),
	Indicator.Warning: IndicatorStyle(
		style=QSciIndicatorStyle.SquiggleIndicator,
		hoverStyle=QSciIndicatorStyle.SquiggleIndicator,
		drawUnder=True,
		foreground=     QColor(0x9F8800),
		hoverForeground=QColor(0x9F8800),
		outline=None
	),
	Indicator.Info: IndicatorStyle(
		style=QSciIndicatorStyle.SquiggleIndicator,
		hoverStyle=QSciIndicatorStyle.SquiggleIndicator,
		drawUnder=True,
		foreground=     QColor(0x0072FF),
		hoverForeground=QColor(0x0072FF),
		outline=None
	),
	Indicator.Fallback: IndicatorStyle(
		style=QSciIndicatorStyle.SquiggleIndicator,
		hoverStyle=QSciIndicatorStyle.SquiggleIndicator,
		drawUnder=True,
		foreground=     QColor(0x3D8C52),
		hoverForeground=QColor(0x3D8C52),
		outline=None
	),
	Indicator.SearchResult: IndicatorStyle(
		style=QSciIndicatorStyle.StraightBoxIndicator,
		hoverStyle=QSciIndicatorStyle.StraightBoxIndicator,
		drawUnder=True,
		foreground=     QColor(0x2F, 0x8C, 0x48, 0x48),
		hoverForeground=QColor(0x2F, 0x8C, 0x48, 0x48),
		outline=        QColor(0x3D, 0x8C, 0x52, 0x79)
	),
	Indicator.MatchedBrace: IndicatorStyle(
		style=QSciIndicatorStyle.StraightBoxIndicator,
		hoverStyle=QSciIndicatorStyle.StraightBoxIndicator,
		drawUnder=True,
		foreground=     QColor(0x00, 0x6F, 0xCC, 0x28),
		hoverForeground=QColor(0x00, 0x6F, 0xCC, 0x28),
		outline=        QColor(0x1D, 0x2D, 0x9C, 0x79)
	),
	Indicator.Link: IndicatorStyle(
		style=QSciIndicatorStyle.HiddenIndicator,
		hoverStyle=QSciIndicatorStyle.PlainIndicator,
		drawUnder=True,
		foreground=     QColor(0x0072FF),
		hoverForeground=QColor(0x0000FF),
		outline=None
	)
}


indicatorStyles: dict[Indicator, IndicatorStyle] = copy.deepcopy(DEFAULT_INDICATOR_STYLES)


def setIndicatorStyles(newIndicatorStyles: dict[Indicator, IndicatorStyle]) -> None:
	global indicatorStyles
	indicatorStyles = copy.copy(DEFAULT_INDICATOR_STYLES)
	if newIndicatorStyles is not None:
		for indicator, style in newIndicatorStyles.items():
			indicatorStyles[indicator] = style
	else:
		pass


errorIndicatorStyles: dict[str, Indicator] = {
	'error': Indicator.Error,
	'warning': Indicator.Warning,
	'info': Indicator.Info,
	'default': Indicator.Fallback,
}


@dataclass
class CallTipInfo:
	name: str
	description: HTMLStr


# ====== QsciAPIs: ======
class MyQsciAPIs(QsciAPIs):
	def __init__(self, lexer: Optional[QsciLexer]):
		super(MyQsciAPIs, self).__init__(lexer)
		self._autoCompletionTree = AutoCompletionTree('', '')

	@final
	def autoCompletionSelected(self, selection: str) -> None:
		"""
		override postAutoCompletionSelected(...) instead of this method.
		:param selection:
		:return:
		"""
		lexer: QsciLexer = self.lexer()
		if lexer is not None:
			editor: QsciScintilla = lexer.editor()
			if isinstance(editor, CodeEditor):
				editor._onUserListActivated(0, selection)  # would be better in class CodeEditor, but we cannot override the appropriate method there... :(
				editor.SendScintilla(editor.SCI_AUTOCCANCEL)
				return
		self.postAutoCompletionSelected(selection)

	def postAutoCompletionSelected(self, selection: str) -> None:
		pass

	@property
	def autoCompletionTree(self) -> AutoCompletionTree:
		return self._autoCompletionTree

	@autoCompletionTree.setter
	def autoCompletionTree(self, value: AutoCompletionTree):
		self._autoCompletionTree = value

	@CrashReportWrapped
	def updateAutoCompletionList(self, context: Iterable[str], aList: Iterable[str]) -> list[str]:
		"""
		Update the list \a list with API entries derived from \a context.  \a
		context is the list of words in the text preceding the cursor position.
		The characters that make up a word and the characters that separate
		words are defined by the lexer.  The last word is a partial word and
		may be empty if the user has just entered a word separator.
		"""
		currentTree: Optional[AutoCompletionTree] = self.autoCompletionTree
		lastTree: AutoCompletionTree = currentTree
		currentWord: str = ''
		for contextWord in context:
			if currentTree is None:
				break
			lastTree = currentTree
			currentTree = lastTree.get(contextWord)
			currentWord = contextWord

		lastWord = currentWord
		if not lastWord:
			return [word for word in lastTree.memberNames()]
		else:
			lastWordLower = lastWord.lower()
			return [word for word in lastTree.memberNames() if word.lower().startswith(lastWordLower)]

	def getHoverTip(self, position: CEPosition) -> Optional[HTMLStr]:
		return None

	def getCallTips(self, position: CEPosition) -> list[CallTipInfo]:
		return []

	def getClickableRanges(self) -> list[tuple[CEPosition, CEPosition]]:
		return []

	def indicatorClicked(self, position: CEPosition, state: Qt.KeyboardModifiers) -> None:
		pass

	def autoCompletionWordSeparators(self) -> list[str]:
		return ['.']  # ':', '#', '.']


# ====== CodeEditor class: ======

class SearchMode(DocEnum):
	Normal = 0
	UnicodeEscaped = 1
	RegEx = 2


@dataclass
class SearchOptions:
	searchMode: SearchMode
	isCaseSensitive: bool
	isMultiLine: bool


char = NewType('char', str)


class CodeEditor(
	CatFocusableMixin,
	UndoBlockableMixin,
	CatFramedAbstractScrollAreaMixin,
	QsciScintilla,
	CatSizePolicyMixin,
	CatStyledWidgetMixin
):
	SCI_SETELEMENTCOLOUR = 2753
	SCI_GETELEMENTCOLOUR = 2754
	SCI_RESETELEMENTCOLOUR = 2755
	SCI_GETELEMENTISSET = 2756
	SCI_GETELEMENTALLOWSTRANSLUCENT = 2757
	SCI_GETELEMENTBASECOLOUR = 2758

	def __init__(self, parent=None):
		super().__init__(parent)
		self._roundedCorners = CORNERS.NONE
		self._colorPalette = palettes.inputColorPaletteB
		self._highlightOnFocus = True
		self.setLineWidth(1)

		self.setUtf8(True)  # Set encoding to UTF-8
		self.setTabWidth(4)
		self._language = 'PlainText'
		self._searchResults: list[tuple[int, int, int, int]] = []

		brightness = 0xE0
		self.setCaretLineBackgroundColor(QColor(brightness, brightness, brightness))

		self.setMarginLineNumbers(1, True)
		connectSafe(self.linesChanged, lambda self=self: self._onLinesChanged())
		self.setFolding(QsciScintilla.PlainFoldStyle)

		connectSafe(self.cursorPositionChanged, self._onCursorPositionChanged)
		self.cursorPositionChanged = self.cursorPositionChanged_
		self._cursorPosition: tuple[int, int] = (0, 0)  # see `getCursorPosition()`

		connectSafe(self.selectionChanged, self._onSelectionChanged)
		self._selection: tuple[int, int, int, int] = (-1, -1, -1, -1)  # see `getSelection()`

		connectSafe(self.textChanged, self._onTextChanged)
		connectSafe(self.indicatorClicked, self._onIndicatorClicked)
		connectSafe(self.userListActivated, self._onUserListActivated)

		self.setAutoCompletionThreshold(1)
		self.setAutoCompletionSource(QsciScintilla.AcsAPIs)
		self.setCallTipsPosition(self.CallTipsAboveText)

		self.initIndicatorStyles(indicatorStyles)
		self.setMatchedBraceIndicator(Indicator.MatchedBrace.value)

		#QShortcut(Qt.ControlModifier | Qt.Key_Space, self, lambda: self.showUserList(1, self.buildUserList()) if not sip.isdeleted(self) else None, lambda: None, Qt.WidgetShortcut)
		QShortcut(Qt.ControlModifier | Qt.Key_Space, self, CrashReportWrapped(lambda: self.myStartAutoCompletionOrCallTips() if not sip.isdeleted(self) else None), lambda: None, Qt.WidgetShortcut)
		QShortcut(Qt.ControlModifier | Qt.Key_K, self, CrashReportWrapped(lambda: self.showCallTips() if not sip.isdeleted(self) else None), lambda: None, Qt.WidgetShortcut)

	@CrashReportWrapped
	def _onUserListActivated(self, id: int, selection: str) -> None:
		li = self.getCursorPosition()
		pos = self.positionFromLineIndex(*li)
		ctx, i, j = self.apiContext(pos)
		if ctx and ctx[-1]:
			#j = pos - len(bytes(ctx[-1], 'utf-8'))
			self.SendScintilla(QsciScintilla.SCI_DELETERANGE, j, pos - j)
			li2 = self.lineIndexFromPosition(j)
		else:
			li2 = li
			j = pos
		self.insertAt(selection, *li2)
		li3 = self.lineIndexFromPosition(j + len(selection))
		self.setCursorPosition(*li3)
		if id != 0:
			if (api := self._catQSciAPIs) is not None:
				api.postAutoCompletionSelected(selection)

	# custom Calltip handling:

	def showCallTips(self) -> None:
		li = CEPosition(*self.getCursorPosition())
		pos = self.positionFromLineIndex(*li)
		if (api := self._catQSciAPIs) is not None:
			callTips = api.getCallTips(li)
			if callTips is not None:
				callTipsStr = '\n'.join(ct.name for ct in callTips)
				callTipsBytes = bytes(callTipsStr, 'utf-8')
				self.setCallTipsVisible(0)
				self.SendScintilla(self.SCI_CALLTIPSHOW, pos, callTipsBytes)

	def hideCallTips(self) -> None:
		self.SendScintilla(self.SCI_CALLTIPCANCEL)

	def myStartAutoCompletionOrCallTips(self) -> None:
		if not self.myStartAutoCompletion():
			self.showCallTips()

	def myStartAutoCompletion(self) -> bool:
		ctx, i, j = self._getCurrentAPIContext()
		if True or not ctx:
			userList = self.buildUserList()
			if userList:
				self.showUserList(1, userList)
				return True
		else:
			# self.startAutoCompletion(QsciScintilla.AcsAPIs, False, False)
			self.autoCompleteFromAPIs()  # autoCompletionSelected API
			return False

	# def showUserList(self, id: int, list: Iterable[str]) -> None:
	# 	ctx, i, j = self._currentAPIContext
	# 	self.SendScintilla(QsciScintilla.SCI_SETEMPTYSELECTION, i)
	# 	super(CodeEditor, self).showUserList(id, list)
	# 	#self.SendScintilla(QsciScintilla.SCI_SETEMPTYSELECTION, pos)

	def buildUserList(self) -> list[str]:
		if (api := self._catQSciAPIs) is not None:
			ctx, i, j = self._getCurrentAPIContext()
			userList = api.updateAutoCompletionList(ctx, [])
			# if ctx:
			# 	ctx0 = ctx[0]
			# 	userList = [t for t in userList if t.startswith(ctx0)]
			return userList
		return []

	def initIndicatorStyles(self, styles: dict[Indicator, IndicatorStyle]):
		for indicator, style in styles.items():
			self.indicatorDefine(style.style, indicator.value)
			self.setIndicatorHoverStyle(style.hoverStyle, indicator.value)
			self.setIndicatorDrawUnder(style.drawUnder, indicator.value)
			self.setIndicatorForegroundColor(style.foreground, indicator.value)
			self.setIndicatorHoverForegroundColor(style.hoverForeground, indicator.value)
			if style.outline is not None:
				self.setIndicatorOutlineColor(style.outline, indicator.value)

	@CrashReportWrapped
	def _onLinesChanged(self) -> None:
		self.setMarginWidth(1, self.fontMetrics().width('M' * int(log10(self.lines()) + 1)) + 6)

	mousePressed = pyqtSignal(QMouseEvent)
	mouseReleased = pyqtSignal(QMouseEvent)
	mouseMoved = pyqtSignal(QMouseEvent)
	cursorPositionChanged_ = pyqtSignal(int, int)
	selectionChanged2 = pyqtSignal(int, int, int, int)

	@CrashReportWrapped
	def _onCursorPositionChanged(self, a: int, b: int):
		cp = super(CodeEditor, self).getCursorPosition()
		self._cursorPosition = cp  # see `getCursorPosition()`
		self.cursorPositionChanged_.emit(*cp)

	@override
	@CrashReportWrapped
	def getCursorPosition(self) -> tuple[int, int]:
		"""
		hides super().getCursorPosition(), which is NOT virtual.
		This construct prevents an issue, when the cursorPosition() changes, while
		python is busy and before cursorPositionChanged can be fired
		"""
		# return super(CodeEditor, self).getCursorPosition()
		return self._cursorPosition

	@override
	@CrashReportWrapped
	def setCursorPosition(self, line: int, index: int) -> None:
		"""
		overrides super().setCursorPosition(int line, int index)
		see getCursorPosition() for detailed description
		"""
		if self.getCursorPosition() != (line, index):
			super(CodeEditor, self).setCursorPosition(line, index)
		self._cursorPosition = (line, index)

	@CrashReportWrapped
	def _onSelectionChanged(self):
		cp = super(CodeEditor, self).getSelection()
		self._selection = cp  # see `getSelection()`
		self.selectionChanged2.emit(*cp)

	@override
	@CrashReportWrapped
	def getSelection(self) -> tuple[int, int, int, int]:
		"""
		hides super().getCursorPosition(), which is NOT virtual.
		This construct prevents an issue, when the cursorPosition() changes, while
		python is busy and before cursorPositionChanged can be fired
		"""
		# return super(CodeEditor, self).getSelection()
		return self._selection

	@override
	@CrashReportWrapped
	def setSelection(self, line1: int, index1: int, line2: int, index2: int) -> None:
		"""
		overrides super().setCursorPosition(int line, int index)
		see getCursorPosition() for detailed description
		"""
		super(CodeEditor, self).setSelection(line1, index1, line2, index2)
		self._selection = (line1, index1, line2, index2)

	def setCaretPos(self, line: int, index: int):
		self.setCursorPosition(line, index)

	def highlightLine(self, line: int):
		self.ensureLineVisible(line)
		self.SendScintilla(QsciScintilla.SCI_SETFOCUS, True)

	def setCaretPosAndHighlightLine(self, line: int, index: int):
		self.setCaretPos(line, index)
		self.highlightLine(line)

	def cePositionFromIndex(self, index: int) -> CEPosition:
		return CEPosition(*self.lineIndexFromPosition(index))

	@CrashReportWrapped
	def _onTextChanged(self) -> None:
		if (api := self._catQSciAPIs) is not None:
			lines = self.lines()
			self.clearIndicatorRange(0, 0, lines - 1, self.lineLength(lines - 1) - 1, Indicator.Link.value)
			clickableRanges = api.getClickableRanges()
			for range in clickableRanges:
				range = (*range[0], *range[1])
				self.fillIndicatorRange(*range, Indicator.Link.value)

	@CrashReportWrapped
	def _onIndicatorClicked(self, line: int, index: int, state: Qt.KeyboardModifiers) -> None:
		if (api := self._catQSciAPIs) is not None:
			api.indicatorClicked(CEPosition(line, index), state)

	def language(self):
		return self._language

	def setLanguage(self, language: str):
		if self._language == language:
			return

		Lexer = getLexer(language)
		if Lexer is None:
			logWarning(f"Cannot find a lexer for language {repr(language)}. Setting lexer to 'None'")
			self.setLexer(None)
		else:
			lexer = Lexer(self)
			self.setLexer(lexer)
		self._language = language

	def highlightSearchResults(self, searchResults: list[IndexSpan]):
		lines = self.lines()
		self.clearIndicatorRange(0, 0, lines - 1, self.lineLength(lines - 1) - 1, Indicator.SearchResult.value)

		self._searchResults = []
		iterator: Iterator[tuple[int, IndexSpan]] = enumerate(searchResults)
		for i, result in iterator:
			resultPos = (
				*self.lineIndexFromPosition(result[0]),
				*self.lineIndexFromPosition(result[1]),
			)
			self.fillIndicatorRange(*resultPos, Indicator.SearchResult.value)
			self._searchResults.append(resultPos)
			if i > 1000:
				break

	def nextSearchResult(self):
		if not self._searchResults:
			return
		line, index = self.getCursorPosition()

		nextSr = next((sr for sr in self._searchResults if sr[0] > line or (sr[0]==line and sr[1] >= index)), self._searchResults[0])
		self.setSelection(*nextSr)

	def prevSearchResult(self):
		if not self._searchResults:
			return
		line, index = self.getCursorPosition()

		nextSr = next((sr for sr in reversed(self._searchResults) if sr[2] < line or (sr[2]==line and sr[3] < index)), self._searchResults[-1])
		self.setSelection(*nextSr)

	def autoCompletionTree(self) -> Optional[AutoCompletionTree]:
		return getattr(self.lexer(), 'autoCompletionTree', lambda: None)()

	def setAutoCompletionTree(self, tree: AutoCompletionTree):
		lexer = self.lexer()
		if hasattr(lexer, 'setAutoCompletionTree'):
			lexer.setAutoCompletionTree(tree)
		else:
			# TODO: decide what to do when lexer has no setAutoCompletionTree(...) method
			pass

	@property
	def _catQSciAPIs(self) -> Optional[MyQsciAPIs]:
		if (lexer := self.lexer()) is not None:
			api = lexer.apis()
			if isinstance(api, MyQsciAPIs):
				return api
		return None

	@CrashReportWrapped
	def apiContext(self, pos: int) -> tuple[list[str], int, int]:
		ctx: list[str]
		ctx, ctxStart, lastWordStart = super(CodeEditor, self).apiContext(pos)
		if ctx:
			# make sure, that the last word in ctx is actually split correctly!
			wordSeps = self.wordSeparators

			ctx2 = []
			for ws in wordSeps:
				for word in ctx:
					words = word.rsplit(ws)
					ctx2 += words
				lastWordStart += len(ctx[-1]) - len(ctx2[-1])
				ctx, ctx2 = ctx2, ctx
				ctx2.clear()

		return ctx, ctxStart, lastWordStart

	def _getCurrentAPIContext(self) -> tuple[list[str], int, int]:
		li = self.getCursorPosition()
		pos = self.positionFromLineIndex(*li)
		ctx, i, j = self.apiContext(pos)
		return ctx, i, j

	# Overriden QScintilla methods:

	# @override
	# @CrashReportWrapped
	# def apiContext(self, pos: int) -> tuple[list[str], int, int]:
	# 	lexer = self.lexer()
	# 	if hasattr(lexer, 'getApiContext'):
	# 		return lexer.getApiContext(pos, self)
	# 	else:
	# 		# return self.apiContextX(pos)
	# 		return super(CodeEditor, self).apiContext(pos)

	@property
	def wordSeparators(self) -> list[str]:
		lexer = self.lexer()
		if lexer is not None:
			return lexer.autoCompletionWordSeparators()
		else:
			return []

	@override
	@CrashReportWrapped
	def wordCharacters(self):
		lexer = self.lexer()
		if lexer is not None:
			return lexer.wordCharacters()
		else:
			return "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"

	def positionAt(self, pos: QPoint) -> int:
		y = pos.y()
		if 0 > y:
			return 0
		elif y >= (4_294_967_295-1):
			return self.length()
		x = pos.x()
		if 0 > x:
			x = 0
		elif x >= (4_294_967_295-1):
			x = self.width()
		return self.SendScintilla(QsciScintilla.SCI_CHARPOSITIONFROMPOINT, x, y)

	@override
	def getBorderBrushes(self, rect: QRect) -> tuple[QBrush, QBrush, QBrush]:
		self.initIndicatorStyles(indicatorStyles)
		return self.getBorderBrush(), self.getBorderBrush2(), QBrush(Qt.NoBrush)

	@override
	@CrashReportWrapped
	def mousePressEvent(self, event: QMouseEvent) -> None:
		super(CodeEditor, self).mousePressEvent(event)
		self.mousePressed.emit(event)

	@override
	@CrashReportWrapped
	def mouseReleaseEvent(self, event: QMouseEvent) -> None:
		super(CodeEditor, self).mouseReleaseEvent(event)
		self.mouseReleased.emit(event)

	@override
	@CrashReportWrapped
	def mouseMoveEvent(self, event: QMouseEvent) -> None:
		super(CodeEditor, self).mouseMoveEvent(event)
		if (api := self._catQSciAPIs) is not None:
			pos = self.positionAt(event.pos())
			lineIndex = self.cePositionFromIndex(pos)
			tip = api.getHoverTip(lineIndex)
			self.setToolTip(tip)
			# TODO use SCN_DWELLSTART and SCN_DWELLEND notifications for hoverTips

		self.mouseMoved.emit(event)

	# Compatibility:
	def isCaretLineVisible(self) -> bool:
		return self.SendScintilla(QsciScintilla.SCI_GETCARETLINEVISIBLE)

	if TYPE_CHECKING:
		def lexer(self) -> QsciLexer:
			return super(CodeEditor, self).lexer()


def _innerAdvancedCodeField(
		gui: 'PythonGUI',
		code: Optional[str],
		label=None,
		language: str = 'PlainText',
		isMultiline=True,
		focusEndOfText: bool = False,
		cursorPosition: tuple[int, int] = None,
		selectionTo: tuple[int, int] = None,
		searchResults: Optional[list[IndexSpan]] = None,
		prev: bool = False,
		next: bool = False,
		searchOptions: Optional[SearchOptions] = None,
		**kwargs
) -> CodeEditor:
	# style: Style = getStyles().fixedWidthChar
	# explicitStyle: Optional[Style] = kwargs.get('style', None)
	# if explicitStyle is not None:
	# 	style += explicitStyle
	# style = Style({'CodeEditor': style})
	# kwargs['style'] = style
	kwargs.setdefault('caretLineVisible', True)
	kwargs.setdefault('eolMode', QsciEolMode.EolUnix.value)
	kwargs.setdefault('scrollWidthTracking', True)
	if 'onInit' in kwargs:  # TODO: add propper onInit handlig to all widgets, that recieve the setMinimumFieldWisth treatement.
		kwargs['onInit'] = lambda x, onInit=kwargs['onInit']: gui.setMinimumFieldWidth(x) or onInit(x)
	else:
		kwargs['onInit'] = gui.setMinimumFieldWidth
	codeField: CodeEditor = gui.addLabeledItem(CodeEditor, label, language=language, **kwargs)

	font = kwargs.get('font', codeField.font())  # QFont('Consolas', 9)  #, italic=True)
	codeField.setMarginsFont(font)
	lexer: QsciLexer = codeField.lexer()
	if lexer is not None:
		lexer.setFont(font)
		lexer.setDefaultFont(font)

	textChanged = codeField.text() != code and code is not None
	isModifiedInput = codeField == gui.modifiedInput[0]
	if not isModifiedInput and textChanged:
		prevCursorPosition = codeField.getCursorPosition()
		codeField.setText(code)

		if not cursorPosition:
			if focusEndOfText:
				lines = code.splitlines()
				newCursorPosition = (len(lines), 0)  # TODO: INVESTIGATE: isn't this wrong, bc len(lines) is 1 beyond last line?
			else:
				lines = code.splitlines()
				lineNo = min(len(lines) - 1, prevCursorPosition[0])
				try:
					columNo = min(len(lines[lineNo]), prevCursorPosition[1]) if len(lines) > 0 else 0
				except Exception:
					print(f"===========================================================================")
					print(f"code = {repr(code)}")
					print(f"lines = {repr(lines)}")
					print(f"lineNo = {repr(lineNo)}")
					print(f"prevCursorPosition = {repr(prevCursorPosition)}")
					print(f"===========================================================================")
					raise
				newCursorPosition = (lineNo, columNo)
			codeField.setCaretPosAndHighlightLine(*newCursorPosition)
	if cursorPosition is not None and not isModifiedInput:
		prevCursorPosition = codeField.getCursorPosition()
		if textChanged or prevCursorPosition != cursorPosition:
			codeField.setCaretPosAndHighlightLine(*cursorPosition)
		if selectionTo is not None:
			prevSelectionTo = codeField.getSelection()[2:]
			if prevSelectionTo != selectionTo:
				codeField.setSelection(*cursorPosition, *selectionTo)

	# searchResults:
	codeField.highlightSearchResults(searchResults or [])

	if next:
		codeField.nextSearchResult()
	if prev:
		codeField.prevSearchResult()
		# codeField.getCursorPosition()
		# if searchOptions is None:
		# 	codeField.findFirst(searchExpr, False, False, False, True, not rev)# , *codeField.getCursorPosition())
		# else:
		# 	codeField.findFirst(searchExpr, searchOptions.isRegex, searchOptions.isCaseSensitive, False, True, not rev)# , *codeField.getCursorPosition())
		# if rev:
		# 	codeField.findNext()

	connectOnlyOnce(codeField, codeField.textChanged, lambda: gui.OnInputModified(codeField), '_OnInputModified_')
	return codeField


def advancedCodeField(
		gui: 'PythonGUI',
		code: Optional[str],
		label=None,
		language: str = 'PlainText',
		isMultiline=True,
		focusEndOfText: bool = False,
		cursorPosition: tuple[int, int] = None,
		selectionTo: tuple[int, int] = None,
		searchResults: Optional[list[IndexSpan]] = None,
		prev: bool = False,
		next: bool = False,
		searchOptions: Optional[SearchOptions] = None,
		returnCursorPos: bool = False,
		errors: list[Error] = None,
		**kwargs
) -> Union[str, tuple[str, tuple[int, int]]]:
	codeField: CodeEditor = _innerAdvancedCodeField(gui, code, label, language, isMultiline, focusEndOfText, cursorPosition, selectionTo, searchResults, prev, next, searchOptions, **kwargs)

	# handle possible custom errorRanges:
	# clear all old error markers:
	fullRange = (*codeField.lineIndexFromPosition(0), *codeField.lineIndexFromPosition(len(codeField.text())))
	codeField.clearIndicatorRange(*fullRange, Indicator.Error.value)
	codeField.clearIndicatorRange(*fullRange, Indicator.Warning.value)
	codeField.clearIndicatorRange(*fullRange, Indicator.Info.value)

	# add all new error markers:
	if errors is not None:
		for error in errors:
			indicator = errorIndicatorStyles.get(error.style, Indicator.Error.value)
			# begin = tuple(error.position)
			# end = tuple(error.end)
			begin = codeField.cePositionFromIndex(error.position.index)
			end = codeField.cePositionFromIndex(error.end.index)
			if end == begin:
				end = (end[0], end[1] + 1)
			codeField.fillIndicatorRange(*begin, *end, indicator)

	result: str = codeField.text()  # .replace('\r\n', '\n')
	if returnCursorPos:
		return result, codeField.getCursorPosition()
	else:
		return result


CodeEditorLexer('AVS')(Qsci.QsciLexerAVS)
CodeEditorLexer('Bash')(Qsci.QsciLexerBash)
CodeEditorLexer('Batch')(Qsci.QsciLexerBatch)
CodeEditorLexer('CMake')(Qsci.QsciLexerCMake)
CodeEditorLexer('CoffeeScript')(Qsci.QsciLexerCoffeeScript)
CodeEditorLexer('CPP')(Qsci.QsciLexerCPP)
CodeEditorLexer('CSharp')(Qsci.QsciLexerCSharp)
CodeEditorLexer('CSS')(Qsci.QsciLexerCSS)
CodeEditorLexer('D')(Qsci.QsciLexerD)
CodeEditorLexer('Diff')(Qsci.QsciLexerDiff)
CodeEditorLexer('Fortran')(Qsci.QsciLexerFortran)
CodeEditorLexer('Fortran77')(Qsci.QsciLexerFortran77)
CodeEditorLexer('HTML')(Qsci.QsciLexerHTML)
CodeEditorLexer('IDL')(Qsci.QsciLexerIDL)
CodeEditorLexer('Java')(Qsci.QsciLexerJava)
CodeEditorLexer('JavaScript')(Qsci.QsciLexerJavaScript)
CodeEditorLexer('JSON')(Qsci.QsciLexerJSON)
CodeEditorLexer('Lua')(Qsci.QsciLexerLua)
CodeEditorLexer('Makefile')(Qsci.QsciLexerMakefile)
CodeEditorLexer('Markdown')(Qsci.QsciLexerMarkdown)
CodeEditorLexer('Matlab')(Qsci.QsciLexerMatlab)
CodeEditorLexer('Octave')(Qsci.QsciLexerOctave)
CodeEditorLexer('Pascal')(Qsci.QsciLexerPascal)
CodeEditorLexer('Perl')(Qsci.QsciLexerPerl)
CodeEditorLexer('PO')(Qsci.QsciLexerPO)
CodeEditorLexer('PostScript')(Qsci.QsciLexerPostScript)
CodeEditorLexer('POV')(Qsci.QsciLexerPOV)
CodeEditorLexer('Properties')(Qsci.QsciLexerProperties)
CodeEditorLexer('Python')(Qsci.QsciLexerPython)
CodeEditorLexer('Ruby')(Qsci.QsciLexerRuby)
CodeEditorLexer('Spice')(Qsci.QsciLexerSpice)
CodeEditorLexer('SQL')(Qsci.QsciLexerSQL)
CodeEditorLexer('TCL')(Qsci.QsciLexerTCL)
CodeEditorLexer('TeX')(Qsci.QsciLexerTeX)
CodeEditorLexer('Verilog')(Qsci.QsciLexerVerilog)
CodeEditorLexer('VHDL')(Qsci.QsciLexerVHDL)
CodeEditorLexer('XML')(Qsci.QsciLexerXML)
CodeEditorLexer('YAML')(Qsci.QsciLexerYAML)
CodeEditorLexer('PlainText')(lambda *x: None)
