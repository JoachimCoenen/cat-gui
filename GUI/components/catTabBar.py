from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import reduce
from typing import Callable, List, NewType, Optional

from PyQt5.QtCore import pyqtSignal, QEvent, QLine, QLineF, QPoint, QRect, QRectF, QSize, Qt
from PyQt5.QtGui import QBrush, QColor, QCursor, QFont, QHelpEvent, QIcon, QKeyEvent, QKeySequence, QMouseEvent, \
	QPainter, QPainterPath, QPaintEvent, QPen, QResizeEvent, QTransform, QWheelEvent
from PyQt5.QtWidgets import QApplication, QStyle, QToolTip, QWhatsThis, QWidget

from ...GUI.components.catWidgetMixins import CatFramedWidgetMixin, CatScalableWidgetMixin, CatSizePolicyMixin, \
	CatStyledWidgetMixin, Margins, maskCorners, PaintEventDebug, palettes, PreciseOverlap, RoundedCorners, \
	ShortcutMixin, CatFocusableMixin
from ...GUI.enums import SizePolicy, TabPosition, TAB_POSITION_EAST_WEST
from ...GUI.utilities import CrashReportWrapped
from ...utils import Deprecated

Fixed64 = NewType('Fixed64', int)


def toFixed(i: int) -> Fixed64:
	return Fixed64(i * 256)


def fRound(i: Fixed64) -> int:
	return i // 256 if (i % 256 < 128) else 1 + i // 256


INT_MAX = 2147483647
QLAYOUTSIZE_MAX: int = INT_MAX//256//16


@dataclass
class QLayoutStruct:
	# parameters
	stretch: int = 0
	sizeHint: int = 0
	minimumSize: int = 0
	maximumSize: int = QLAYOUTSIZE_MAX
	spacing: int = 0
	expansive: bool = False
	empty: bool = True

	# temporary storage
	done: bool = False

	# result
	pos: int = 0
	size: int = 0

	def __post_init__(self) -> None:
		self.minimumSize = self.sizeHint
		# self.maximumSize = QLAYOUTSIZE_MAX
		# self.expansive = False
		# self.empty = True
		# self.spacing = 0

	def smartSizeHint(self) -> int:
		return self.minimumSize if self.stretch > 0 else self.sizeHint

	def effectiveSpacer(self, uniformSpacer: int) -> int:
		assert (uniformSpacer >= 0 or self.spacing >= 0)
		return uniformSpacer if uniformSpacer >= 0 else self.spacing


def qGeomCalc(chainIO: list[QLayoutStruct], start: int, count: int, pos: int, space: int, spacer: int) -> None:
	"""
	This is the main workhorse of the QGridLayout. It portions out
	available space to the chain's children.

	The calculation is done in fixed point: "fixed" variables are
	scaled by a factor of 256.

	If the layout runs "backwards" (i.e. RightToLeft or Up) the layout
	is computed mirror-reversed, and it's the caller's responsibility
	do reverse the values before use.

	chain contains input and output parameters describing the geometry.
	count is the count of items in the chain; pos and space give the
	interval (relative to parentWidget topLeft).
	"""
	cHint: int = 0
	cMin: int = 0
	cMax: int = 0
	sumStretch: int = 0
	sumSpacing: int = 0
	expandingCount: int = 0

	allEmptyNonstretch: bool = True
	pendingSpacing: int = -1
	spacerCount: int = 0

	for data in chainIO:
		data.done = False
		cHint += data.smartSizeHint()
		cMin += data.minimumSize
		cMax += data.maximumSize
		sumStretch += data.stretch
		if not data.empty:
			# Using pendingSpacing, we ensure that the spacing for the last
			# (non-empty) item is ignored.
			if pendingSpacing >= 0:
				sumSpacing += pendingSpacing
				spacerCount += 1

			pendingSpacing = data.effectiveSpacer(spacer)

		if data.expansive:
			expandingCount += 1
		allEmptyNonstretch = allEmptyNonstretch and data.empty and not data.expansive and data.stretch <= 0

	extraSpace: int = 0

	if space < cMin + sumSpacing:
		# Less space than minimumSize; take from the biggest first

		minSize: int = cMin + sumSpacing

		# shrink the spacers proportionally
		if spacer >= 0:
			spacer = spacer * space // minSize if minSize > 0 else 0
			sumSpacing = spacer * spacerCount

		minimumSizes: list[int] = [c.minimumSize for c in chainIO]  # QVarLengthArray[int, 32]
		minimumSizes.sort()

		space_left: int = space - sumSpacing

		sum: int = 0
		idx: int = 0
		space_used: int = 0
		current: int = 0
		while idx < count and space_used < space_left:
			current = minimumSizes[idx]
			space_used = sum + current * (count - idx)
			sum += current
			idx += 1

		idx -= 1
		deficit: int = space_used - space_left

		items: int = count - idx
		# If we truncate all items to "current", we would get "deficit" too many pixels. Therefore, we have to remove
		# deficit/items from each item bigger than maxval. The actual value to remove is deficitPerItem + remainder/items
		# "rest" is the accumulated error from using integer arithmetic.
		deficitPerItem: int = deficit // items
		remainder: int = deficit % items
		maxval: int = current - deficitPerItem

		rest: int = 0
		for data in chainIO:
			maxv: int = maxval
			rest += remainder
			if rest >= items:
				maxv -= 1
				rest -= items

			data.size = min(data.minimumSize, maxv)
			data.done = True

	elif space < cHint + sumSpacing:
		# Less space than smartSizeHint(), but more than minimumSize.
		# Currently take space equally from each, as in Qt 2.x.
		# Commented-out lines will give more space to stretchier
		# items.
		n: int = count
		space_left: int = space - sumSpacing
		overdraft: int = cHint - space_left

		# first give to the fixed ones:
		for data in chainIO:
			if not data.done and data.minimumSize >= data.smartSizeHint():
				data.size = data.smartSizeHint()
				data.done = True
				space_left -= data.smartSizeHint()
				# sumStretch -= data.stretch
				n -= 1

		finished: bool = n == 0
		while not finished:
			finished = True
			fp_over: Fixed64 = toFixed(overdraft)
			fp_w: Fixed64 = Fixed64(0)

			for data in chainIO:
				if data.done:
					continue
				# if (sumStretch <= 0)
				fp_w += fp_over // n
				# else
				# 	fp_w += (fp_over * data.stretch) / sumStretch
				w: int = fRound(fp_w)
				data.size = data.smartSizeHint() - w
				fp_w -= toFixed(w)  # give the difference to the next
				if data.size < data.minimumSize:
					data.done = True
					data.size = data.minimumSize
					finished = False
					overdraft -= data.smartSizeHint() - data.minimumSize
					# sumStretch -= data.stretch
					n -= 1
					break

	else:  # extra space
		n: int = count
		space_left: int = space - sumSpacing
		# first give to the fixed ones, and handle non-expansiveness
		for data in chainIO:
			if not data.done and (data.maximumSize <= data.smartSizeHint() or (not allEmptyNonstretch and data.empty and not data.expansive and data.stretch == 0)):
				data.size = data.smartSizeHint()
				data.done = True
				space_left -= data.size
				sumStretch -= data.stretch
				if data.expansive:
					expandingCount -= 1
				n -= 1

		extraSpace = space_left

		# Do a trial distribution and calculate how much it is off.
		# If there are more deficit pixels than surplus pixels, give
		# the minimum size items what they need, and repeat.
		# Otherwise give to the maximum size items, and repeat.
		#
		# Paul Olav Tvete has a wonderful mathematical proof of the
		# correctness of this principle, but unfortunately this
		# comment is too small to contain it.
		while True:
			surplus = 0
			deficit = 0
			fp_space: Fixed64 = toFixed(space_left)
			fp_w: Fixed64 = Fixed64(0)
			for data in chainIO:
				if data.done:
					continue
				extraSpace = 0
				if sumStretch > 0:
					fp_w += (fp_space * data.stretch) // sumStretch
				elif expandingCount > 0:
					fp_w += (fp_space * int(data.expansive)) // expandingCount
				else:
					fp_w += fp_space * 1 // n

				w: int = fRound(fp_w)
				data.size = w
				fp_w -= toFixed(w)  # give the difference to the next
				if w < data.smartSizeHint():
					deficit += data.smartSizeHint() - w
				elif w > data.maximumSize:
					surplus += w - data.maximumSize

			if deficit > 0 and surplus <= deficit:
				# give to the ones that have too little
				for data in chainIO:
					if not data.done and data.size < data.smartSizeHint():
						data.size = data.smartSizeHint()
						data.done = True
						space_left -= data.smartSizeHint()
						sumStretch -= data.stretch
						if data.expansive:
							expandingCount -= 1
						n -= 1

			if surplus > 0 and surplus >= deficit:
				# take from the ones that have too much
				for data in chainIO:
					if not data.done and data.size > data.maximumSize:
						data.size = data.maximumSize
						data.done = True
						space_left -= data.maximumSize
						sumStretch -= data.stretch
						if data.expansive:
							expandingCount -= 1
						n -= 1

			if not (n > 0 and surplus != deficit):
				break

		if n == 0:
			extraSpace = space_left

	# As a last resort, we distribute the unwanted space equally
	# among the spacers (counting the start and end of the chain). We
	# could, but don't, attempt a sub-pixel allocation of the extra
	# space.
	extra: int = extraSpace // (spacerCount + 2)
	p: int = pos + extra
	for data in chainIO:
		data.pos = p
		p += data.size
		if not data.empty:
			p += data.effectiveSpacer(spacer) + extra


