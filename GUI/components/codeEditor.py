from __future__ import annotations

import copy
import enum
from collections import OrderedDict
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
from ...utils.collections_ import AddToDictDecorator, Stack
from ...utils.profiling import logWarning
from ...utils.utils import CrashReportWrapped

try:
	from recordclass import as_dataclass
except ImportError:
	HAS_RECORDCLASS = False
	as_dataclass = None
else:
	HAS_RECORDCLASS = True


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
		childIterators: Stack[Iterator[tuple[str, AutoCompletionTree]]] = Stack()
		newChildrenStack: Stack[OrderedDict[str, AutoCompletionTree]] = Stack()
		prefixStack: Stack[str] = Stack()

		childIterators.push(iter(other._children.items()))
		newChildrenStack.push(self._children)
		prefixStack.push(prefix)
		while childIterators:
			nextTreeTpl = next(childIterators.peek(), None)
			if nextTreeTpl is None:
				childIterators.pop()
				newChildrenStack.pop()
				prefixStack.pop()
			else:
				prefix = prefixStack.peek()
				name, nextTree = nextTreeTpl
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


def choicesFromAutoCompletionTree(tree: AutoCompletionTree, text: str, addSeparator: bool = True, *, includePrefixes: bool = True) -> list[str]:
	result: list[str] = []
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


if HAS_RECORDCLASS:
	@as_dataclass(sequence=True, readonly=True, fast_new=True)
	class IndexSpan:
		start: int
		end: int
else:
	class IndexSpan(NamedTuple):
		start: int
		end: int


if HAS_RECORDCLASS:
	@as_dataclass(sequence=True, readonly=True, fast_new=True)
	class CEPosition:
		line: int
		column: int
		if TYPE_CHECKING:
			def __iter__(self):
				yield self.line
				yield self.column
else:
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


@dataclass(kw_only=True)
class IndicatorStyle:
	style:           QSciIndicatorStyle
	hoverStyle:      QSciIndicatorStyle = None
	drawUnder:       bool
	foreground:      QColor
	hoverForeground: QColor = None
	outline:         Optional[QColor] = None

	def __post_init__(self):
		if self.hoverStyle is None:
			self.hoverStyle = self.style
		if self.hoverForeground is None:
			self.hoverForeground = self.foreground


class OriginalSciIndicatorRanges(enum.IntEnum):
	"""
	The Original Scintilla indicator ranges.
	CodeEditor divides the range differently. See enum CatIndicatorRanges.
	"""
	SCI_LEXER_MIN = 0
	SCI_LEXER_MAX = QsciScintilla.INDIC_CONTAINER - 1  # 7

	SCI_CONTAINER_MIN = QsciScintilla.INDIC_CONTAINER  # 8
	SCI_CONTAINER_MAX = QsciScintilla.INDIC_IME - 1  # 31

	SCI_IME_MIN = QsciScintilla.INDIC_IME  # 32
	SCI_IME_MAX = QsciScintilla.INDIC_IME_MAX  # 35

	SCI_HISTORY_MIN = QsciScintilla.INDIC_IME_MAX + 1  # 36
	SCI_HISTORY_MAX = QsciScintilla.INDIC_MAX  # 43

	SCI_MAX = QsciScintilla.INDIC_MAX  # 43


class CatIndicatorRanges(enum.IntEnum):
	"""
	Scintilla grants only 8 indicators (0..7) to lexers, but 24 indicators (8..31) to the container.
	CodeEditor divides up the ranges differently:
		- lexers:      0..15
		- containers: 16..31 (25..31) are already taken. See enum CatIndicatorIds.
		- IME:        32..35 (the same as Scintilla)
		- history:    36..43 (the same as Scintilla)
	"""
	CAT_LEXER_MIN = 0
	CAT_LEXER_MAX = 15

	CAT_CONTAINER_MIN = 16
	CAT_CONTAINER_MAX = OriginalSciIndicatorRanges.SCI_CONTAINER_MAX.value  # 31

	SCI_IME_MIN = QsciScintilla.INDIC_IME  # 32
	SCI_IME_MAX = QsciScintilla.INDIC_IME_MAX  # 35

	SCI_HISTORY_MIN = OriginalSciIndicatorRanges.SCI_HISTORY_MIN.value  # 36
	SCI_HISTORY_MAX = OriginalSciIndicatorRanges.SCI_HISTORY_MAX.value  # 43

	SCI_MAX = OriginalSciIndicatorRanges.SCI_MAX.value  # 43


