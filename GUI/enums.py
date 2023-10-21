from enum import Enum
from typing import cast, Sequence, Union

from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCompleter, QHeaderView, QMessageBox, QSizePolicy, QTabWidget

from Cat.utils import DocEnum


class MessageBoxStyle(DocEnum):
	"""docstring for MessageBoxStyle"""
	Information = 1, "An information message box"
	Question    = 2, "An question message box"
	Warning     = 3, "An warning message box"
	Critical    = 4, "An critical (error) message box"
	Error       = Critical
	About       = 12, "a simple about box with title and text"
	AboutQt     = 13, "simple message box about Qt"


class MessageBoxButton(DocEnum):
	"""
	A mapping of QMessageBox::StandardButton.
	For further documentation see: https://doc.qt.io/qt-5/qmessagebox.html#StandardButton-enum
	"""
	Empty = cast(QMessageBox.StandardButton, int(QMessageBox.NoButton))
	Ok = cast(QMessageBox.StandardButton, int(QMessageBox.Ok)),                           "An \"OK\" button defined with the AcceptRole."
	Open = cast(QMessageBox.StandardButton, int(QMessageBox.Open)),                       "An \"Open\" button defined with the AcceptRole."
	Save = cast(QMessageBox.StandardButton, int(QMessageBox.Save)),                       "A \"Save\" button defined with the AcceptRole."
	Cancel = cast(QMessageBox.StandardButton, int(QMessageBox.Cancel)),                   "A \"Cancel\" button defined with the RejectRole."
	Close = cast(QMessageBox.StandardButton, int(QMessageBox.Close)),                     "A \"Close\" button defined with the RejectRole."
	Discard = cast(QMessageBox.StandardButton, int(QMessageBox.Discard)),                 "A \"Discard\" or \"Don't Save\" button, depending on the platform, defined with the DestructiveRole."
	Apply = cast(QMessageBox.StandardButton, int(QMessageBox.Apply)),                     "An \"Apply\" button defined with the ApplyRole."
	Reset = cast(QMessageBox.StandardButton, int(QMessageBox.Reset)),                     "A \"Reset\" button defined with the ResetRole."
	RestoreDefaults = cast(QMessageBox.StandardButton, QMessageBox.RestoreDefaults), "A \"Restore Defaults\" button defined with the ResetRole."
	Help = cast(QMessageBox.StandardButton, int(QMessageBox.Help)),                       "A \"Help\" button defined with the HelpRole."
	SaveAll = cast(QMessageBox.StandardButton, int(QMessageBox.SaveAll)),                 "A \"Save All\" button defined with the AcceptRole."
	Yes = cast(QMessageBox.StandardButton, int(QMessageBox.Yes)),                         "A \"Yes\" button defined with the YesRole."
	YesToAll = cast(QMessageBox.StandardButton, int(QMessageBox.YesToAll)),               "A \"Yes to All\" button defined with the YesRole."
	No = cast(QMessageBox.StandardButton, int(QMessageBox.No)),                           "A \"No\" button defined with the NoRole."
	NoToAll = cast(QMessageBox.StandardButton, int(QMessageBox.NoToAll)),                 "A \"No to All\" button defined with the NoRole."
	Abort = cast(QMessageBox.StandardButton, int(QMessageBox.Abort)),                     "An \"Abort\" button defined with the RejectRole."
	Retry = cast(QMessageBox.StandardButton, int(QMessageBox.Retry)),                     "A \"Retry\" button defined with the AcceptRole."
	Ignore = cast(QMessageBox.StandardButton, int(QMessageBox.Ignore)),                   "An \"Ignore\" button defined with the AcceptRole."
	NoButton = cast(QMessageBox.StandardButton, int(QMessageBox.NoButton)),               "An invalid button."


class MessageBoxButtonPreset(frozenset[MessageBoxButton], Enum):
	JustOK = frozenset({MessageBoxButton.Ok})
	YesNo = frozenset({MessageBoxButton.Yes, MessageBoxButton.No})
	OkCancel = frozenset({MessageBoxButton.Ok, MessageBoxButton.Cancel})
	IgnoreCancel = frozenset({MessageBoxButton.Ignore, MessageBoxButton.Cancel})


MessageBoxButtons = set[MessageBoxButton] | MessageBoxButtonPreset

class ToggleCheckState(DocEnum):
	"""docstring for ToggleCheckState"""
	Unchecked = cast(Qt.CheckState, Qt.Unchecked),               "The item is unchecked."
	PartiallyChecked = cast(Qt.CheckState, Qt.PartiallyChecked), "The item is partially checked. Items in hierarchical models may be partially checked if some, but not all, of their children are checked."
	Checked = cast(Qt.CheckState, Qt.Checked),                   "The item is checked."


