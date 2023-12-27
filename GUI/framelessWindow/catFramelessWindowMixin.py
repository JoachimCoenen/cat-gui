from __future__ import annotations

from abc import abstractmethod
from dataclasses import replace
from typing import Callable, Generic, Optional, TYPE_CHECKING, Type, TypeVar, Union

from PyQt5 import QtWidgets
from PyQt5.QtCore import QEvent, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QHideEvent, QIcon, QPaintEvent, QPainter, QPixmap, QShowEvent, QWindow, qGray
from PyQt5.QtWidgets import QLayout, QWidget, qApp

from . import framelessWindowsManager
from .utilities import getDefaultAppIcon
from ..utilities import connectSafe
from ...GUI.components.Widgets import CatButton, CatFramelessButton, CatWindowMixin
from ...GUI.components.catWidgetMixins import CLEAR_COLOR_COLOR_SET, CORNERS, ColorSet, DEFAULT_WINDOW_CORNER_RADIUS, INNER_CORNERS, InnerCorners, Margins, NO_MARGINS, Overlap, \
	RoundedCorners, adjustOverlap, joinCorners, joinInnerCorners, joinOverlap, maskCorners, palettes, selectInnerCorners
from ...GUI.enums import SizePolicy
from ...GUI.icons import icons
from ...utils.utils import CrashReportWrapped, runLaterSafe


# PythonGUIWidget:      onGUI, GuiCls, parent
# PythonGUIWindow:      parent, flags, GuiCls, *, x, y, ...
# PythonGUIMainWindow:  GuiCls, flags
# PythonGUIDialog:      parent, flags, GuiCls, *, x, y, ...
# PythonGUIPopupWindow: initVal, guiFunc, GUICls, parent, *, x, y, ...
#
# PythonGUIWidget:               onGUI, GUICls, parent, flags
# PythonGUIWindow:                      GUICls, parent, flags, *, x, y, ...
# PythonGUIMainWindow:                  GUICls, parent, flags, *, x, y, ...
# PythonGUIDialog:                      GUICls, parent, flags, *, x, y, ...
# PythonGUIPopupWindow: initVal, onGUI, GUICls, parent, flags, *, x, y, ...
#
# PythonGUIWindow:      onGUI, GuiCls, parent, flags, *, x, y, ...
# PythonGUIMainWindow:  onGUI, GuiCls, parent, flags

def changeHue(c1: QColor, hue: int) -> QColor:
	c2 = QColor.fromHsvF(hue / 360, c1.hsvSaturationF(), c1.valueF(), c1.alphaF())
	br1 = qGray(c1.rgb())
	br2 = qGray(c2.rgb())
	val3 = c1.valueF() * br1 / br2 if br2 != 0 else c1.valueF()
	val3 = min(1., val3)
	c3 = QColor.fromHsvF(hue / 360, c1.hsvSaturationF(), val3, c1.alphaF())

	return c3


def changeHue2(c1: ColorSet, hue: int) -> ColorSet:
	return ColorSet(
		getNormal=lambda: changeHue(c1.getNormal(), hue),
		getDisabled=lambda: changeHue(c1.getDisabled(), hue),
		getInactive=lambda: changeHue(c1.getInactive(), hue),
		getSelected=lambda: changeHue(c1.getSelected(), hue),
	)


CLEAR_COLOR = QColor(0, 0, 0, 0)


def setNewBorderHue(btn: CatButton, hue: int, useDefault: bool):

	btnDefColorPalette = replace(
		palettes.defaultButtonColorPalette,
		borderColor=changeHue2(palettes.defaultButtonColorPalette.borderColor, hue),
		borderColor2=changeHue2(palettes.defaultButtonColorPalette.borderColor2, hue),
		backgroundColor=changeHue2(palettes.defaultButtonColorPalette.backgroundColor, hue),
		backgroundColor2=changeHue2(palettes.defaultButtonColorPalette.backgroundColor2, hue)
	)

	btnColorPalette = replace(
		palettes.buttonColorPalette,
		borderColor=changeHue2(palettes.buttonColorPalette.borderColor, hue),
		borderColor2=replace(
			changeHue2(palettes.buttonColorPalette.borderColor2, hue),
			getSelected=btnDefColorPalette.borderColor2.getSelected
		),
		backgroundColor=replace(
			CLEAR_COLOR_COLOR_SET,
			getSelected=btnDefColorPalette.backgroundColor.getSelected
		),
		backgroundColor2=replace(
			CLEAR_COLOR_COLOR_SET,
			getSelected=btnDefColorPalette.backgroundColor2.getSelected
		),
	)

	btn._normalColorPalette = btnColorPalette
	btn._defaultColorPalette = btnDefColorPalette


if TYPE_CHECKING:
	from ...GUI import PythonGUI
	_TPythonGUI = TypeVar('_TPythonGUI', bound=PythonGUI)
else:
	_TPythonGUI = TypeVar('_TPythonGUI', bound='PythonGUI')