class CatIndicatorIds(enum.IntEnum):
	CAT_ERROR =         CatIndicatorRanges.CAT_CONTAINER_MAX - 6  # 25
	CAT_WARNING =       CatIndicatorRanges.CAT_CONTAINER_MAX - 5  # 26
	CAT_INFO =          CatIndicatorRanges.CAT_CONTAINER_MAX - 4  # 27
	CAT_FALLBACK =      CatIndicatorRanges.CAT_CONTAINER_MAX - 3  # 28
	CAT_SEARCH_RESULT = CatIndicatorRanges.CAT_CONTAINER_MAX - 2  # 29
	CAT_MATCHED_BRACE = CatIndicatorRanges.CAT_CONTAINER_MAX - 1  # 30
	CAT_LINK =          CatIndicatorRanges.CAT_CONTAINER_MAX - 0  # 31

	SCI_HISTORY_REVERTED_TO_ORIGIN_INSERTION = 36
	"""
	Text was deleted and saved but then reverted to its original state. 
	This text has not been saved to disk.
	"""
	SCI_HISTORY_REVERTED_TO_ORIGIN_DELETION = 37
	"""
	Text was inserted and saved but then reverted to its original state. 
	There is text on disk that is missing.
	"""
	SCI_HISTORY_SAVED_INSERTION = 38
	"""
	Text was inserted and saved. 
	This text is the same as on disk.
	"""
	SCI_HISTORY_SAVED_DELETION = 39
	"""
	Text was deleted and saved. 
	This range is the same as on disk.
	"""
	SCI_HISTORY_MODIFIED_INSERTION = 40
	"""
	Text was inserted but not yet saved. 
	This text has not been saved to disk.
	"""
	SCI_HISTORY_MODIFIED_DELETION = 41
	"""
	Text was deleted but not yet saved. 
	There is text on disk that is missing.
	"""
	SCI_HISTORY_REVERTED_TO_MODIFIED_INSERTION = 42
	"""
	Text was deleted and saved but then reverted but not to its original state. 
	This text has not been saved to disk.
	"""
	SCI_HISTORY_REVERTED_TO_MODIFIED_DELETION = 43
	"""
	Text was inserted and saved but then reverted but not to its original state. 
	There is text on disk that is missing.
	"""


DEFAULT_INDICATOR_STYLES = {
	CatIndicatorIds.CAT_ERROR: IndicatorStyle(
		style=QSciIndicatorStyle.SquiggleIndicator,
		drawUnder=True,
		foreground=QColor(0xFF0000),
	),
	CatIndicatorIds.CAT_WARNING: IndicatorStyle(
		style=QSciIndicatorStyle.SquiggleIndicator,
		drawUnder=True,
		foreground=QColor(0x9F8800),
	),
	CatIndicatorIds.CAT_INFO: IndicatorStyle(
		style=QSciIndicatorStyle.SquiggleIndicator,
		drawUnder=True,
		foreground=QColor(0x0072FF),
	),
	CatIndicatorIds.CAT_FALLBACK: IndicatorStyle(
		style=QSciIndicatorStyle.SquiggleIndicator,
		drawUnder=True,
		foreground=QColor(0x3D8C52),
	),
	CatIndicatorIds.CAT_SEARCH_RESULT: IndicatorStyle(
		style=QSciIndicatorStyle.StraightBoxIndicator,
		drawUnder=True,
		foreground=QColor(0x2F, 0x8C, 0x48, 0x48),
		outline=   QColor(0x3D, 0x8C, 0x52, 0x79)
	),
	CatIndicatorIds.CAT_MATCHED_BRACE: IndicatorStyle(
		style=QSciIndicatorStyle.StraightBoxIndicator,
		drawUnder=True,
		foreground=QColor(0x00, 0x6F, 0xCC, 0x28),
		outline=   QColor(0x1D, 0x2D, 0x9C, 0x79)
	),
	CatIndicatorIds.CAT_LINK: IndicatorStyle(
		style=QSciIndicatorStyle.HiddenIndicator,
		hoverStyle=QSciIndicatorStyle.PlainIndicator,
		drawUnder=True,
		foreground=     QColor(0x0072FF),
		hoverForeground=QColor(0x0000FF),
	)
}