class SizePolicy(DocEnum):
	# description is taken from: https://doc.qt.io/qt-5/qsizepolicy.html#Policy-enum
	#GrowFlag         = cast(QSizePolicy.PolicyFlag, QSizePolicy.GrowFlag)    # 1                                 # The widget can grow beyond its size hint if necessary.
	#ExpandFlag       = cast(QSizePolicy.PolicyFlag, QSizePolicy.ExpandFlag)  # 2                                 # The widget should get as much space as possible.
	#ShrinkFlag       = cast(QSizePolicy.PolicyFlag, QSizePolicy.ShrinkFlag)  # 4                                 # The widget can shrink below its size hint if necessary.
	#IgnoreFlag       = cast(QSizePolicy.PolicyFlag, QSizePolicy.IgnoreFlag)  # 8                                 # The widget's size hint is ignored. The widget will get as much space as possible.
	Fixed = cast(QSizePolicy.Policy, QSizePolicy.Fixed),                       " 0: 0:                                  The QWidget::sizeHint() is the only acceptable alternative, so the widget can never grow or shrink (e.g. the vertical direction of a push button)."
	Minimum = cast(QSizePolicy.Policy, QSizePolicy.Minimum),                   " 1: GrowFlag:                           The sizeHint() is minimal, and sufficient. The widget can be expanded, but there is no advantage to it being larger (e.g. the horizontal direction of a push button). It cannot be smaller than the size provided by sizeHint()."
	Maximum = cast(QSizePolicy.Policy, QSizePolicy.Maximum),                   " 4: ShrinkFlag:                         The sizeHint() is a maximum. The widget can be shrunk any amount without detriment if other widgets need the space (e.g. a separator line). It cannot be larger than the size provided by sizeHint()."
	Preferred = cast(QSizePolicy.Policy, QSizePolicy.Preferred),               " 5: GrowFlag | ShrinkFlag:              The sizeHint() is best, but the widget can be shrunk and still be useful. The widget can be expanded, but there is no advantage to it being larger than sizeHint() (the default QWidget policy)."
	Expanding = cast(QSizePolicy.Policy, QSizePolicy.Expanding),               " 7: GrowFlag | ShrinkFlag | ExpandFlag: The sizeHint() is a sensible size, but the widget can be shrunk and still be useful. The widget can make use of extra space, so it should get as much space as possible (e.g. the horizontal direction of a horizontal slider)."
	MinimumExpanding = cast(QSizePolicy.Policy, QSizePolicy.MinimumExpanding), " 3: GrowFlag | ExpandFlag:              The sizeHint() is minimal, and sufficient. The widget can make use of extra space, so it should get as much space as possible (e.g. the horizontal direction of a horizontal slider)."
	Ignored = cast(QSizePolicy.Policy, QSizePolicy.Ignored),                   "13: ShrinkFlag | GrowFlag | IgnoreFlag: The sizeHint() is ignored. The widget will get as much space as possible."
	_AllAtOnce = cast(QSizePolicy.Policy, QSizePolicy.Policy(15)),             "15: ShrinkFlag | ExpandFlag | GrowFlag | IgnoreFlag: ???."


class TextElideMode(DocEnum):
	ElideLeft = cast(Qt.TextElideMode, Qt.ElideLeft),     "The ellipsis should appear at the beginning of the text."
	ElideRight = cast(Qt.TextElideMode, Qt.ElideRight),   "The ellipsis should appear at the end of the text."
	ElideMiddle = cast(Qt.TextElideMode, Qt.ElideMiddle), "The ellipsis should appear in the middle of the text."
	ElideNone = cast(Qt.TextElideMode, Qt.ElideNone),     "Ellipsis should NOT appear in the text."


class TabPosition(DocEnum):
	North = cast(QTabWidget.TabPosition, QTabWidget.North), "The tabs are drawn above the pages."
	South = cast(QTabWidget.TabPosition, QTabWidget.South), "The tabs are drawn below the pages."
	West = cast(QTabWidget.TabPosition, QTabWidget.West),   "The tabs are drawn to the left of the pages."
	East = cast(QTabWidget.TabPosition, QTabWidget.East),   "The tabs are drawn to the right of the pages."


TAB_POSITION_EAST_WEST = {TabPosition.East, TabPosition.West}
TAB_POSITION_NORTH_SOUTH = {TabPosition.North, TabPosition.South}


class TabShape(DocEnum):
	Rounded = cast(QTabWidget.TabShape, QTabWidget.Rounded),       "The tabs are drawn with a rounded look. This is the default shape."
	Triangular = cast(QTabWidget.TabShape, QTabWidget.Triangular), "The tabs are drawn with a triangular look."


class CompletionMode(DocEnum):
	PopupCompletion = cast(QCompleter.CompletionMode, QCompleter.PopupCompletion),                     "Current completions are displayed in a popup window."
	UnfilteredPopupCompletion = cast(QCompleter.CompletionMode, QCompleter.UnfilteredPopupCompletion), "Completions appear inline (as selected text)."
	InlineCompletion = cast(QCompleter.CompletionMode, QCompleter.InlineCompletion),                   "All possible completions are displayed in a popup window with the most likely suggestion indicated as current."


class ResizeMode(Enum):
	Interactive      = cast(QHeaderView.ResizeMode, QHeaderView.Interactive)
	Fixed            = cast(QHeaderView.ResizeMode, QHeaderView.Fixed)
	Stretch          = cast(QHeaderView.ResizeMode, QHeaderView.Stretch)
	ResizeToContents = cast(QHeaderView.ResizeMode, QHeaderView.ResizeToContents)


# non-enum types:
LabelContent = Union[str, int, float, QtGui.QPixmap, QtGui.QPicture, QtGui.QIcon, QtGui.QMovie]
FileExtensionFilter = tuple[str, Union[str, Sequence[str]]]

__all__ = [
	'MessageBoxStyle',
	'MessageBoxButton',
	'MessageBoxButtonPreset',
	'MessageBoxButtons',
	'ToggleCheckState',
	'SizePolicy',
	'TabPosition',
	'TAB_POSITION_EAST_WEST',
	'TAB_POSITION_NORTH_SOUTH',
	'TabShape',
	'CompletionMode',
	'ResizeMode',
	# non-enum types:
	'LabelContent',
	'FileExtensionFilter',
]