_SHADOW_DATA_2 = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00@\x00\x00\x00@\x08\x06\x00\x00\x00\xaaiq\xde\x00\x00\x00\x01sRGB\x00\xae\xce\x1c\xe9\x00\x00\x00\x04gAMA\x00\x00\xb1\x8f\x0b\xfca\x05\x00\x00'
b'\x00\tpHYs\x00\x00\x0e\xc3\x00\x00\x0e\xc3\x01\xc7o\xa8d\x00\x00\x00\x18tEXtSoftware\x00paint.net 4.1.6\xfdN\t\xe8\x00\x00\thIDATx'
b"^\xed\xdae\x93c\xc9\x11\x85\xe153333\xb3\xd7\xcc\xcc\xf4\xff\x7f\x87\xef\xe3\xd0\xeb\xc8\xa8(\xa9[=\xdd3\xb3kW\xc4\xf90\xbaU\x99yNB]\xa9\xe7\x99\xff\xaf\x87_/xD<'\xd7\x8e\xc8}"
b'\xe0\xa9^\xbb\x80wx\xe1\r\xd8\x9d\xd9\xe1\xa9Y\xbb\xe0`\x92z\xd1\x1d1m\xec|\xc0\x13[k \xe7\xc8\xbex\x83\x97\x9c\xc1n/L{\xe7\x04ylku\xbc\x12/\xe8H\xbd\xf4\x84\x97]\x81\xce\xc0*\xce'
b'\x13\x15b::G:\xb2/?\xe1\x15\x07^y\xc2\xab\x06^\xbd`>k\xbf\xb3\xc0N\xc2\x9c\x13c\xc6\xf6 k:\x88|\x81L\xd2\x11\x8e\xd8k\x0e\xbc\xf6\x84\xd7\x1dx\xfd\x05x\x0e\xedw6q\x12d\x8a1'
b'\x85xP\x11V\xe2\x91\x9f\xc4#\x1d\xd17\x9c\xf0\xa6\x13\xde|\xe0-\x07\xdez\x01\x9e\x83\xbd\x9d{\xe3\x81\xc4I\x10\xbe\x12\xa2\x8a(\xae)\xc4\xbd\xac\x8c\xc1J~%.P\x01#\x80\xd0\xdb\x0e\xbc\xfd\xc0;\x0e\xbc'
b'\xf3\x84w\xdd\x80\xf69\xe3,\x1b\x89\x92\x18|M!\xaa\x86{\x17!#\xb3\xe4)Ny\xe5\xa84#.[\x02\x15\xb0\xe0\x91y\xcf\x81\xf7\x1ex\xdf\x81\xf7\x9f\xf0\xc1\x0b\xf8\xc0\x81\xf69\xe3,\x1b\t\x93\x18|%'
b"\x84\x18\xc4\xb2VC\xb1\xdfY\x84i e'\xf9\xb2\xae\xcceGp\x82\x14p\x84\x91\xfa\xf0\x81\x8f\x1c\xf8\xe8\x81\x8f\x9d\xf0\xf13\xe8\xb9\xbd\xce8\xfb\xa1\x03\t\xc2vB\xf0\xc9w\xd50EX\xab\x00\xae^\x1d\x9c"
b'\xd9\x9f\xe4\xf5\xa4L(u\x19\x8fx\xa4#\xfa\xc9\x03\x9f:\xf0\xe9\x03\x9f9\xf0\xd9\x13>7\xd0g\x9e\x83\xbd\xce8\xfb\x89\x03\x04a\x93\xed\x84\xe0\x93o1\x88\xe5&\x11\xaeZ;\xf2\xfal%_\xd6\x95\xea$.'
b'p$\x90\xfa\xfc\x81/\x1c\xf8\xd2\t_>\xe1+\x1b\xf4\xcc>g\x9ce\x83-6\xd9N\x08>\xab\x86)\xc2:\x13\xee$B\x07&y\x86\xeb\xf9\xc8\xebM\x19Q\xa6\xb2$H\x19\x14\xf8\x17\x0f \xf3\xd5\x03_?'
b'\xf0\x8d\x13\xbey\xc2\xb7\x16\xf4y\xfb\x9cq\x96\r\xb6\xd8d\x9b\x0f\xbe\xf8\xe4[\x0c\x89\xd0L\x10\xeb\x9d\xe7A\x1b\xd7\xd27q\xeby\xa5G\xfd\xc8\xcb\x8c\x92U\xce\x82\x95M\x04\x10\xfa\xf6\x81\xef\x1c\xf8\xee\x81g\x0f'
b'|\xef\x84\xef/\xf0\x99\xe7`\xaf3\xce\xb2\xc1\x16\x9bl\xf3\xc1\x17\x9f\x89 \x161\xb9%\\\x95b\xbds+L\x01f\xf6\x95\x97\xc9k\xf8\xe8?%\x18y%*CJ\xf7k\x07\x04\x1di\xe4~p\xe0\x87\x07~'
b"t\xe0\xc7'\xfcdA\x9f\xdbc\xaf3\x89\xc2\x16\x9bl\xab\x08\xbe\xf8L\x04\xb1\x88\xc9\r!\xc6]+\xdcJ\x80I~\x97\xfdJ\xdf\x10\xd2\x87JQ6\x04$0\x99\x925\xc4\x11@\x06\xb9\x9f\x1e\xf8\xd9\x81\x9f\x1f"
b'\xf8\xc5\r\xb0\xc7^g\x12\x84-B\xb0\xcdG"\xf0-\x06\xb1\x88i\xb6BU\x90\x00\xb7\xaa\x82U\x00%4\xb3O\xe1J\xdf0\xd2\x8fJR\xe6#/P\x19\x8c8B\xbf<\xf0\xab\x13~s\x03\xda\xe7\x8c\xb3\t'
b'\xc1\xe6*\x02\xdfb\x10K\xad\xb0V\xc1Um\xd0\x86\xb2\xdf\xe4\xa7\xa8\xfe\x9a\xd9W~\x86\x92\xbeT\x9a\x91/\xeb\x11\xff\xf5\x81\xdf\x1e\xf8\xdd\t\xbf?\xe1\x0f\x1b\xf8\xbc}\xce8;\x85 \x82\xb6H\x04\xbe\xc5 \x96'
b"Y\x05s\x16\xdc\xba\rz8\x05\xa8\xfc]1\xf5\xfe\xcc\xbe24\x9c\xf4\xa7\xb2/\xf3\x02.\xdb\x91F\xf0\x8f'\xfc\xe9\x0cz>\xc5\xa8*\xd8d\x9b\x0f\xbe\xf8\xe4[\x0c\xb3\n\xc4(\xd6\xab\xdb\xa0\x07\xbb\xf2o\xf2"
b'\xbbr\xbc\x955\xf8d@&\x0c)}:\xc9\xcb \x12\x11\xfe\xf3\t\x7fY\xf0\xd7\xcdg\t\x92\x10lM\x11\x0cV>\xab\x82\x06\xa2Wi1\x8a\xf5\xea6\xb8I\x80Y\xfe\xde\xf0\xbc\xa0\xe8\xc3\xb2\xaf\xf4\x95\xa9\x92'
b'\x95\xb5\x95|d\xe1og\xd0\xf3)\x04\x1bU\x02\xdb\x06d\xf3\x80o1\x88ELn\x84\xda@\xcc\xda\x00\x07mpQ\x80>L\x80\xd9\xff\x8c\x98\xac\xbe\x99\xb9nf\xf9{Q\xd1\x8f2R\xf6\xf5\xad\x80#\x1f\xf1'
b'H\xfe\xfd\x06L1\x12A%\xb0\xc9\xb6\x9b\xc2P\xe4\x93o1\xcc6\xe8J4\x07\xb4\x01\x0e7\xce\x81)\x80M\t0\xaf\xbf\xfa\xdf\x97\x14\xd7\x8fW\xd5Y\xfee\xbf\xd2/\xf3\x91\x9f$\xffq\x06\xe7D &\x9b'
b'U\x01_|\xd6\x06b\x11\x93\xd8\x9a\x03\xf3:\xbc\x93\x00\xf3\xfe7T\\1\xfa\xdf\xbd\xab\xe7\\}^Y\x1b~JS\x9f\xca\x94\x8cU\xf6\x93|D\xffy\x06;!\x88P+4\x0bj\x03\xbe\xc5 \x161\x89M'
b"\x8cb\x15\xb3\xe1\xbd\x0e\xc2\xc9\xf5\xbfk~8\x05\xf0^\xcdH\xf7\x7f\x03\xd0\xd5\x93\x00]}\r\xbf\xca\x7f\xcd\xfeM\xe4'\x12!\x01\xd8j\x16h\x03\xbe\xb4\x01\xdf\t\xd0u(F\x83P\xccW\x0b\xd0\x00\x9c\x02\x98"
b'\xa6\xdd\x00\xdd\xffs\x00\xba\x97\x05\xa37\xe7\xf0\xab\xf7\xcb\xe6J\xfe_\x03\xf3sH,\xe7j\x03UP\x1bL\x01\xe6 \x9c7A/D8\x9c\x13\x00\xfe\xb3\xfa\xc7\xbc\x01\xce\t\xb0\xde\x00;\x01\x1a~3\xfb+\xc9'
b')\xc0N\x88Y\x05\xab\x00|\x19\xba|\xfb&9o\x021\xde\x9b\x00\xbd\x02\xaf\x02x\x05\xf5\x12\xc2y7@\x02\xe8\xffK\x02\xec\x88\x87\x9b\x04`\xdb\x1cX\x05\x10\x8b\x98\x12\xe0\xdd\x07z\x17 \x80\xab\xf0\x7fR\x00'
b"\xef\x02OL\x80u\x00>\xaf\x04\xd0ow\xad\x00\xd8\x91\x87\xb9g'\xc0\xb9\x19 \x96u\x06\x88\xb9\x16\xb8\xf3\x0cp\xf8\x92\x00\xbb!\xf8$\x04\xd8\r\xc1G\x12\xc0\xe6\x04\xe8=\x80QWL\xef\x01\xdd\x02\xae\xa2\xbb"
b'\\\x83\x970\xc9\xdf\xf6\x1a\xec=\xe0\x91\xaeA8\'\xc0\xfa"\xc4\xe9\xa5\x17\xa1\x048W\x05\x97\xb0\np\xe9E\x88\x00\xf7\xf6"\x04\t0\xbf\x0b\xdc\xe5Ux\xb6\xc1\x14\xe1\x92\x10=\xb7\x17f\xf6\x1b\x80\x8f\xedU'
b'\xf8>\xbe\x0c\xadU0E\xd8\xa1=P\xf6\xd9\x90}\x02(\xff\x07\xff2d\x0e$\xc0m\xbf\x0e7\x08\x95f_\x87g\x15$\xc2\x14b\x87\xf6\xd8\xbff\x9fM\xd9\xaf\xfc/}\x1d\x16\xebU_\x87\xadU\x007\x81'
b'\xc3\xae\xc2\xf9{\xa0\x1f\x1d\xfc\xb9\xca\xd4\x9d\x83\xf0\xd2\x0f"\x89\x10"\xbab\x12\x8f<\x1bl\xa9,\xb6\xcf\xfd "\xa6;\xff bM\x01l&\x80\xc3]\x85\xdd\x04s\x0e\xac?\x89U\x052%\xe0*!!\xfa'
b'\x8a|\t\xf6D\xdc\xd9\xc8\x97}\xd7\x9f\xecW\xfe\xfd$V\xff\xcf+P\xf2p\xc0\xe5\xd6\x02\x80\xcd\xaa\xc0\xf0\xd0C\x86I\x83P\x8f\xcd6\xe8}@FdF\x15$\x82J B\xd5\x90\x10\x97\x10\xf1\xca>\xf2\xdd'
b'\xfd\r?>\xf9\x9e\xe5_\xff7\x00\xd7+\xf0\xa2\x00\xd6*\xc0\x9c\x03\xb7\xfdY\\\x80\x02%\x82\x925\x13\x08QE\x10\x03"Y\x96C\xa4\x9dA\x9c\x8d2_\xe9\xf3\xc5\'\xdf]\x7fb\xaa\xfc\xfbY\xfc\xd6\xfd\xdf'
b'j\xc3\xda\x06\xbd\x12\xf7>0\xab\xc0;\xb8>T\x8e\r\xc4D\xd0\xaf2\x87\x042\x89\x91 \xa1\xcf\xc0\x9eI\x9c\x8d\x95<_|\xf2=\xb3/\xb6^\x80\xae*\xff\xd6*\xc0l\x83\xae\xc3Y\x05\xfa\xce\xf5\xa3\x0c\xa7'
b'\x08JT\x9f\n\xda\\\xd0\x16\x88 \x04D\xd9\xa1\xe7\xf6:\xe3,\x1bl\xb19\xc9\xf3\xc9\xb7\x18f\xf6\xe7\xf5wU\xf9\xb7\xa6\x08\xb5\xc1\xac\x02\xfd\xa5\xcf\\7\xeb\x1fG\x13A\x7f\x1aR2&x\x0321@F'
b'w\xe8\xb9\xbd\xce8\xcb\x06[l>\xf8\x1fG\xad)\xc0\xae\n\\/\xa6l\xad\x90\x08\xb2\xa1$\xf5\xa5\xe1\x94\x10\xb2\x86\x80\x0c"\x03\xdad\x87\x9e\xdb\xeb\x8c\xb3l\xb0\xc5&\xdb|\xf0\x15\xf9J_L\xf5~\xd9\xbf'
b"\xaa\xfc\xe7js\x02\xcc+q\xb6\x82+'\x11\x94\xa2~4\x94dH\xb0\xb2\xe5E\x05\x01\xaf\xac\x80\x90op;x\x06\xf69\xe3,\x1bl\xb1\xc96\x1f|E^\x0c\xb3\xf4\xc5X\xef_\x9d\xfdV\x07f\x15t#"
b'(/WL"P_\t\xeaC\xc3Hf\x04\xa9D\xbd\xa0\x08\xdc\xab\xaa\xf7u@\x08dt\xa2\xcf\xdb\xe7\x8c\xb3l\xb0\xc5&\xdb|\xf0\xc5\'\xdf\x91\x17\xd3\xae\xf4\xaf\xce~k\'\x82\xb2ZEPz\xfa\xcf\x10\x92'
b'\x91)\x84\xef\xe7\x02W\xb2H\xc8 B\xa0\x94C\x9fy\x0e\xf6:\xe3\xec\xb5\xffI\n\xf9;\x97\xfe\\\x1d\x04\xc6\x80\xe1)\x82\x92\xd3w\x86O\xd5\x90\x10\xbe\x97+S\x81\xfb\x92\x82\x04Q\x12f\x87\x9e\xdb\xeb\x8c\xb3'
b'lx\xc3\x8bxY\xe7\x93o1D~\xf6=L\x0ewZ\x1d\x9eU\x90\x08\xcd\x04C\xc7\xe4\x95\x89\x84\x90\x1d\xbd)`\xa5*x$\x8002\xb9\x83g\xeds\xc6Y6\xd8b3\xe2|\xf1\xc9w=?3\x7f/'
b'\xe4[\xab\x08\xc0\x11\x87\x1c\x9b\xb8U\x83\xa0d\xc5U\xa9<\x13\x03d\x0e\x91\xe0\x87\xcb0?\x07{\x9d\xe9\xbf\xca\xb2\xc5&\xdb|\x94u\xbew\xe4\x1f\xa9\xf4w+cS\x88\xb5\x1a\x12BV\x12\xc3\x95)h\x19C'
b'@\xf6\x02R+zf\xaf3\xce\xb2\xc1\x96>g{\x12\xaf\xe4\x1bx0c\xbd\xd75\r\xaf"\xc8\xc0\x14b\x15\x03\x10\x00d\x02r\x11\x0c\xed\xeb\\\xa4\x95\xba>\x8fxY\x8f\xfc\xcc:<\xc8\x9a\x0efK\x08b'
b'\'\x06\x08:Q\x00\x91K\x98{#\xbc#\x1d\xf1\xc7F\xbe5\x1d\xc1\x14b\'F@`"b\x91[1\xcf\xeeH\xc3J\x1c\x1e\xdbZ\x1d\x0bf\x15\x03\n\xfc\xaeX\xed\xe5g\xf5\xffD\xd6\x1aD(\xc8\x9d \xd7'
b'b\xda\xda\xf9zj\xd6.\xb8\x87\xc4S\xbdv\x01\xdf\x07\x9e\xd3kG\xe8\x12\x9e\xb7kGv\xe21\xaeg\x9e\xf97$\xb6\xbb\xfed\x99b\xbe\x00\x00\x00\x00IEND\xaeB`\x82')