@dataclass
class CatTabLayout:
	minRect: QRect = field(default_factory=QRect)
	prefRect: QRect = field(default_factory=QRect)
	maxRect: QRect = field(default_factory=QRect)

	rect: QRect = field(default_factory=QRect)
	borderRect: QRect = field(default_factory=QRect)
	iconRect: QRect = field(default_factory=QRect)
	textRect: QRect = field(default_factory=QRect)
	closeRect: QRect = field(default_factory=QRect)
	indicatorLine: QLine = field(default_factory=QLine)
	clearLine: QLine = field(default_factory=QLine)


@dataclass(frozen=True)
class TabOptions:
	text: str
	icon: Optional[QIcon] = field(default=None, kw_only=True)
	tip: Optional[str] = field(default=None, kw_only=True)
	whatsThis: Optional[str] = field(default=None, kw_only=True)
	textColor: Optional[QColor] = field(default=None, kw_only=True)
	enabled: bool = field(default=True, kw_only=True)
	visible: bool = field(default=True, kw_only=True)

	@property
	def hasIcon(self) -> bool:
		return not (self.icon is None or self.icon.isNull())


@dataclass
class Tab:
	"""
		Tabs are managed by instance; they are not the same even
		if all properties are the same.
	"""
	# text: str
	# icon: QIcon = QIcon()
	# toolTip: Optional[str] = None
	# whatsThis: Optional[str] = None
	# textColor: Optional[QColor] = None
	# enabled: bool = True
	# visible: bool = True
	options: TabOptions
	layout: CatTabLayout = field(default_factory=CatTabLayout)
	dragOffset: QPoint = field(default_factory=QPoint)


@dataclass
class CatTabBarStyle:
	borderPen: QPen
	backgroundBrush: QBrush
	selectedBackgroundBrush: QBrush
	indicatorPen: QPen
	indicatorWidth: float
	textPen: QPen
	selectedTextPen: QPen
	font: QFont
	layoutBorderPen: QPen


@dataclass
class CatTabBarLayoutOptions:
	# scale: float  is already covered by CatScalableWidgetMixin
	# overlap: PreciseOverlap  is already covered by CatFramedWidgetMixin
	# availableSize: QSize  is already covered by CatFramedWidgetMixin
	position: TabPosition
	# fontMetrics: QFontMetrics  is already covered by CatScalableWidgetMixin (via font())
	tabsClosable: bool
	expanding: bool
	tabOverlap: int = 1
	# baseIconHeight: float = 17.  is already covered by CatScalableWidgetMixin
	elideMode: Qt.TextElideMode = Qt.ElideMiddle

	@property
	def isVertical(self) -> bool:
		return self.position in {TabPosition.East, TabPosition.West}


def transposeRect(r: QRect) -> QRect:
	# size = r.size().transposed()
	# r.setTopLeft(r.topLeft().transposed())
	# r.setSize(size)
	return QRect(r.topLeft().transposed(), r.size().transposed())


def transposeAndFlipYRect(r: QRect, outerR: QRect) -> None:
	size = r.size().transposed()
	tl = QPoint(outerR.right() + outerR.left() - r.right(), r.top())
	r.setTopLeft(tl.transposed())
	r.setSize(size)


def transposeAndFlipXRect(r: QRect, outerR: QRect) -> None:
	size = r.size().transposed()
	tl = QPoint(r.left(), outerR.bottom() + outerR.top() - r.bottom())
	r.setTopLeft(tl.transposed())
	r.setSize(size)