indicatorStyles: dict[int, IndicatorStyle] = copy.deepcopy(DEFAULT_INDICATOR_STYLES)


def setIndicatorStyles(newIndicatorStyles: dict[int, IndicatorStyle]) -> None:
	global indicatorStyles
	indicatorStyles = copy.copy(DEFAULT_INDICATOR_STYLES)
	if newIndicatorStyles is not None:
		for indicator, style in newIndicatorStyles.items():
			indicatorStyles[indicator] = style
	else:
		pass


errorIndicatorStyles: dict[str, CatIndicatorIds] = {
	'error': CatIndicatorIds.CAT_ERROR,
	'warning': CatIndicatorIds.CAT_WARNING,
	'info': CatIndicatorIds.CAT_INFO,
	'default': CatIndicatorIds.CAT_FALLBACK,
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

	def getClickableRanges(self) -> list[IndexSpan]:
		return []

	def indicatorClicked(self, position: CEPosition, state: Qt.KeyboardModifiers) -> None:
		pass

	def wordCharacters(self) -> str:
		return "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"

	def autoCompletionWordSeparators(self) -> list[str]:
		return []  # ':', '#', '.']


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
		self._searchResults: list[IndexSpan] = []

		brightness = 0xE0
		self.setCaretLineBackgroundColor(QColor(brightness, brightness, brightness))

		self.setMarginLineNumbers(1, True)
		connectSafe(self.linesChanged, self._onLinesChanged)
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
		self.setMatchedBraceIndicator(CatIndicatorIds.CAT_MATCHED_BRACE.value)

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

	def initIndicatorStyles(self, styles: dict[int, IndicatorStyle]):
		for indicator, style in styles.items():
			self.indicatorDefine(style.style, indicator)
			self.setIndicatorHoverStyle(style.hoverStyle, indicator)
			self.setIndicatorDrawUnder(style.drawUnder, indicator)
			self.setIndicatorForegroundColor(style.foreground, indicator)
			self.setIndicatorHoverForegroundColor(style.hoverForeground, indicator)
			if style.outline is not None:
				self.setIndicatorOutlineColor(style.outline, indicator)

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
			# TODO defer clickable ranges after parsing.
			clickableRanges = api.getClickableRanges()
			self.updateIndicatorRanges({CatIndicatorIds.CAT_LINK: clickableRanges})

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

	def updateIndicatorRanges(self, indicatorRanges: dict[int, list[IndexSpan]]) -> None:
		"""
		updates all ranges for the given indicators.
		"""
		length = self.length()

		for indicator, ranges in indicatorRanges.items():
			self.clearIndicatorRangeIndex(0, self.length(), indicator)

			for iRange in ranges:
				beginIdx = iRange.start
				endIdx = iRange.end

				if endIdx <= 0:
					endIdx = 1  # endIdx is not before the start of text
				elif beginIdx >= length:
					beginIdx = max(0, length - 1)  # beginIdx is not past the end of text
				elif beginIdx == endIdx:
					endIdx += 1  # no zero-width indicators

				self.fillIndicatorRangeIndex(beginIdx, endIdx, indicator)

	def clearIndicatorRangeIndex(self, begin: int, end: int, indicator: int) -> None:
		beginCEPos = self.cePositionFromIndex(begin)
		endCEPos = self.cePositionFromIndex(end)
		self.clearIndicatorRange(*beginCEPos, *endCEPos, indicator)

	def fillIndicatorRangeIndex(self, begin: int, end: int, indicator: int) -> None:
		beginCEPos = self.cePositionFromIndex(begin)
		endCEPos = self.cePositionFromIndex(end)
		self.fillIndicatorRange(*beginCEPos, *endCEPos, indicator)

	def highlightSearchResults(self, searchResults: list[IndexSpan]):
		searchResultsCapped = searchResults[:1000]
		self.updateIndicatorRanges({CatIndicatorIds.CAT_SEARCH_RESULT: searchResultsCapped})
		self._searchResults = searchResultsCapped

	def nextSearchResult(self) -> None:
		if not self._searchResults:
			return
		line, column = self.getCursorPosition()
		index = self.positionFromLineIndex(line, column)

		nextSr = next((sr for sr in self._searchResults if sr.start > index), self._searchResults[0])
		begin = self.cePositionFromIndex(nextSr.start)
		end = self.cePositionFromIndex(nextSr.end)
		self.setSelection(*begin, *end)

	def prevSearchResult(self) -> None:
		if not self._searchResults:
			return
		line, column = self.getCursorPosition()
		index = self.positionFromLineIndex(line, column)

		nextSr = next((sr for sr in reversed(self._searchResults) if sr.end < index), self._searchResults[-1])
		begin = self.cePositionFromIndex(nextSr.start)
		end = self.cePositionFromIndex(nextSr.end)
		self.setSelection(*begin, *end)

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
			if wordSeps is None:
				wordSeps = ()

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
		self.initIndicatorStyles(indicatorStyles)  # huh?
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

	def extraAscent(self) -> int:
		return self.SendScintilla(QsciScintilla.SCI_GETEXTRAASCENT)

	def extraDescent(self) -> int:
		return self.SendScintilla(QsciScintilla.SCI_GETEXTRADESCENT)

	def setExtraAscent(self, ascent: int) -> None:
		self.SendScintilla(QsciScintilla.SCI_SETEXTRAASCENT, ascent)

	def setExtraDescent(self, descent: int) -> None:
		self.SendScintilla(QsciScintilla.SCI_SETEXTRADESCENT, descent)

	if TYPE_CHECKING:
		def lexer(self) -> QsciLexer:
			return super(CodeEditor, self).lexer()


def _innerAdvancedCodeField(
		gui: 'PythonGUI',
		code: Optional[str],
		label=None,
		language: str = 'PlainText',
		focusEndOfText: bool = False,
		cursorPosition: tuple[int, int] = None,
		selectionTo: tuple[int, int] = None,
		searchResults: Optional[list[IndexSpan]] = None,
		prev: bool = False,
		next: bool = False,
		**kwargs
) -> CodeEditor:
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

	codeField.setExtraAscent(int(font.pointSizeF() * 0.1))
	codeField.setExtraDescent(int(font.pointSizeF() * 0.1))

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

	gui._connectOnInputModified(codeField, codeField.textChanged)
	return codeField


def advancedCodeField(
		gui: 'PythonGUI',
		code: Optional[str],
		label=None,
		language: str = 'PlainText',
		focusEndOfText: bool = False,
		cursorPosition: tuple[int, int] = None,
		selectionTo: tuple[int, int] = None,
		searchResults: Optional[list[IndexSpan]] = None,
		prev: bool = False,
		next: bool = False,
		returnCursorPos: bool = False,
		errors: list[Error] = None,
		**kwargs
) -> Union[str, tuple[str, tuple[int, int]]]:
	codeField: CodeEditor = _innerAdvancedCodeField(gui, code, label, language, focusEndOfText, cursorPosition, selectionTo, searchResults, prev, next, **kwargs)

	# handle possible custom errorRanges:
	indicatorRanges: dict[int, list[IndexSpan]] = {indicator: [] for indicator in errorIndicatorStyles.values()}
	for error in errors:
		indicator = errorIndicatorStyles.get(error.style, CatIndicatorIds.CAT_FALLBACK)
		indicatorRanges[indicator].append(IndexSpan(error.position.index, error.end.index))
	codeField.updateIndicatorRanges(indicatorRanges)

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