class CatFramelessWindowMixin(CatWindowMixin, Generic[_TPythonGUI]):  # , QDialog):
	def __init__(
			self,
			GUICls: Type[_TPythonGUI] = ...,
			parent: Optional[QWidget] = None,
			flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowFlags(),
			*,
			x: Optional[int] = None,
			y: Optional[int] = None,
			width: Optional[int] = None,
			height: Optional[int] = None
	):
		if GUICls is ...:
			from ...GUI import PythonGUI
			GUICls = PythonGUI
		super(CatFramelessWindowMixin, self).__init__(parent, flags | Qt.FramelessWindowHint, x=x, y=y, width=width, height=height)
		self._initGeometry = (x, y, width, height)
		self.setAttribute(Qt.WA_TranslucentBackground)
		self._isInited: bool = False
		self._isTitlebarVisible: bool = True
		self._isToolbarInTitleBar: bool = False
		self._drawTitleToolbarBorder: bool = True
		self._drawStatusbarBorder: bool = True
		self._statusbarIsWindowPanel: bool = False
		self._disableContentMargins: bool = False
		self._disableSidebarMargins: bool = False
		self._disableBottombarMargins: bool = False
		self._disableStatusbarMargins: bool = False
		self.roundedCorners: RoundedCorners = CORNERS.ALL

		self._shadowData = QPixmap()
		self._shadowData.loadFromData(_SHADOW_DATA_2, 'PNG')

		self._minimizeBtn: CatButton = CatFramelessButton()
		self._maximizeBtn: CatButton = CatFramelessButton()
		self._closeBtn: CatButton = CatFramelessButton()
		self._ignoredTitleBarObjects: list[QWidget] = [
			self._minimizeBtn,
			self._maximizeBtn,
			self._closeBtn,
		]

		# setNewBorderHue(self._minimizeBtn, 48, True)
		# setNewBorderHue(self._maximizeBtn, 93, True)
		setNewBorderHue(self._closeBtn, 3, True)

		self._minimizeBtn._neverInactive = True
		self._maximizeBtn._neverInactive = True
		self._closeBtn._neverInactive = True

		self._minimizeBtn.setCheckable(False)
		self._maximizeBtn.setCheckable(False)
		self._closeBtn.setCheckable(False)
		self._titleBar: Optional[QWidget] = None
		self._toolbarInTitleBar: Optional[QWidget] = None
		self._ignoredToolbarObjects: list[QWidget] = []
		connectSafe(self._minimizeBtn.clicked, lambda _, s=self: s.showMinimized())
		connectSafe(self._maximizeBtn.clicked, lambda _, s=self: s.showNormal() if s.isMaximized() or s.isFullScreen() else s.showMaximized())
		connectSafe(self._closeBtn.clicked, lambda _, s=self: s.close())

		self.borderSize = (9, 9, 9, 9)
		self._shadowMargins = (13, 13, 13, 13)
		self.borderMargin = (
			self._shadowMargins[0] - self.borderSize[0] + 2,
			self._shadowMargins[1] - self.borderSize[1] + 2,
			self._shadowMargins[2] - self.borderSize[2] + 2,
			self._shadowMargins[3] - self.borderSize[3] + 2,
		)

		if hasattr(self, 'setCentralWidget'):
			centerWidget = QWidget()
			self.setCentralWidget(centerWidget)
		else:
			centerWidget = QWidget()
			if self.layout() is None:
				self.setLayout(QtWidgets.QVBoxLayout())
			self.layout().addWidget(centerWidget)

		self._centralWidget: QWidget = centerWidget
		self._gui: _TPythonGUI = GUICls(centerWidget, self._windowGUI)

		# centerWidget.setContentsMargins(*self._shadowMargins)
		self.setContentsMargins(*self._shadowMargins)


		self.layout().setContentsMargins(*NO_MARGINS)

		# runLaterSafe(5, self.redraw)

		connectSafe(self.windowIconChanged, lambda x, s=self: s.redrawLater('windowIconChanged'))
		connectSafe(self.windowTitleChanged, lambda x, s=self: s.redrawLater('windowTitleChanged'))
		connectSafe(self.windowStateChanged, self.onWindowStateChanged )
		# connect(self.titleBarWidget.iconButton, &QPushButton.clicked, self, &MainWindow.displaySystemMenu)

	if TYPE_CHECKING:
		windowIconChanged: pyqtSignal
		windowTitleChanged: pyqtSignal
		windowIconTextChanged: pyqtSignal

		def setAttribute(self, attribute: Qt.WidgetAttribute, on: bool = True) -> None: ...  # raise NotImplementedError()
		def centralWidget(self) -> QWidget: ...  # raise NotImplementedError()
		def layout(self) -> QLayout: ...  # raise NotImplementedError()
		def windowIcon(self) -> QIcon: ...  # raise NotImplementedError()
		def windowTitle(self) -> str: ...  # raise NotImplementedError()
		def isFullScreen(self) -> bool: ...  # raise NotImplementedError()
		def isMaximized(self) -> bool: ...  # raise NotImplementedError()
		def isMinimized(self) -> bool: ...  # raise NotImplementedError()
		def close(self) -> bool: ...  # raise NotImplementedError()
		def showMinimized(self) -> None: ...  # raise NotImplementedError()
		def windowHandle(self) -> QWindow: ...  # raise NotImplementedError()
		def update(self) -> None: ...  # raise NotImplementedError()

	# def showEvent(self, event: QShowEvent) -> None:
	# 		raise NotImplementedError()
	#
	# def changeEvent(self, event: QEvent) -> None:
	# 		raise NotImplementedError()
	#
	# def hideEvent(self, event: QHideEvent) -> None:
	# 		raise NotImplementedError()
	#


	# Q_SIGNALS:
	windowStateChanged = pyqtSignal()

	# def showNormal(self) -> None:
	# 	win: QWindow = self.windowHandle()
	# 	win.showNormal()
	#
	# def showMaximized(self) -> None:
	# 	win: QWindow = self.windowHandle()
	# 	win.hide() # is needed on windows 10. possibly a bug?
	# 	win.showMaximized()

	@abstractmethod
	def OnToolbarGUI(self, gui: _TPythonGUI):
		pass

	@abstractmethod
	def OnSidebarGUI(self, gui: _TPythonGUI):
		pass

	@abstractmethod
	def OnBottombarGUI(self, gui: _TPythonGUI):
		pass

	@abstractmethod
	def OnStatusbarGUI(self, gui: _TPythonGUI):
		pass

	@abstractmethod
	def OnGUI(self, gui: _TPythonGUI):
		pass

	OnToolbarGUI: Optional[Callable[[CatFramelessWindowMixin, _TPythonGUI], None]] = None
	OnSidebarGUI: Optional[Callable[[CatFramelessWindowMixin, _TPythonGUI], None]] = None
	OnBottombarGUI: Optional[Callable[[CatFramelessWindowMixin, _TPythonGUI], None]] = None
	OnStatusbarGUI: Optional[Callable[[CatFramelessWindowMixin, _TPythonGUI], None]] = None

	@property
	def disableContentMargins(self) -> bool:
		return self._disableContentMargins

	@disableContentMargins.setter
	def disableContentMargins(self, value: bool) -> None:
		self._disableContentMargins = value

	@property
	def disableSidebarMargins(self) -> bool:
		return self._disableSidebarMargins

	@disableSidebarMargins.setter
	def disableSidebarMargins(self, value: bool) -> None:
		self._disableSidebarMargins = value

	@property
	def disableBottombarMargins(self) -> bool:
		return self._disableBottombarMargins

	@disableBottombarMargins.setter
	def disableBottombarMargins(self, value: bool) -> None:
		self._disableBottombarMargins = value

	@property
	def disableStatusbarMargins(self) -> bool:
		return self._disableStatusbarMargins

	@disableStatusbarMargins.setter
	def disableStatusbarMargins(self, value: bool) -> None:
		self._disableStatusbarMargins = value

	@property
	def isToolbarInTitleBar(self) -> bool:
		return self._isToolbarInTitleBar

	@isToolbarInTitleBar.setter
	def isToolbarInTitleBar(self, value: bool):
		self._isToolbarInTitleBar = value

	@property
	def drawTitleToolbarBorder(self) -> bool:
		return self._drawTitleToolbarBorder

	@drawTitleToolbarBorder.setter
	def drawTitleToolbarBorder(self, value: bool):
		self._drawTitleToolbarBorder = value

	@property
	def isTitlebarVisible(self) -> bool:
		return self._isTitlebarVisible

	@isTitlebarVisible.setter
	def isTitlebarVisible(self, value: bool):
		self._isTitlebarVisible = value

	@property
	def isToolbarVisible(self) -> bool:
		return self.OnToolbarGUI is not None

	@property
	def isSidebarVisible(self) -> bool:
		return self.OnSidebarGUI is not None

	@property
	def isBottombarVisible(self) -> bool:
		return self.OnBottombarGUI is not None

	@property
	def drawStatusbarBorder(self) -> bool:
		return self._drawStatusbarBorder

	@drawStatusbarBorder.setter
	def drawStatusbarBorder(self, value: bool):
		self._drawStatusbarBorder = value

	@property
	def statusbarIsWindowPanel(self) -> bool:
		return self._statusbarIsWindowPanel

	@statusbarIsWindowPanel.setter
	def statusbarIsWindowPanel(self, value: bool):
		self._statusbarIsWindowPanel = value

	@property
	def isStatusbarVisible(self) -> bool:
		return self.OnStatusbarGUI is not None

	def setIgnoredToolbarObjects(self, ignoredToolbarObjects: list[QWidget]):
		if ignoredToolbarObjects != self._ignoredToolbarObjects:
			self._ignoredToolbarObjects = ignoredToolbarObjects
			if self._isInited:
				win = self.windowHandle()
				if win:
					ignoredObjects = self._ignoredTitleBarObjects + self._ignoredToolbarObjects
					framelessWindowsManager.updateIgnoredObjects(win, ignoredObjects)

	@property
	def windowSpacing(self) -> int:
		return self._gui.spacing

	@property
	def _sidebarMargins(self) -> Margins:
		if self.disableSidebarMargins:
			return NO_MARGINS
		else:
			margin = self._gui.margin
			return margin, 0, 0, margin

	@property
	def _bottombarMargins(self) -> Margins:
		if self.disableBottombarMargins:
			return NO_MARGINS
		else:
			margin = self._gui.margin
			return margin, margin, margin, margin

	@property
	def _statusbarMargins(self) -> Margins:
		if self.disableStatusbarMargins:
			return NO_MARGINS
		else:
			margin = self._gui.margin
			return margin, margin, margin, margin

	@property
	def _contentMargins(self) -> Margins:
		if self.disableContentMargins:
			return NO_MARGINS
		else:
			margin = self._gui.margin
			return margin, margin, margin, margin

	@property
	def windowRoundedCorners(self) -> RoundedCorners:
		return self.roundedCorners
		if self.isMaximized() or self.isFullScreen():
			return CORNERS.NONE
		else:
			return self.roundedCorners

	@property
	def windowCornerRadius(self) -> float:
		return DEFAULT_WINDOW_CORNER_RADIUS

	def _windowGUI(self, gui: _TPythonGUI):
		gui.currentLayout._qLayout.setContentsMargins(*NO_MARGINS)
		gui.currentLayout._qLayout.setVerticalSpacing(0)
		leftOverCorners = self.windowRoundedCorners

		with gui.vPanel(roundedCorners=leftOverCorners, cornerRadius=self.windowCornerRadius, verticalSpacing=0, windowPanel=False, contentsMargins=NO_MARGINS):

			hasSeparateToolbar = self.isToolbarVisible and not self.isToolbarInTitleBar
			isTitleOrToolbarVisible = self.isTitlebarVisible or hasSeparateToolbar

			if self.isTitlebarVisible:
				titleBarCorners = maskCorners(leftOverCorners, CORNERS.TOP)
				leftOverCorners = maskCorners(leftOverCorners, CORNERS.BOTTOM)
				titleBarOverlap = (0, 0, 0, 1)  # if hasSeparateToolbar else (0, 0, 0, 0 if self.drawTitleToolbarBorder else 1)
				with gui.hPanel(
						overlap=titleBarOverlap,
						roundedCorners=titleBarCorners,
						cornerRadius=self.windowCornerRadius,
						windowPanel=False,
						contentsMargins=NO_MARGINS,
						sizePolicy=(SizePolicy.Expanding.value, SizePolicy.Fixed.value)
				):
					self._titleBar = gui.lastWidget
					self._titleBarGUI(gui, roundedCorners=titleBarCorners, cornerRadius=self.windowCornerRadius, overlap=titleBarOverlap)
				del titleBarOverlap
				del titleBarCorners
			else:
				self._titleBar = None
				self._toolbarInTitleBar = None
				self.setIgnoredToolbarObjects([])

			if hasSeparateToolbar:
				toolbarCorners = maskCorners(leftOverCorners, CORNERS.TOP)
				leftOverCorners = maskCorners(leftOverCorners, CORNERS.BOTTOM)
				toolbarOverlap = (0, 1, 0, 1)  # (0, 1, 0, 0 if self.drawTitleToolbarBorder else 1)
				mg = gui.panelMargins
				smg = gui.smallSpacing
				toolBarMargins = (mg, mg if not self.isTitlebarVisible else smg, mg, smg)
				with gui.hPanel(
						overlap=toolbarOverlap,
						roundedCorners=toolbarCorners,
						cornerRadius=self.windowCornerRadius,
						windowPanel=False,
						contentsMargins=toolBarMargins,
						sizePolicy=(SizePolicy.Expanding.value, SizePolicy.Fixed.value)
				):
					self.OnToolbarGUI(gui)
				del toolbarOverlap
				del toolbarCorners

			if self.isStatusbarVisible:
				statusbarCorners = maskCorners(leftOverCorners, CORNERS.BOTTOM)
				leftOverCorners = maskCorners(leftOverCorners, CORNERS.TOP)
			else:
				statusbarCorners = CORNERS.NONE

			innerCorners = InnerCorners(
				False,
				isTitleOrToolbarVisible and self.drawTitleToolbarBorder,
				False,
				self.isStatusbarVisible and self.drawStatusbarBorder
			)
			topOverlap = 1 if isTitleOrToolbarVisible and not self.drawTitleToolbarBorder else 0  # find better name
			bottomOverlap = 1 if self.isStatusbarVisible and not self.drawStatusbarBorder else 0  # find better name
			if self.isSidebarVisible:
				# innerCorners = joinCorners(
				# 	CORNERS.TOP if isTitleOrToolbarVisible and not self.drawTitleToolbarBorder else CORNERS.NONE,
				# 	CORNERS.BOTTOM if self.isStatusbarVisible else CORNERS.NONE
				# )
				with gui.hSplitter(handleWidth=self.windowSpacing, childrenCollapsible=True) as splitter:
					with splitter.addArea(id_='&!sidebar', stretchFactor=0, contentsMargins=NO_MARGINS):
						sidebarCorners = joinCorners(
							maskCorners(leftOverCorners, CORNERS.LEFT),
							selectInnerCorners(innerCorners, INNER_CORNERS.RIGHT)
						)
						sidebarOverlap = (0, topOverlap, 0, bottomOverlap)
						sidebarMargins = self._sidebarMargins
						with gui.vPanel(overlap=sidebarOverlap, roundedCorners=sidebarCorners, cornerRadius=self.windowCornerRadius, windowPanel=True, seamless=self.disableSidebarMargins, contentsMargins=sidebarMargins):
							self.OnSidebarGUI(gui)

					with splitter.addArea(id_='&!mainArea', stretchFactor=2, verticalSpacing=0, contentsMargins=NO_MARGINS):
						mainAreaInnerCorners = INNER_CORNERS.LEFT if self.isSidebarVisible else INNER_CORNERS.NONE
						mainAreaCorners = joinCorners(
							maskCorners(leftOverCorners, CORNERS.RIGHT),
							selectInnerCorners(innerCorners, mainAreaInnerCorners)
						)
						mainAreaOverlap = (0, topOverlap, 0, bottomOverlap)
						self._mainAreaGUI(gui, overlap=mainAreaOverlap, roundedCorners=mainAreaCorners, innerCorners=joinInnerCorners(innerCorners, mainAreaInnerCorners))
				leftOverCorners = CORNERS.NONE
			else:
				mainAreaCorners = leftOverCorners
				leftOverCorners = CORNERS.NONE
				mainAreaOverlap = (0, topOverlap, 0, bottomOverlap)
				self._mainAreaGUI(gui, overlap=mainAreaOverlap, roundedCorners=mainAreaCorners, innerCorners=innerCorners)

			if self.isStatusbarVisible:
				statusbarMargins = self._statusbarMargins
				with gui.hPanel(overlap=(0, 1), roundedCorners=statusbarCorners, cornerRadius=self.windowCornerRadius, windowPanel=self.statusbarIsWindowPanel, seamless=self.disableStatusbarMargins, contentsMargins=statusbarMargins, vSizePolicy=SizePolicy.Fixed.value):
					self.OnStatusbarGUI(gui)

	def _titleBarGUI(self, gui: _TPythonGUI, roundedCorners: RoundedCorners, cornerRadius: float, overlap: Overlap) -> None:
		lSpacing = gui.spacing
		tSpacing = gui.smallSpacing - 1
		with gui.hLayout(contentsMargins=(lSpacing, tSpacing*0, 0, 0),):
			gui.label(self._getWindowIcon())
		with gui.hLayout(horizontalSpacing=0):
			self._titleOrToolbarGUI(gui, overlap)
			self._titleBarButtonsGUI(gui, overlap=joinOverlap(overlap, (1, 0, 0, 0)), roundedCorners=maskCorners(roundedCorners, CORNERS.RIGHT), cornerRadius=cornerRadius)

	def _titleOrToolbarGUI(self, gui: _TPythonGUI, overlap: Overlap) -> None:
		if self.isToolbarVisible and self.isToolbarInTitleBar:
			mg = gui.panelMargins
			with gui.hPanel(
					overlap=joinOverlap(overlap, (1, 0, 1, 0)),
					roundedCorners=CORNERS.NONE,
					cornerRadius=self.windowCornerRadius,
					windowPanel=False,
					contentsMargins=(mg, 0, mg, 0),
					sizePolicy=(SizePolicy.Expanding.value, SizePolicy.Fixed.value)):
				self._toolbarInTitleBar = gui.lastWidget
				self.OnToolbarGUI(gui)

			newIgnoredToolbarObject = [ c for c in self._toolbarInTitleBar.children() if isinstance(c, QWidget)]
			self.setIgnoredToolbarObjects(newIgnoredToolbarObject)

		else:
			self._toolbarInTitleBar = None
			self.setIgnoredToolbarObjects([])

			gui.elidedLabel(self.windowTitle() or qApp.applicationDisplayName())
			gui.addHSpacer(0, SizePolicy.Expanding)

	def _getWindowIcon(self) -> QIcon:
		windowIcon: QIcon = self.windowIcon()
		if windowIcon.isNull():
			windowIcon: QIcon = qApp.windowIcon()
		if windowIcon.isNull():
			windowIcon: QIcon = getDefaultAppIcon()
		return windowIcon

	def _titleBarButtonsGUI(self, gui: _TPythonGUI, overlap: Overlap, roundedCorners: RoundedCorners, cornerRadius: float) -> None:
		maximizeTip = 'Restore' if self.isMaximized() else 'Maximize'
		maximizeIcon = icons.btnRestore if self.isMaximized() else icons.btnMaximize

		with gui.hLayout(horizontalSpacing=0):
			gui.customWidget(self._minimizeBtn, icon=icons.btnMinimize, tip='Minimize', roundedCorners=maskCorners(roundedCorners, CORNERS.LEFT), cornerRadius=cornerRadius,
							overlap=adjustOverlap(overlap, (None, None, 1, None)), focusPolicy=Qt.NoFocus,  # onInit=self._addIgnoreObject,
							)

			gui.customWidget(self._maximizeBtn, icon=maximizeIcon, tip=maximizeTip, roundedCorners=CORNERS.NONE,
							overlap=adjustOverlap(overlap, (1, None, 1, None)), focusPolicy=Qt.NoFocus,  # onInit=self._addIgnoreObject,
							)

			gui.customWidget(self._closeBtn, icon=icons.btnClose, tip='Close', roundedCorners=maskCorners(roundedCorners, CORNERS.RIGHT), cornerRadius=cornerRadius,
							overlap=adjustOverlap(overlap, (1, None, None, None)), focusPolicy=Qt.NoFocus,  # onInit=self._addIgnoreObject,
							)

	def _mainAreaGUI(self, gui: _TPythonGUI, overlap: Overlap, roundedCorners: RoundedCorners, innerCorners: InnerCorners):
		if self.OnBottombarGUI is not None:
			with gui.vSplitter(handleWidth=self.windowSpacing, childrenCollapsible=True) as splitter:
				with splitter.addArea(stretchFactor=2, id_='&!contents', verticalSpacing=0, seamless=False):
					contentsOverlap = adjustOverlap(overlap, (None, None, None, 0))
					contentsRoundedCorners = joinCorners(roundedCorners, selectInnerCorners(innerCorners, INNER_CORNERS.BOTTOM))
					contentsMargins = self._contentMargins
					with gui.vPanel(overlap=contentsOverlap, roundedCorners=contentsRoundedCorners, cornerRadius=self.windowCornerRadius, windowPanel=True, seamless=self.disableContentMargins, contentsMargins=contentsMargins):
						self.OnGUI(gui)

				with splitter.addArea(stretchFactor=0, id_='&!bottombar', verticalSpacing=0, seamless=False):
					bottomOverlap = adjustOverlap(overlap, (None, 0, None, None))
					bottomRoundedCorners = joinCorners(roundedCorners, selectInnerCorners(innerCorners, INNER_CORNERS.TOP))
					bottomMargins = self._bottombarMargins
					with gui.vPanel(overlap=bottomOverlap, roundedCorners=bottomRoundedCorners, cornerRadius=self.windowCornerRadius, windowPanel=True, seamless=self.disableBottombarMargins, contentsMargins=bottomMargins):
						self.OnBottombarGUI(gui)
		else:
			contentsMargins = self._contentMargins
			with gui.vPanel(overlap=overlap, roundedCorners=roundedCorners, cornerRadius=self.windowCornerRadius, windowPanel=True, seamless=self.disableContentMargins, contentsMargins=contentsMargins):
				self.OnGUI(gui)

	def redraw(self):
		self._gui.redrawGUI()

	def redrawLater(self, cause: Optional[str] = None):
		self._gui.redrawLater(cause)

	@CrashReportWrapped
	def paintEvent(self, event: QPaintEvent) -> None:
		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)
			if self.isMaximized() or self.isFullScreen():
				p.fillRect(self.rect(), QColor('black'))
			else:
				h = self.height()
				w = self.width()
				p.drawPixmap(QRectF(0.,      0.,      32.,     32.),     self._shadowData, QRectF( 0.,  0., 32., 32.))
				p.drawPixmap(QRectF(32.,     0.,      w - 64., 32.),     self._shadowData, QRectF(31.,  0.,  2., 32.))
				p.drawPixmap(QRectF(w - 32., 0.,      32.,     32.),     self._shadowData, QRectF(32.,  0., 32., 32.))
				p.drawPixmap(QRectF(w - 32., 32.,     32.,     h - 64.), self._shadowData, QRectF(32., 31., 32.,  2.))
				p.drawPixmap(QRectF(w - 32., h - 32.,     32., 32.),     self._shadowData, QRectF(32., 32., 32., 32.))
				p.drawPixmap(QRectF(32.,     h - 32., w - 64., 32.),     self._shadowData, QRectF(31., 32.,  2., 32.))
				p.drawPixmap(QRectF(0.,      h - 32.,     32., 32.),     self._shadowData, QRectF( 0., 32., 32., 32.))
				p.drawPixmap(QRectF(0.,      32.,     32.,     h - 64.), self._shadowData, QRectF( 0., 31., 32.,  2.))

	@CrashReportWrapped
	def showEvent(self, event: QShowEvent) -> None:
		super(CatFramelessWindowMixin, self).showEvent(event)
		self.redraw()
		if not self._isInited:
			win = self.windowHandle()
			if win:
				titleBar = [self._titleBar] if self._titleBar is not None else []
				ignoredObjects = self._ignoredTitleBarObjects + self._ignoredToolbarObjects
				framelessWindowsManager.registerWindow(win, titleBar=titleBar, ignoredObjects=ignoredObjects, borderSize=self.borderSize, borderMargin=self.borderMargin)
				# self._addIgnoreObject(self._minimizeBtn)
				# self._addIgnoreObject(self._maximizeBtn)
				# self._addIgnoreObject(self._closeBtn)
				self._isInited = True
		self.redraw()
		if self._initGeometry is not None:
			runLaterSafe(1, lambda geo=self._initGeometry: self.setInitialGeometry(*geo))
			self._initGeometry = None

	@CrashReportWrapped
	def hideEvent(self, event: QHideEvent) -> None:
		super(CatFramelessWindowMixin, self).hideEvent(event)
		if self._isInited:
			win = self.windowHandle()
			if win:
				framelessWindowsManager.deregisterWindow(win)
				self._isInited = False

	@CrashReportWrapped
	def onWindowStateChanged(self):
		if self.isMaximized() or self.isFullScreen():
			self.setContentsMargins(0, 0, 0, 0)
		elif not self.isMinimized():
			self.setContentsMargins(*self._shadowMargins)

		self._gui.host.repaint()
		self.update()
		self._gui.redrawGUI()

	@CrashReportWrapped
	def changeEvent(self:QWidget, event: QEvent) -> None:
		super(CatFramelessWindowMixin, self).changeEvent(event)
		shouldUpdate: bool = False
		if event.type() == QEvent.WindowStateChange:
			shouldUpdate = True
			self.windowStateChanged.emit()
		elif event.type() == QEvent.ActivationChange:
			shouldUpdate = True

		if shouldUpdate:
			self.update()