def _getLines(borderRect: QRect, position: TabPosition, overlap: PreciseOverlap) -> tuple[QLine, QLine]:
	# outer:
	o_t, o_l = borderRect.top(), borderRect.left()
	o_b, o_r = borderRect.bottom() + 1, borderRect.right() + 1
	# inner:
	i_t, i_l = o_t + 1, o_l + 1
	i_b, i_r = o_b - 1, o_r - 1

	if position == TabPosition.North:
		src = QPoint(i_l, overlap[1])
		dst = QPoint(i_r, overlap[1])
		ind = QPoint(0, o_t)
		clr = QPoint(0, i_b)
	elif position == TabPosition.South:
		src = QPoint(i_l, -overlap[3])
		dst = QPoint(i_r, -overlap[3])
		ind = QPoint(0, o_b)
		clr = QPoint(0, i_t)
	elif position == TabPosition.West:
		src = QPoint(overlap[0], i_t)
		dst = QPoint(overlap[0], i_b)
		ind = QPoint(o_l, 0)
		clr = QPoint(i_r, 0)
	else:  # if position == TabPosition.East:
		src = QPoint(-overlap[2], i_t)
		dst = QPoint(-overlap[2], i_b)
		ind = QPoint(o_r, 0)
		clr = QPoint(i_l, 0)

	indicatorLine = QLine(src + ind, dst + ind)
	clearLine = QLine(src + clr, dst + clr)
	return clearLine, indicatorLine


class TabLayouter(CatScalableWidgetMixin):  # , CatFramedWidgetMixin):
	def __init__(
			self,
			parent: QWidget,
			layoutOptions: CatTabBarLayoutOptions,
			size: QSize,
			scale: float,
			margins: Margins,
			cornerRadius: float,
			roundedCorners: RoundedCorners,
			overlap: PreciseOverlap
	):
		super(TabLayouter, self).__init__()
		self._parent: QWidget = parent
		self.lo: CatTabBarLayoutOptions = layoutOptions
		self.size: QSize = size
		self._scale = scale
		self._margins = margins
		self._cornerRadius = cornerRadius
		self._roundedCorners = roundedCorners
		self._overlap = overlap

		self._baseMargins: tuple[tuple[float, float], tuple[float, float]] \
			= self._baseMarginMakers[self.lo.position](self._margins, self._scale)

		self._maxTranslation: QPoint = QPoint()
		self._allTabsRect: QRect = QRect()

	def parentWidget(self) -> Optional[QWidget]:
		return self._parent

	@property
	def maxTranslation(self) -> QPoint:
		return self._maxTranslation

	@property
	def allTabsRect(self) -> QRect:
		return self._allTabsRect

	_baseMarginMakers = {
		TabPosition.North: lambda bm, s: ((bm[0] * s, bm[1] * s), (bm[2] * s, bm[3] * s)),
		TabPosition.South: lambda bm, s: ((bm[0] * s, bm[1] * s), (bm[2] * s, bm[3] * s)),
		TabPosition.East: lambda bm, s: ((bm[2] * s, bm[3] * s), (bm[0] * s, bm[1] * s)),
		TabPosition.West: lambda bm, s: ((bm[3] * s, bm[2] * s), (bm[1] * s, bm[0] * s)),
	}

	@property
	def _hMargins(self) -> tuple[float, float]:
		return self._baseMargins[0]

	@property
	def _vMargins(self) -> tuple[float, float]:
		return self._baseMargins[1]

	@property
	def _closeButtonScale(self) -> float:
		return 0.75

	@property
	def _closeButtonPadding(self) -> float:
		return self.getDefaultIconPadding() * 2

	def _tabSizeHint(self, tab: TabOptions) -> QSize:
		hasIcon = tab.hasIcon
		sizeHint = (self.getDefaultSize(tab.text, int(hasIcon), int(tab.text and hasIcon)))

		if self.lo.tabsClosable:
			sizeHint.setWidth(sizeHint.width() + self._closeButtonPadding + int(self._closeButtonScale * self.getDefaultIconSize().width()))

		if self.lo.isVertical:
			sizeHint.transpose()
		return sizeHint

	# Compute the most-elided possible text, for minimumSizeHint
	@staticmethod
	def _computeMostElidedText(mode: Qt.TextElideMode, text: str) -> str:
		if len(text) <= 3:
			return text

		ellipses = '...'
		elideFuncs = {
			Qt.ElideRight:
				lambda t: t[0:2] + ellipses,
			Qt.ElideMiddle:
				lambda t: t[0:1] + ellipses + t[-1],
			Qt.ElideLeft:
				lambda t: ellipses + t[-2:],
			Qt.ElideNone:
				lambda t: t,
		}
		ret = elideFuncs[mode](text)
		return ret

	def _minimumTabSizeHint(self, tab: TabOptions) -> QSize:
		elidedTab = replace(tab, text=self._computeMostElidedText(self.lo.elideMode, tab.text))
		size: QSize = self._tabSizeHint(elidedTab)
		return size

	def layoutTabsQ(self, tabs: List[Tab]) -> None:
		q = self  # : CatTabBar
		expanding = self.lo.expanding
		tabOverlap = self.lo.tabOverlap
		size: QSize = q.size
		vertTabs: bool = self.lo.isVertical
		tabChainIndex: int = 0
		hiddenTabs: int = 0

		tabAlignment: Qt.Alignment = Qt.AlignLeft  # cast(Qt.Alignment, q.style().styleHint(QStyle.SH_TabBar_Alignment, None, q))
		tabChain: List[QLayoutStruct] = []

		# We put an empty item at the front and back and set its expansive attribute
		# depending on tabAlignment and expanding.
		chainItem = QLayoutStruct()
		chainItem.expansive = (not expanding) and (tabAlignment != Qt.AlignLeft) and (tabAlignment != Qt.AlignJustify)
		chainItem.empty = True
		tabChain.append(chainItem)
		del chainItem
		tabChainIndex += 1

		# We now go through our list of tabs and set the minimum size and the size hint
		# This will allow us to elide text if necessary. Since we don't set
		# a maximum size, tabs will EXPAND to fill up the empty space.
		# Since tab widget is rather *ahem* strict about keeping the geometry of the
		# tab bar to its absolute minimum, self won't bleed through, but will show up
		# if you use tab bar on its own (a.k.a. not a bug, but a feature).
		# Update: if expanding is false, we DO set a maximum size to prevent the tabs
		# being wider than necessary.
		minx: int = 0
		miny: int = 0
		x: int = 0
		y: int = 0
		maxHeight: int = 0
		maxWidth: int = 0
		for tab in tabs:
			options = tab.options
			if not options.visible:
				hiddenTabs += 1
				continue
			sz: QSize = self._tabSizeHint(options)
			tab.layout.maxRect = QRect(x, y, sz.width(), sz.height())
			szMin = self._minimumTabSizeHint(options)
			tab.layout.minRect = QRect(minx, miny, szMin.width(), szMin.height())
			if vertTabs:
				y += sz.height() - tabOverlap
				miny += szMin.height() - tabOverlap
				maxWidth = max(maxWidth, sz.width())
			else:
				x += sz.width() - tabOverlap
				minx += szMin.width() - tabOverlap
				maxHeight = max(maxHeight, sz.height())

			chainItem = QLayoutStruct()
			chainItem.sizeHint = (sz.height() if vertTabs else sz.width()) - tabOverlap
			chainItem.minimumSize = (szMin.height() if vertTabs else szMin.width()) - tabOverlap
			chainItem.empty = False
			chainItem.expansive = True
			if not expanding:
				chainItem.maximumSize = chainItem.sizeHint
			tabChain.append(chainItem)
			del chainItem
			tabChainIndex += 1

		if vertTabs:
			last = miny
			available = size.height()
			maxExtent = maxWidth
		else:
			last = minx
			available = size.width()
			maxExtent = maxHeight

		# Mirror our front item.
		chainItem = QLayoutStruct()
		chainItem.expansive = (not expanding) and (tabAlignment != Qt.AlignRight) and (tabAlignment != Qt.AlignJustify)
		chainItem.empty = True
		tabChain.append(chainItem)
		del chainItem
		assert (tabChainIndex == len(tabChain) - 1 - hiddenTabs)  # add an assert just to make sure.

		# Do the calculation
		qGeomCalc(tabChain, 0, len(tabChain), 0, max(available, last), 0)

		# Use the results
		hiddenTabs = 0
		for i, tab in enumerate(tabs):
			if not tab.options.visible:
				tab.layout.rect = QRect()
				hiddenTabs += 1
				continue
			lstruct: QLayoutStruct = tabChain[i + 1 - hiddenTabs]
			if not vertTabs:
				tab.layout.rect.setRect(lstruct.pos - self._overlap[0], 0 - self._overlap[1], lstruct.size + tabOverlap, maxExtent)
			else:
				tab.layout.rect.setRect(0 - self._overlap[0], lstruct.pos - self._overlap[1], maxExtent, lstruct.size + tabOverlap)
			self._computeContentRects(tab)

		if self.lo.isVertical:
			available = self.size.height()
			maxExtent = y + tabOverlap
			maxTranslation = QPoint(0, max(maxExtent - available, 0))
		else:
			available = self.size.width()
			maxExtent = x + tabOverlap
			maxTranslation = QPoint(max(maxExtent - available, 0), 0)

		self._maxTranslation = maxTranslation
		self._allTabsRect = reduce(QRect.united, (tab.layout.rect for tab in tabs), QRect())

	def _computeContentRects(self, tab: Tab):
		rect = QRect(tab.layout.rect)

		hasIcon = tab.options.hasIcon
		iconSize = self.getDefaultIconSize()
		if not hasIcon:
			iconSize.setWidth(0)

		iconPadding = self.getDefaultIconPadding() if (hasIcon and tab.options.text) else 0
		textSize = self.getTextSize(tab.options.text)

		hasCloseIcon = self.lo.tabsClosable
		closeIconSize = self.getDefaultIconSize() * self._closeButtonScale if hasCloseIcon else QSize()
		closeIconPadding = self.getDefaultIconPadding()*2 if hasCloseIcon else 0

		borderRect = rect.adjusted(0, 0, 0, 0)

		if self.lo.position in TAB_POSITION_EAST_WEST:
			rect = transposeRect(rect)

		contentRect = rect.marginsRemoved(self.qMargins)

		iconRect = QRect(
			contentRect.left(),
			contentRect.top(),
			iconSize.width(),
			iconSize.height()
		)
		textTop = self.getTextTop(contentRect)
		closeRect = QRect(
			contentRect.right() + 1 - closeIconSize.width(),
			textTop + textSize.height() - closeIconSize.height() - 1,
			closeIconSize.width(),
			closeIconSize.height()
		)
		textLeft = iconRect.right() + 1 + iconPadding
		textRect = QRect(
			textLeft,
			textTop,
			closeRect.left() - closeIconPadding - textLeft,
			textSize.height()
		)

		if self.lo.position == TabPosition.East:
			transposeAndFlipXRect(iconRect, contentRect)
			transposeAndFlipXRect(textRect, contentRect)
			transposeAndFlipXRect(closeRect, contentRect)
		elif self.lo.position == TabPosition.West:
			transposeAndFlipYRect(iconRect, contentRect)
			transposeAndFlipYRect(textRect, contentRect)
			transposeAndFlipYRect(closeRect, contentRect)

		clearLine, indicatorLine = _getLines(borderRect, self.lo.position, self._overlap)
		# tab.layout.rect = rect
		tab.layout.borderRect = borderRect
		tab.layout.iconRect = iconRect
		tab.layout.textRect = textRect
		tab.layout.closeRect = closeRect
		tab.layout.indicatorLine = indicatorLine
		tab.layout.clearLine = clearLine


class CatTabBar(CatFocusableMixin, ShortcutMixin, QWidget, CatSizePolicyMixin, CatScalableWidgetMixin, CatFramedWidgetMixin, CatStyledWidgetMixin):
	def __init__(self, parent: QWidget = None):
		super().__init__(parent, Qt.WindowFlags())
		self.setFocusPolicy(Qt.ClickFocus)

		self._layoutDirty: bool = True
		self._tabs: List[Tab] = []
		self._currentIndex: int = -1

		self._draggedIndex: int = -1
		self._dragStartPosition = QPoint()
		self._dragDistance: QPoint = QPoint()
		self._toBeMovedTo: int = -1
		self._allTabsRect: QRect = QRect()

		self._tabShape: bool = False
		self._tabsMovable: bool = False
		self._tabsClosable: bool = False
		self._expanding: bool = False
		self._closeIcon: QIcon = QIcon()
		self._position: TabPosition = TabPosition.North
		self.updateSizePolicy()
		self._shouldDrawBase: bool = False
		self._windowPanel: bool = False

		self._translation: QPoint = QPoint()
		self._maxTranslation: QPoint = QPoint()
		self.setMouseTracking(True)

		self._updateColorPalette()

	def tabs(self) -> List[Tab]:
		return self._tabs

	def setTabs(self, tabs: List[Tab]):
		if self._tabs != tabs:
			self._tabs = tabs
			self._onTabsChanged(fireEvent=False)

	def count(self) -> int:
		return len(self._tabs)

	def _getTab(self, index: int) -> Optional[Tab]:
		if self.isValidIndex(index):
			return self._tabs[index]
		else:
			return None

	def getIndexAtPos(self, pos: QPoint) -> int:
		for i, tab in enumerate(self._tabs):
			if not tab.options.visible:
				continue
			if tab.layout.rect.contains(pos + self._translation):
				return i
		return -1

	def getTabAtPos(self, pos: QPoint) -> Optional[Tab]:
		return self._getTab(self.getIndexAtPos(pos))

	def addTab(self, options: TabOptions):
		self._tabs.append(Tab(options))
		self._onTabsChanged(fireEvent=False)  # TODO: INVESTIGATE: maybe fireEvent=True...

	def insertTab(self, index: int, options: TabOptions):
		self._tabs.insert(index, Tab(options))
		self._onTabsChanged(fireEvent=False)  # TODO: INVESTIGATE: maybe fireEvent=True...

	def moveTab(self, oldIndex: int, index: int):
		if self.isValidIndex(oldIndex):
			tab = self._tabs.pop(oldIndex)
			self._tabs.insert(index, tab)
			self._onTabsChanged(fireEvent=False)  # TODO: INVESTIGATE: maybe fireEvent=True...

	def removeTab(self, index: int):
		if self.isValidIndex(index):
			del self._tabs[index]
			self._onTabsChanged(fireEvent=False)

	def _onTabsChanged(self, *, fireEvent: bool) -> None:
		self._ensureValidIndex(fireEvent=fireEvent, callRefresh=False)
		self._layoutDirty = True
		self._refresh()  # self.update() ?

	def position(self) -> TabPosition:
		return self._position

	def setPosition(self, pos: TabPosition):
		if self._position != pos:
			self._position = pos
			self.updateSizePolicy()
			self._refresh()

	def isVertical(self) -> bool:
		return self._position in {TabPosition.East, TabPosition.West}

	def updateSizePolicy(self) -> None:
		if self.isVertical():
			self.setSizePolicy(SizePolicy.Fixed.value, SizePolicy.Preferred.value)
		else:
			self.setSizePolicy(SizePolicy.Preferred.value, SizePolicy.Fixed.value)

	def drawBase(self) -> bool:
		return self._shouldDrawBase

	def setDrawBase(self, shouldDrawBase: bool):
		if self._shouldDrawBase != shouldDrawBase:
			self._shouldDrawBase = shouldDrawBase
			self._refresh()

	def isWindowPanel(self) -> bool:
		return self._windowPanel

	def setWindowPanel(self, windowPanel: bool) -> None:
		if windowPanel != self._windowPanel:
			self._windowPanel = windowPanel
			self._updateColorPalette()

	@Deprecated
	def documentMode(self) -> bool:
		return self._windowPanel

	@Deprecated
	def setDocumentMode(self, documentMode: bool):
		if self._windowPanel != documentMode:
			self._windowPanel = documentMode
			self._updateColorPalette()
			self._refresh()

	def isMovable(self) -> bool:
		return self._tabsMovable

	def setMovable(self, movable: bool):
		self._tabsMovable = movable

	def tabsClosable(self) -> bool:
		return self._tabsClosable

	def setTabsClosable(self, closable: bool) -> None:
		if self._tabsClosable != closable:
			self._tabsClosable = closable
			self._refresh()

	def expanding(self) -> bool:
		return self._expanding

	def setExpanding(self, expanding: bool) -> None:
		if self._expanding != expanding:
			self._expanding = expanding
			self._refresh()

	def shape(self):
		return self._tabShape

	def setShape(self, shape):
		self._tabShape = shape

	def closeIcon(self) -> QIcon:
		return self._closeIcon

	def setCloseIcon(self, icon: QIcon):
		if self._closeIcon != icon:
			self._closeIcon = icon
			self._refresh()

	def getCloseIconOrDefault(self) -> QIcon:
		if self._closeIcon.isNull():
			closeIcn = self.style().standardIcon(QStyle.SP_DialogCloseButton)
		else:
			closeIcn = self._closeIcon
		return closeIcn

	tabMoved = pyqtSignal(int, int)
	tabCloseRequested = pyqtSignal(int)
	currentChanged = pyqtSignal(int)
	contextMenuRequested = pyqtSignal(int)

	def currentIndex(self) -> int:
		return self._currentIndex

	def setCurrentIndex(self, index: int, *, fireEvent: bool = False, callRefresh: bool = True) -> None:
		if self._currentIndex != index:
			if self.isValidIndex(index):
				self._currentIndex = index
				self.makeTabVisible(self._currentIndex)
				if fireEvent:
					self.currentChanged.emit(self._currentIndex)
				if callRefresh:
					self._refresh()

	def isValidIndex(self, index: int):
		return index in range(self.count())

	def _ensureValidIndex(self, *, fireEvent: bool, callRefresh: bool) -> None:
		tabsCount = self.count()
		if self._currentIndex >= tabsCount:
			self.setCurrentIndex(tabsCount - 1, fireEvent=fireEvent, callRefresh=callRefresh)
		if self._currentIndex < 0 < tabsCount:
			self.setCurrentIndex(0, fireEvent=fireEvent, callRefresh=callRefresh)

	# def tabText(self, index: int) -> str:
	# 	if (tab := self._getTab(index)) is not None:
	# 		return tab.text
	# 	return ''
	#
	# def setTabText(self, index: int, text: str) -> None:
	# 	if (tab := self._getTab(index)) is not None:
	# 		tab.text = text
	# 		self._refresh()
	#
	# def tabIcon(self, index: int) -> QIcon:
	# 	if (tab := self._getTab(index)) is not None:
	# 		return tab.icon
	# 	return QIcon()
	#
	# def setTabIcon(self, index: int, icon: QIcon) -> None:
	# 	if (tab := self._getTab(index)) is not None:
	# 		simpleIconChange: bool = (not icon.isNull() and not tab.icon.isNull())
	# 		tab.icon = icon
	# 		if simpleIconChange:
	# 			self.update(self._getTab(index).layout.rect)
	# 		else:
	# 			self._refresh()
	#
	# def tabToolTip(self, index: int) -> Optional[str]:
	# 	if (tab := self._getTab(index)) is not None:
	# 		return tab.toolTip
	# 	return None
	#
	# def setTabToolTip(self, index: int, tip: Optional[str]) -> None:
	# 	if (tab := self._getTab(index)) is not None:
	# 		tab.toolTip = tip
	#
	# def tabWhatsThis(self, index: int) -> Optional[str]:
	# 	if (tab := self._getTab(index)) is not None:
	# 		return tab.whatsThis
	# 	return None
	#
	# def setTabWhatsThis(self, index: int, whatsThis: Optional[str]) -> None:
	# 	if (tab := self._getTab(index)) is not None:
	# 		tab.whatsThis = whatsThis
	#
	# def tabTextColor(self, index: int) -> Optional[QColor]:
	# 	if (tab := self._getTab(index)) is not None:
	# 		return tab.textColor
	# 	return None
	#
	# def setTabTextColor(self, index: int, color: Optional[QColor]) -> None:
	# 	if (tab := self._getTab(index)) is not None:
	# 		tab.textColor = color

	def tabOptions(self, index: int) -> Optional[TabOptions]:
		if (tab := self._getTab(index)) is not None:
			return tab.options
		return None

	def setTabOptions(self, index: int, options: TabOptions) -> None:
		if (tab := self._getTab(index)) is not None:
			optionsChanged = options != tab.options
			tab.options = options
			if optionsChanged:
				self._refresh()

	def makeTabVisible(self, index: int):
		# make selecedTab visible:
		if (tab := self._getTab(index)) is not None:
			self._layoutTabsIfDirty()
			rect = tab.layout.rect
			if self.isVertical():
				translation = self._translation.y()
				bottomPos = rect.bottom() - translation
				if bottomPos > self.height():
					translation += bottomPos - self.height()
				topPos = rect.top() - translation
				if topPos < 0:
					translation += topPos
				self._translation.setY(translation)

			else:
				translation = self._translation.x()
				rightPos = rect.right() - translation
				if rightPos > self.width():
					translation += rightPos - self.width()
				leftPos = rect.left() - translation
				if leftPos < 0:
					translation += leftPos
				self._translation.setX(translation)

			self._ensureValidTranslation()

	def _updateColorPalette(self) -> None:
		if self.isWindowPanel():
			colorPalette = palettes.windowTabBarColorPalette
		else:
			colorPalette = palettes.tabBarColorPalette
		self.setColorPalette(colorPalette)

	def _ensureValidTranslation(self) -> None:
		self._translation = QPoint(
			max(0, min(self._translation.x(), self._maxTranslation.x())),
			max(0, min(self._translation.y(), self._maxTranslation.y()))
		)

	def _refresh(self) -> None:
		# be safe in case a subclass is also handling move with the tabs
		# if pressedIndex != -1 and movable and mouseButtons == Qt.NoButton:
		# 	self.moveTabFinished(pressedIndex)
		# 	if not self.validIndex(pressedIndex):
		# 		pressedIndex = -1

		if not self.isVisible():
			self._layoutDirty = True
		else:
			# self.makeVisible(currentIndex)
			self.update()
			self.updateGeometry()

	def _layoutTabsIfDirty(self) -> None:
		self.updateScaleFromFontMetrics()
		if not self._layoutDirty:
			return
		tl = TabLayouter(
			self,
			CatTabBarLayoutOptions(
				position=self._position,
				tabsClosable=self._tabsClosable,
				expanding=self._expanding,
				tabOverlap=1,
				elideMode=Qt.ElideNone
			),
			size=self.size(),
			scale=self._scale,
			margins=self.margins(),
			cornerRadius=self.cornerRadius(),
			roundedCorners=self.roundedCorners(),
			overlap=self.overlap()
		)
		tl.layoutTabsQ(self._tabs)
		self._maxTranslation = tl.maxTranslation
		self._allTabsRect = tl.allTabsRect
		self._ensureValidTranslation()
		self._layoutDirty = False

	def _getTabBarStyle(self, rect: QRect) -> CatTabBarStyle:

		bkgBrush = self.getBackgroundBrush(rect)
		bkgBrush2 = self.getBackgroundBrush(rect)

		borderColor = self.getBorderBrush()
		textColor = self.getTextBrush()
		selectedTextColor = self.getTextBrush()
		indicatorColor = self.getIndicatorBorderBrush()

		borderPen = QPen(borderColor, 1)
		borderPen.setJoinStyle(Qt.BevelJoin)
		indicatorPen = QPen(indicatorColor, 1)
		indicatorPen.setJoinStyle(Qt.MiterJoin)
		indicatorPen.setWidth(0)
		return CatTabBarStyle(
			borderPen=borderPen,
			backgroundBrush=bkgBrush,
			selectedBackgroundBrush=bkgBrush2,
			indicatorPen=indicatorPen,
			indicatorWidth=3 * self._scale,
			textPen=QPen(textColor, 1),
			selectedTextPen=QPen(selectedTextColor, 1),
			font=self.font(),
			layoutBorderPen=borderPen
		)

	def _getIndicatorPath(self, tab: Tab, style: CatTabBarStyle, allTabsBorderPathForIndicator: QPainterPath) -> QPainterPath:

		indicatorLine = tab.layout.indicatorLine.translated(tab.dragOffset)
		if self.position() == TabPosition.North:
			indicatorRect = QRectF(
				indicatorLine.x1(),
				indicatorLine.y1(),
				indicatorLine.x2() - indicatorLine.x1(),
				style.indicatorWidth,
			)
		elif self.position() == TabPosition.South:
			indicatorRect = QRectF(
				indicatorLine.x1(),
				indicatorLine.y1() - style.indicatorWidth,
				indicatorLine.x2() - indicatorLine.x1(),
				style.indicatorWidth,
			)
		elif self.position() == TabPosition.West:
			indicatorRect = QRectF(
				indicatorLine.x1(),
				indicatorLine.y1(),
				style.indicatorWidth,
				indicatorLine.y2() - indicatorLine.y1(),
			)
		else:  # self.position() == TabPosition.East:
			indicatorRect = QRectF(
				indicatorLine.x1() - style.indicatorWidth,
				indicatorLine.y1(),
				style.indicatorWidth,
				indicatorLine.y2() - indicatorLine.y1(),
			)

		adjust = style.indicatorPen.widthF() / 2
		adjustedIndicatorRect = indicatorRect.adjusted(adjust, adjust, -adjust, -adjust)
		indicatorPath = QPainterPath()
		indicatorPath.addRect(adjustedIndicatorRect)

		indicatorPath = allTabsBorderPathForIndicator.intersected(indicatorPath)
		indicatorPath.closeSubpath()
		return indicatorPath

	def _paintTab(self, p: QPainter, tab: Tab, style: CatTabBarStyle, selected: bool, allTabsBorderPath: QPainterPath, allTabsBorderPathForIndicator: QPainterPath) -> None:
		drawLayoutBorders = False

		p.setPen(style.borderPen)
		if selected:
			p.setBrush(style.selectedBackgroundBrush)
		else:
			p.setBrush(style.backgroundBrush)

		borderRect = tab.layout.borderRect.translated(tab.dragOffset)
		adjustedBorderRect = QRectF(borderRect).adjusted(0.5, 0.5, -0.5, -0.5)
		borderPath = QPainterPath()
		borderPath.addRect(adjustedBorderRect)

		borderPath = allTabsBorderPath.intersected(borderPath)
		borderPath.closeSubpath()
		p.drawPath(borderPath)

		if selected:
			indicatorPath = self._getIndicatorPath(tab, style, allTabsBorderPathForIndicator)
			p.setPen(Qt.NoPen)
			p.setBrush(style.indicatorPen.color())
			p.drawPath(indicatorPath)

		p.save()
		if not tab.dragOffset.isNull():
			p.translate(tab.dragOffset)

		if tab.options.hasIcon:
			mode = QIcon.Normal  # .Selected if selected else QIcon.Normal
			mode = mode if self.isEnabled() else QIcon.Disabled
			p.drawPixmap(tab.layout.iconRect, tab.options.icon.pixmap(
				tab.layout.iconRect.size(),
				mode=mode,
				state=QIcon.On if selected else QIcon.Off
			))
			if drawLayoutBorders:
				p.setPen(style.layoutBorderPen)
				p.setBrush(Qt.NoBrush)
				p.drawRect(QRectF(tab.layout.iconRect).adjusted(0.5, 0.5, -0.5, -0.5))

		textRect = tab.layout.textRect
		p.save()
		if self.isVertical():
			if self.position() == TabPosition.East:
				angle = 90.
			else:
				angle = -90.
			invTextTransform = QTransform()
			invTextTransform.rotate(-angle)
			textRect = invTextTransform.mapRect(textRect)
			p.rotate(angle)

		if drawLayoutBorders:
			p.setPen(style.layoutBorderPen)
			p.setBrush(Qt.NoBrush)
			p.drawRect(QRectF(textRect).adjusted(0.5, 0.5, -0.5, -0.5))

		if selected:
			textPen = style.selectedTextPen
		else:
			textPen = style.textPen

		if tab.options.textColor is not None:
			textPen = QPen(textPen)
			textPen.setColor(tab.options.textColor)
		p.setPen(textPen)
		p.setFont(style.font)
		p.drawText(textRect, Qt.AlignVCenter, tab.options.text)
		p.restore()

		if self._tabsClosable:
			cursorPos = self.mapFromGlobal(QCursor.pos())
			cursorInCloseRect = tab.layout.closeRect.contains(cursorPos + self._translation - tab.dragOffset, False)
			p.drawPixmap(tab.layout.closeRect, self.getCloseIconOrDefault().pixmap(
				tab.layout.closeRect.size(),
				mode=QIcon.Normal if self.isEnabled() else QIcon.Disabled,
				state=QIcon.On if cursorInCloseRect else QIcon.Off
			))

			if drawLayoutBorders:
				p.setPen(style.layoutBorderPen)
				p.setBrush(Qt.NoBrush)
				p.drawRect(QRectF(tab.layout.closeRect).adjusted(0.5, 0.5, -0.5, -0.5))

		p.restore()

	def _drawBase(self, p: QPainter, style: CatTabBarStyle, rect: QRect) -> None:
		p.setPen(style.borderPen)
		if self.position() == TabPosition.North:
			p.drawLine(QLineF(rect.left(), rect.bottom()+1 - 0.5, rect.right()+1, rect.bottom()+1 - 0.5))
		elif self.position() == TabPosition.South:
			p.drawLine(QLineF(rect.left(), rect.top() + 0.5,    rect.right()+1, rect.top() + 0.5))
		elif self.position() == TabPosition.East:
			p.drawLine(QLineF(rect.left() + 0.5, rect.top(),    rect.left() + 0.5, rect.bottom()+1))
		elif self.position() == TabPosition.West:
			p.drawLine(QLineF(rect.right()+1 - 0.5, rect.top(),   rect.right()+1 - 0.5, rect.bottom()+1))

	_roundedCornerFiltersForSelected: dict[TabPosition, RoundedCorners] = {
		TabPosition.North: (True, True, False, False,),
		TabPosition.South: (False, False, True, True,),
		TabPosition.West: (True, False, True, False,),
		TabPosition.East: (False, True, False, True,),
	}

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event: QPaintEvent) -> None:
		super(CatTabBar, self).paintEvent(event)
		self._layoutTabsIfDirty()

		rect = self.adjustRectByOverlap(self.rect())
		translatedRect = rect.translated(+self._translation)

		style = self._getTabBarStyle(rect)

		corners = self.roundedCorners()
		if self.drawBase():
			roundedCornerFilter = self._roundedCornerFiltersForSelected[self.position()]
			corners = maskCorners(corners, roundedCornerFilter)

		allTabsBorderPath = self.getBorderPath(translatedRect, corners=corners)

		if self.isVertical():
			translatedRectForIndicator = QRectF(translatedRect).adjusted(0, 0.5, 0, -0.5)
		else:
			translatedRectForIndicator = QRectF(translatedRect).adjusted(0.5, 0, -0.5, 0)
		allTabsBorderPathForIndicator = self.getBorderPath(
			translatedRectForIndicator,
			corners=corners,
			penWidth=style.indicatorPen.widthF()
		)

		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)

			p.save()
			p.translate(-self._translation)

			if self._shouldDrawBase:
				self._drawBase(p, style, rect)

			# paint all Tabs, except for the currently dragged tab:
			for i, tab in enumerate(self._tabs):
				if self._draggedIndex == i:
					continue
				selected = self._currentIndex == i
				self._paintTab(p, tab, style, selected, allTabsBorderPath, allTabsBorderPathForIndicator)

			# paint dragged tab last
			i = self._draggedIndex
			if i != -1:
				tab = self._getTab(i)
				selected = self._currentIndex == i
				self._paintTab(p, tab, style, selected, allTabsBorderPath, allTabsBorderPathForIndicator)

			p.restore()

	@CrashReportWrapped
	def sizeHint(self) -> QSize:
		self._layoutTabsIfDirty()
		r: QRect = QRect()
		for tab in self._tabs:
			if tab.options.visible:
				r = r.united(tab.layout.prefRect)
		return self.adjustSizeByOverlap(r.size())

	@CrashReportWrapped
	def minimumSizeHint(self) -> QSize:
		self._layoutTabsIfDirty()

		r: QRect = QRect()
		for tab in self._tabs:
			if tab.options.visible:
				r = r.united(tab.layout.minRect)
		sz = min(r.size().width(), r.size().height())
		default = self.getDefaultMinimumSize(self.font())
		if self.isVertical():
			default.transpose()
		minSize = QSize(
			max(sz, default.width()),
			max(sz, default.height())
		)
		return self.adjustSizeByOverlap(minSize)

	def _toolTipEvent(self, ev: QHelpEvent) -> bool:
		if (tab := self.getTabAtPos(ev.pos())) is not None and (tip := tab.options.tip) is not None:
			QToolTip.showText(ev.globalPos(), tip, self)
			return True
		return False

	def _queryWhatsThisEvent(self, ev: QEvent) -> bool:
		if (tab := self.getTabAtPos(ev.pos())) is not None and tab.options.whatsThis is not None:
			return True
		ev.ignore()
		return False

	def _whatsThisEvent(self, ev: QHelpEvent) -> bool:
		if (tab := self.getTabAtPos(ev.pos())) is not None and (whatsThis := tab.options.whatsThis) is not None:
			QWhatsThis.showText(ev.globalPos(), whatsThis, self)
			return True
		return False

	eventHandlers: dict[QEvent.Type, Callable[[CatTabBar, QEvent], bool]] = {
		QEvent.ToolTip:        _toolTipEvent,
		QEvent.QueryWhatsThis: _queryWhatsThisEvent,
		QEvent.WhatsThis:      _whatsThisEvent,
	}

	@CrashReportWrapped
	def event(self, event: QEvent) -> bool:
		handler = self.eventHandlers.get(event.type(), None)
		if handler is not None:
			result = handler(self, event)
			if result:
				return result
		return super(CatTabBar, self).event(event)

	@CrashReportWrapped
	def keyPressEvent(self, event: QKeyEvent) -> None:
		if self._draggedIndex != -1 and self.isMovable():
			if event.matches(QKeySequence.Cancel):
				self.moveTabFinished(self._draggedIndex)
				event.accept()

	def _updateDragPosition(self, mousePos: QPoint) -> None:
		if (draggedTab := self._getTab(self._draggedIndex)) is not None:
			dragVector = mousePos + self._translation - self._dragStartPosition
			if dragVector.manhattanLength() <= QApplication.startDragDistance():
				draggedTab.dragOffset = QPoint()
			else:
				if self.isVertical():
					dragVector.setX(0)
				else:
					dragVector.setY(0)

				if dragVector.x() + dragVector.y() > 0:
					direction = +1
					cornerPos = draggedTab.layout.rect.bottomRight() + dragVector
					toBeMoved = self.getIndexAtPos(cornerPos - self._translation)
					if toBeMoved > -1:
						toBeMovedCenter = self._getTab(toBeMoved).layout.rect.center()
						if toBeMovedCenter.x() > cornerPos.x() or toBeMovedCenter.y() > cornerPos.y():
							toBeMoved -= 1
				else:
					direction = -1
					cornerPos = draggedTab.layout.rect.topLeft() + dragVector
					toBeMoved = self.getIndexAtPos(cornerPos - self._translation)
					if toBeMoved > -1:
						toBeMovedCenter = self._getTab(toBeMoved).layout.rect.center()
						if toBeMovedCenter.x() < cornerPos.x() or toBeMovedCenter.y() < cornerPos.y():
							toBeMoved += 1
						if toBeMoved >= len(self._tabs):
							toBeMoved = -1
				self._toBeMovedTo = toBeMoved
				if toBeMoved != -1:
					for tab in self._tabs:
						tab.dragOffset = QPoint()

					for i in range(self._draggedIndex + direction, toBeMoved + direction, direction):
						if self.isVertical():
							self._getTab(i).dragOffset = QPoint(0, -draggedTab.layout.rect.size().height() * direction)
						else:
							self._getTab(i).dragOffset = QPoint(-draggedTab.layout.rect.size().width() * direction, 0)
				draggedTab.dragOffset = dragVector
		self.update()

	@CrashReportWrapped
	def mousePressEvent(self, event: QMouseEvent) -> None:
		# Be safe!
		if self._draggedIndex != -1 and self.isMovable():
			self.moveTabFinished(self._draggedIndex)

		index = self.getIndexAtPos(event.pos())
		if event.button() == Qt.LeftButton:
			if (tab := self._getTab(index)) is not None:
				if self._tabsClosable:
					if tab.layout.closeRect.contains(event.pos() + self._translation, True):
						self.tabCloseRequested.emit(index)
						event.accept()
						return

				self._draggedIndex = index
				if self.isMovable():
					self._dragStartPosition = event.pos() + self._translation
				event.accept()
			else:
				self._draggedIndex = -1
		elif event.button() == Qt.RightButton:
			self.contextMenuRequested.emit(index)

		self.update()

	@CrashReportWrapped
	def mouseMoveEvent(self, event: QMouseEvent) -> None:
		if not (event.buttons() & Qt.LeftButton):
			# Be safe!
			if self._draggedIndex != -1 and self.isMovable():
				self.moveTabFinished(self._draggedIndex)
				event.ignore()
			self.update()
			event.accept()
			return

		if self._draggedIndex != -1 and self.isMovable():
			self._updateDragPosition(event.pos())
			event.accept()

	@CrashReportWrapped
	def mouseReleaseEvent(self, event: QMouseEvent) -> None:
		if event.button() != Qt.LeftButton:
			event.ignore()
			return

		# mouse release event might happen outside the tab, so keep the pressed index
		oldPressedIndex: int = self._draggedIndex

		i: int = oldPressedIndex if self.getIndexAtPos(event.pos()) == oldPressedIndex else -1
		if self.isMovable() and self._dragStartPosition != event.pos() + self._translation:
			i = -1
		self._draggedIndex = -1
		if i != -1:
			self.setCurrentIndex(i, fireEvent=True)
		else:
			toBeMovedFrom = oldPressedIndex
			toBeMovedTo = self._toBeMovedTo
			if toBeMovedTo != -1 and toBeMovedFrom != -1 and toBeMovedTo != toBeMovedFrom:
				tab = self._tabs.pop(toBeMovedFrom)
				self._tabs.insert(toBeMovedTo, tab)
				if self._currentIndex == toBeMovedFrom:
					self._currentIndex = toBeMovedTo
				else:
					direction = +1 if toBeMovedFrom < toBeMovedTo else -1
					if self._currentIndex in range(toBeMovedFrom, toBeMovedTo + direction, direction):
						self._currentIndex -= direction
				self.tabMoved.emit(toBeMovedFrom, toBeMovedTo)
			self.moveTabFinished(self._draggedIndex)
		event.accept()
		pass

	@CrashReportWrapped
	def wheelEvent(self, event: QWheelEvent) -> None:
		if abs(event.angleDelta().y()) > abs(event.angleDelta().x()):
			angleDelta = event.angleDelta().y()
		else:
			angleDelta = event.angleDelta().x()

		if angleDelta == 0:
			event.ignore()
			return
		# accelerated scolling:
		pixelDelta = int(angleDelta / 120 * 30 * self._scale)
		if self.isVertical():
			self._translation -= QPoint(0, pixelDelta)
		else:
			self._translation -= QPoint(pixelDelta, 0)
		self._ensureValidTranslation()
		if self._draggedIndex != -1 and self.isMovable():
			self._updateDragPosition(event.pos())
			event.accept()
		self.update()

	def moveTabFinished(self, index: int):
		self._draggedIndex = -1
		self._toBeMovedTo = -1
		self._dragDistance = QPoint()
		self._dragStartPosition = QPoint()
		for tab in self._tabs:
			tab.dragOffset = QPoint()
		self._onTabsChanged(fireEvent=False)  # TODO: INVESTIGATE: maybe fireEvent=True...

	@CrashReportWrapped
	def resizeEvent(self, event: QResizeEvent) -> None:
		self._layoutDirty = True
		super(CatTabBar, self).resizeEvent(event)
