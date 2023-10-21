from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from math import atan2, copysign, cos, pi, sin, sqrt
from itertools import zip_longest
from time import perf_counter_ns
from typing import Optional, overload, TypeVar, Iterator, Iterable, ContextManager, Union, Generic

from PyQt5.QtCore import QRect, QSize, Qt, QLineF, QPointF, QRectF
from PyQt5.QtGui import QBrush, QFont, QPainter, QPainterPath, QPalette, QPen, QPolygonF, QPaintEvent, QPicture, \
	QColor, QTextDocument, QTextOption, QTransform, QWheelEvent
from PyQt5.QtWidgets import QWidget

from ...GUI.components.catWidgetMixins import CatFramedWidgetMixin, CatScalableWidgetMixin, CatStyledWidgetMixin, CORNERS, PaintEventDebug, \
	palettes
from ...GUI.components.Layouts import WithBlock
from ...GUI.utilities import CrashReportWrapped
from ...utils import Deprecated
from ...utils.collections_ import Stack


_TT = TypeVar('_TT')
_TS = TypeVar('_TS')


class Drawable:
	@abstractmethod
	def paint(self, painter: CatPainter):
		pass


class TupleInDisguise(Generic[_TT]):
	__slots__ = ('_values',)

	def __iter__(self) -> Iterator[_TT]:
		yield from self._values

	def __getitem__(self, index: int) -> _TT:
		return self._values[index]

	def __len__(self) -> int:
		return len(self._values)

	def __eq__(self, other: TupleInDisguise):
		if isinstance(other, TupleInDisguise):
			return all(v1 == v2 for v1, v2 in zip_longest(self, other, fillvalue=None))
		else:
			return False

	def __ne__(self, other: TupleInDisguise):
		if isinstance(other, TupleInDisguise):
			return any(v1 != v2 for v1, v2 in zip_longest(self, other, fillvalue=None))
		else:
			return True

	def __repr__(self):
		args = ', '.join(repr(v) for v in self)
		return f'{type(self).__name__}({args})'


class VectorLike(TupleInDisguise[_TT], Generic[_TT]):
	__slots__ = ('_values',)

	def __init_subclass__(cls, **kwargs):
		super(VectorLike, cls).__init_subclass__(**kwargs)
		cls._class = cls

	def __init__(self, *args: _TT):
		self._values: tuple[_TT, ...] = args

	def __add__(self: _TS, other: VectorLike[_TT]) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(v1 + v2 for v1, v2 in zip(self, other))
		return result

	def __sub__(self: _TS, other: VectorLike[_TT]) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(v1 - v2 for v1, v2 in zip(self, other))
		return result

	def __mul__(self: _TS, other: float) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(v1 * other for v1 in self)
		return result

	def __truediv__(self: _TS, other: float) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(v1 / other for v1 in self)
		return result

	def __neg__(self: _TS) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(-v1 for v1 in self)
		return result

	# iMaths
	def __iadd__(self: _TS, other: VectorLike[_TT]) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(v1 + v2 for v1, v2 in zip(self, other))
		return result

	def __isub__(self: _TS, other: VectorLike[_TT]) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(v1 - v2 for v1, v2 in zip(self, other))
		return result

	def __imul__(self: _TS, other: float) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(v1 * other for v1 in self)
		return result

	def __itruediv__(self: _TS, other: float) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(v1 / other for v1 in self)
		return result

	# rMaths
	def __rmul__(self: _TS, other: float) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(other * v1 for v1 in self)
		return result

	def scaled(self: _TS, other: VectorLike[_TT]) -> _TS:
		result = self._class.__new__(self._class)
		result._values = tuple(v1 * v2 for v1, v2 in zip(self, other))
		return result


VectorLike._class = VectorLike


class VectorCat(VectorLike[float]):
	__slots__ = ('_values',)

	@overload
	def __init__(self, x: float, y: float): ...

	@overload
	def __init__(self, x: float, y: float, z: float): ...

	@overload
	def __init__(self, x: float, y: float, z: float, *arg):
		pass

	def __init__(self, *args: float):
		super(VectorCat, self).__init__(*args)  # avoid warning "Call to __init__ of super class is missed"

	____ = __init__  # avoid warning "Redeclared '__init__' defined above without usage"
	del ____         # delete unused ___
	__init__ = VectorLike.__init__  # improve performance

	@property
	def x(self) -> float:
		return self[0]

	@property
	def y(self) -> float:
		return self[1]

	@property
	def z(self) -> float:
		return self[2]

	@property
	def magnitudeSqr(self) -> float:
		return sum(v * v for v in self)

	@property
	def magnitude(self) -> float:
		return sqrt(sum(v * v for v in self))

	@property
	def normalized(self) -> VectorCat:
		return self * (1 / self.magnitude)


class VectorQ:  # (VectorLike[float]):
	__slots__ = ('values',)

	def __init__(self, x: float, y: float):
		self.values: QPointF = QPointF(x, y)

	@property
	def x(self) -> float:
		return self.values.x()

	@property
	def y(self) -> float:
		return self.values.y()

	def __iter__(self) -> Iterator[float]:
		yield self.values.x()
		yield self.values.y()

	def __getitem__(self, index: int) -> float:
		if index == 0:
			return self.values.x()
		elif index == 1:
			return self.values.y()
		else:
			IndexError('index out of range')

	def __len__(self) -> int:
		return 2

	def __repr__(self) -> str:
		return f'{type(self).__name__}({self.x}, {self.y})'

	def adjusted(self, dx: float, dy: float) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = self.values + QPointF(dx, dy)
		return result

	def __add__(self, other: VectorQ) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = self.values + other.values
		return result

	def __sub__(self, other: VectorQ) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = self.values - other.values
		return result

	def __mul__(self, other: float) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = self.values * other
		return result

	def __truediv__(self, other: float) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = self.values / other
		return result

	def __neg__(self) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = -self.values
		return result

	# iMaths
	def __iadd__(self, other: VectorQ) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = self.values + other.values
		return result

	def __isub__(self, other: VectorQ) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = self.values - other.values
		return result

	def __imul__(self, other: float) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = self.values * other
		return result

	def __itruediv__(self, other: float) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = self.values / other
		return result

	# rMaths
	def __rmul__(self, other: float) -> VectorQ:
		result = VectorQ.__new__(VectorQ)
		result.values = other * self.values
		return result

	def scaled(self, other: VectorQ) -> VectorQ:
		v1 = self.values
		v2 = other.values
		return VectorQ(v1.x() * v2.x(), v1.y() * v2.y())

	def invScaled(self, other: VectorQ) -> VectorQ:
		v1 = self.values
		v2 = other.values
		return VectorQ(v1.x() / v2.x(), v1.y() / v2.y())
	
	@property
	def magnitudeSqr(self) -> float:
		return QPointF.dotProduct(self.values, self.values)

	@property
	def magnitude(self) -> float:
		return sqrt(QPointF.dotProduct(self.values, self.values))

	@property
	def normalized(self) -> VectorQ:
		magnitude = self.magnitude
		return self * (1 / magnitude) if magnitude else self

	def __eq__(self, other: VectorQ):
		if isinstance(other, VectorQ):
			return self.values == other.values
		else:
			return False

	def __ne__(self, other: VectorQ):
		if isinstance(other, VectorQ):
			return self.values != other.values
		else:
			return True


Vector = VectorQ


def dot(a: Vector, b: Vector) -> float:
	return a[0] * b[0] + a[1] * b[1]


class Matrix(VectorLike[Union[VectorCat, Vector]]):

	def __matmul__(self, other):
		selfLen = len(self)
		if isinstance(other, Vector):
			otherLen = len(other)
			assert selfLen == otherLen or selfLen == otherLen + 1
			if selfLen == otherLen:
				return Vector(*(sum(self[i][j] * other[i] for i in range(selfLen)) for j in range(selfLen)))
			else:
				other = (*other, 1.)
				# mult = [0., 0., 0.]
				# for j in range(selfLen):
				# 	for i in range(selfLen):
				# 		self_ij = self[i][j]
				# 		other_i = other[i]
				# 		mult[j] += self_ij * other_i

				mult = [sum(self[i][j] * other[i] for i in range(selfLen)) for j in range(selfLen)]
				return Vector(*mult[:-1]) / mult[-1]
		elif isinstance(other, Matrix):
			assert selfLen == len(other)
			return Matrix(
				*(
					VectorCat(*(sum(self[i][j] * other[k][i] for i in range(selfLen)) for j in range(selfLen)))
					for k in range(selfLen)
				)
			)


class Line(TupleInDisguise[Vector]):
	__slots__ = ('_values',)
	# __slots__ = ('start', 'end',)

	def __init__(self, start: Vector, end: Vector):
		self._values: tuple[Vector, Vector] = (start, end)

	@property
	def start(self) -> Vector:
		return self._values[0]

	@property
	def end(self) -> Vector:
		return self._values[1]

	def __iter__(self):
		yield from self._values


class Rect(TupleInDisguise[Vector]):
	__slots__ = ('_values',)

	# __slots__ = ('topLeft', 'bottomRight',)

	@property
	def topLeft(self) -> Vector:
		return self._values[0]

	@property
	def bottomRight(self) -> Vector:
		return self._values[1]

	@property
	def center(self) -> Vector:
		return (self._values[0] + self._values[1]) / 2.

	def adjusted(self, L: float, t: float, r: float, b: float) -> Rect:
		return Rect(topLeft=self.topLeft.adjusted(L, t), bottomRight=self.bottomRight.adjusted(r, b))

	@overload
	def __init__(self, *, center: Vector, size: Vector):
		pass

	@overload
	def __init__(self, *, bottomRight: Vector, center: Vector):
		pass

	@overload
	def __init__(self, *, bottomRight: Vector, size: Vector):
		pass

	@overload
	def __init__(self, *, topLeft: Vector, center: Vector):
		pass

	@overload
	def __init__(self, *, topLeft: Vector, size: Vector):
		pass

	@overload
	def __init__(self, *, topLeft: Vector, bottomRight: Vector):
		pass

	@overload
	def __init__(self, topLeft: Vector, bottomRight: Vector, /):
		pass

	def __init__(self, *args, **kwargs):
		topLeft: Vector
		bottomRight: Vector
		# values: tuple[Vector, Vector]
		if args:
			assert not kwargs
			assert len(args) == 2
			assert all(type(v) is Vector for v in args)
			topLeft, bottomRight = args
		else:
			if len(kwargs) != 2:
				raise TypeError("Bad arguments for Rect(). `topLeft` must be specified together with either `bottomRight`, `center` or `size`.")
			if not all(kw in {'topLeft', 'bottomRight', 'center', 'size'} for kw in kwargs.keys()):
				raise TypeError("Bad arguments for Rect(). `topLeft` must be specified together with either `bottomRight`, `center` or `size`.")

			topLeft: Optional[Vector] = kwargs.pop('topLeft', None)
			bottomRight: Optional[Vector] = kwargs.pop('bottomRight', None)
			center: Optional[Vector] = kwargs.pop('center', None)
			size: Optional[Vector] = kwargs.pop('size', None)

			if topLeft is not None:
				if bottomRight is not None:  # topLeft & bottomRight
					pass  # good!
				elif center is not None:  # topLeft & center
					bottomRight = center * 2 - topLeft
				else:  # topLeft & size
					bottomRight = topLeft + size
			elif bottomRight is not None:
				if center is not None:  # bottomRight & center
					topLeft = center * 2 - bottomRight
				else:  # bottomRight & size
					topLeft = bottomRight - size
			else:
				topLeft = center - size / 2
				bottomRight = center + size / 2

		self._values: tuple[Vector, Vector] = (topLeft, bottomRight,)

	@property
	def corners(self) -> tuple[Vector, Vector, Vector, Vector]:
		L, t = self.topLeft
		r, b = self.bottomRight
		return (
			Vector(L, b), Vector(r, b),
			Vector(r, t), Vector(L, t),
		)


class Polyline(TupleInDisguise[Vector]):
	__slots__ = ('_values',)

	def __init__(self, points: list[Vector], isClosed: bool = False):
		values = list(points)
		if isClosed and (values[0] != values[-1]):
			values.append(values[0])

		self._values: list[Vector] = values

	def __setitem__(self, index: int, value: Vector):
		self._values[index] = value

	@property
	def values(self) -> list[Vector]:
		return self._values


class Ellipse(TupleInDisguise[Vector]):
	__slots__ = ('_values',)

	# __slots__ = ('topLeft', 'bottomRight',)

	@property
	def center(self) -> Vector:
		return self._values[0]

	@property
	def radius(self) -> Vector:
		return self._values[1]

	def __init__(self, center: Vector, radius: Vector):
		self._values: tuple[Vector, Vector] = (center, radius,)


def makeTransformationMatrix(translation: Vector = Vector(0., 0.), scale: Vector = Vector(1, 1)) -> Matrix:  # tuple[Vector, Vector, Vector]:
	v1 = VectorCat(scale[0], 0., 0.)
	v2 = VectorCat(0., scale[1], 0.)
	v3 = VectorCat(translation[0], translation[1], 1.)
	return Matrix(v1, v2, v3)


@dataclass
class ScaledContext(ContextManager[None]):
	painter: CatPainter
	scale: Vector
	translation: Vector = field(default_factory=lambda: Vector(0., 0.))

	def __enter__(self) -> None:
		current = self.painter.transformationStack.peek()
		new = makeTransformationMatrix(self.translation, self.scale)
		new = new @ current
		self.painter.transformationStack.push(new)
		self.painter.painter.setTransform(QTransform(*new[0], *new[1], *new[2]))

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.painter.transformationStack.pop()
		old = self.painter.transformationStack.peek()
		self.painter.painter.setTransform(QTransform(*old[0], *old[1], *old[2]))


class ArrowType(Enum):
	none    = 0
	arrow   = 1
	dot     = 2
	box     = 3
	diamond = 4


def makePen(color: Union[str, int, QColor]) -> QPen:
	pen = QPen(QColor(color))
	pen.setJoinStyle(Qt.RoundJoin)
	return pen


def makeBrush(color: Union[str, int, QColor]) -> QPen:
	brush = QBrush(QColor(color))
	return brush


class Pens:
	aliceblue = makePen('aliceblue')
	antiquewhite = makePen('antiquewhite')
	aqua = makePen('aqua')
	aquamarine = makePen('aquamarine')
	azure = makePen('azure')
	beige = makePen('beige')
	bisque = makePen('bisque')
	black = makePen('black')
	blanchedalmond = makePen('blanchedalmond')
	blue = makePen('blue')
	blueviolet = makePen('blueviolet')
	brown = makePen('brown')
	burlywood = makePen('burlywood')
	cadetblue = makePen('cadetblue')
	chartreuse = makePen('chartreuse')
	chocolate = makePen('chocolate')
	coral = makePen('coral')
	cornflowerblue = makePen('cornflowerblue')
	cornsilk = makePen('cornsilk')
	crimson = makePen('crimson')
	cyan = makePen('cyan')
	darkblue = makePen('darkblue')
	darkcyan = makePen('darkcyan')
	darkgoldenrod = makePen('darkgoldenrod')
	darkgray = makePen('darkgray')
	darkgreen = makePen('darkgreen')
	darkkhaki = makePen('darkkhaki')
	darkmagenta = makePen('darkmagenta')
	darkolivegreen = makePen('darkolivegreen')
	darkorange = makePen('darkorange')
	darkorchid = makePen('darkorchid')
	darkred = makePen('darkred')
	darksalmon = makePen('darksalmon')
	darkseagreen = makePen('darkseagreen')
	darkslateblue = makePen('darkslateblue')
	darkslategray = makePen('darkslategray')
	darkturquoise = makePen('darkturquoise')
	darkviolet = makePen('darkviolet')
	deeppink = makePen('deeppink')
	deepskyblue = makePen('deepskyblue')
	dimgray = makePen('dimgray')
	dodgerblue = makePen('dodgerblue')
	firebrick = makePen('firebrick')
	floralwhite = makePen('floralwhite')
	forestgreen = makePen('forestgreen')
	fuchsia = makePen('fuchsia')
	gainsboro = makePen('gainsboro')
	ghostwhite = makePen('ghostwhite')
	gold = makePen('gold')
	goldenrod = makePen('goldenrod')
	gray = makePen('gray')
	green = makePen('green')
	greenyellow = makePen('greenyellow')
	honeydew = makePen('honeydew')
	hotpink = makePen('hotpink')
	indianred = makePen('indianred')
	indigo = makePen('indigo')
	ivory = makePen('ivory')
	khaki = makePen('khaki')
	lavender = makePen('lavender')
	lavenderblush = makePen('lavenderblush')
	lawngreen = makePen('lawngreen')
	lemonchiffon = makePen('lemonchiffon')
	lightblue = makePen('lightblue')
	lightcoral = makePen('lightcoral')
	lightcyan = makePen('lightcyan')
	lightgoldenrodyellow = makePen('lightgoldenrodyellow')
	lightgray = makePen('lightgray')
	lightgreen = makePen('lightgreen')
	lightpink = makePen('lightpink')
	lightsalmon = makePen('lightsalmon')
	lightseagreen = makePen('lightseagreen')
	lightskyblue = makePen('lightskyblue')
	lightslategray = makePen('lightslategray')
	lightsteelblue = makePen('lightsteelblue')
	lightyellow = makePen('lightyellow')
	lime = makePen('lime')
	limegreen = makePen('limegreen')
	linen = makePen('linen')
	magenta = makePen('magenta')
	maroon = makePen('maroon')
	mediumaquamarine = makePen('mediumaquamarine')
	mediumblue = makePen('mediumblue')
	mediumorchid = makePen('mediumorchid')
	mediumpurple = makePen('mediumpurple')
	mediumseagreen = makePen('mediumseagreen')
	mediumslateblue = makePen('mediumslateblue')
	mediumspringgreen = makePen('mediumspringgreen')
	mediumturquoise = makePen('mediumturquoise')
	mediumvioletred = makePen('mediumvioletred')
	midnightblue = makePen('midnightblue')
	mintcream = makePen('mintcream')
	mistyrose = makePen('mistyrose')
	moccasin = makePen('moccasin')
	navajowhite = makePen('navajowhite')
	navy = makePen('navy')
	oldlace = makePen('oldlace')
	olive = makePen('olive')
	olivedrab = makePen('olivedrab')
	orange = makePen('orange')
	orangered = makePen('orangered')
	orchid = makePen('orchid')
	palegoldenrod = makePen('palegoldenrod')
	palegreen = makePen('palegreen')
	paleturquoise = makePen('paleturquoise')
	palevioletred = makePen('palevioletred')
	papayawhip = makePen('papayawhip')
	peachpuff = makePen('peachpuff')
	peru = makePen('peru')
	pink = makePen('pink')
	plum = makePen('plum')
	powderblue = makePen('powderblue')
	purple = makePen('purple')
	red = makePen('red')
	rosybrown = makePen('rosybrown')
	royalblue = makePen('royalblue')
	saddlebrown = makePen('saddlebrown')
	salmon = makePen('salmon')
	sandybrown = makePen('sandybrown')
	seagreen = makePen('seagreen')
	seashell = makePen('seashell')
	sienna = makePen('sienna')
	silver = makePen('silver')
	skyblue = makePen('skyblue')
	slateblue = makePen('slateblue')
	slategray = makePen('slategray')
	snow = makePen('snow')
	springgreen = makePen('springgreen')
	steelblue = makePen('steelblue')
	tan = makePen('tan')
	teal = makePen('teal')
	thistle = makePen('thistle')
	tomato = makePen('tomato')
	transparent = makePen('transparent')
	turquoise = makePen('turquoise')
	violet = makePen('violet')
	wheat = makePen('wheat')
	white = makePen('white')
	whitesmoke = makePen('whitesmoke')
	yellow = makePen('yellow')
	yellowgreen = makePen('yellowgreen')
	default = black


class Brushes:
	aliceblue = makeBrush('aliceblue')
	antiquewhite = makeBrush('antiquewhite')
	aqua = makeBrush('aqua')
	aquamarine = makeBrush('aquamarine')
	azure = makeBrush('azure')
	beige = makeBrush('beige')
	bisque = makeBrush('bisque')
	black = makeBrush('black')
	blanchedalmond = makeBrush('blanchedalmond')
	blue = makeBrush('blue')
	blueviolet = makeBrush('blueviolet')
	brown = makeBrush('brown')
	burlywood = makeBrush('burlywood')
	cadetblue = makeBrush('cadetblue')
	chartreuse = makeBrush('chartreuse')
	chocolate = makeBrush('chocolate')
	coral = makeBrush('coral')
	cornflowerblue = makeBrush('cornflowerblue')
	cornsilk = makeBrush('cornsilk')
	crimson = makeBrush('crimson')
	cyan = makeBrush('cyan')
	darkblue = makeBrush('darkblue')
	darkcyan = makeBrush('darkcyan')
	darkgoldenrod = makeBrush('darkgoldenrod')
	darkgray = makeBrush('darkgray')
	darkgreen = makeBrush('darkgreen')
	darkkhaki = makeBrush('darkkhaki')
	darkmagenta = makeBrush('darkmagenta')
	darkolivegreen = makeBrush('darkolivegreen')
	darkorange = makeBrush('darkorange')
	darkorchid = makeBrush('darkorchid')
	darkred = makeBrush('darkred')
	darksalmon = makeBrush('darksalmon')
	darkseagreen = makeBrush('darkseagreen')
	darkslateblue = makeBrush('darkslateblue')
	darkslategray = makeBrush('darkslategray')
	darkturquoise = makeBrush('darkturquoise')
	darkviolet = makeBrush('darkviolet')
	deeppink = makeBrush('deeppink')
	deepskyblue = makeBrush('deepskyblue')
	dimgray = makeBrush('dimgray')
	dodgerblue = makeBrush('dodgerblue')
	firebrick = makeBrush('firebrick')
	floralwhite = makeBrush('floralwhite')
	forestgreen = makeBrush('forestgreen')
	fuchsia = makeBrush('fuchsia')
	gainsboro = makeBrush('gainsboro')
	ghostwhite = makeBrush('ghostwhite')
	gold = makeBrush('gold')
	goldenrod = makeBrush('goldenrod')
	gray = makeBrush('gray')
	green = makeBrush('green')
	greenyellow = makeBrush('greenyellow')
	honeydew = makeBrush('honeydew')
	hotpink = makeBrush('hotpink')
	indianred = makeBrush('indianred')
	indigo = makeBrush('indigo')
	ivory = makeBrush('ivory')
	khaki = makeBrush('khaki')
	lavender = makeBrush('lavender')
	lavenderblush = makeBrush('lavenderblush')
	lawngreen = makeBrush('lawngreen')
	lemonchiffon = makeBrush('lemonchiffon')
	lightblue = makeBrush('lightblue')
	lightcoral = makeBrush('lightcoral')
	lightcyan = makeBrush('lightcyan')
	lightgoldenrodyellow = makeBrush('lightgoldenrodyellow')
	lightgray = makeBrush('lightgray')
	lightgreen = makeBrush('lightgreen')
	lightpink = makeBrush('lightpink')
	lightsalmon = makeBrush('lightsalmon')
	lightseagreen = makeBrush('lightseagreen')
	lightskyblue = makeBrush('lightskyblue')
	lightslategray = makeBrush('lightslategray')
	lightsteelblue = makeBrush('lightsteelblue')
	lightyellow = makeBrush('lightyellow')
	lime = makeBrush('lime')
	limegreen = makeBrush('limegreen')
	linen = makeBrush('linen')
	magenta = makeBrush('magenta')
	maroon = makeBrush('maroon')
	mediumaquamarine = makeBrush('mediumaquamarine')
	mediumblue = makeBrush('mediumblue')
	mediumorchid = makeBrush('mediumorchid')
	mediumpurple = makeBrush('mediumpurple')
	mediumseagreen = makeBrush('mediumseagreen')
	mediumslateblue = makeBrush('mediumslateblue')
	mediumspringgreen = makeBrush('mediumspringgreen')
	mediumturquoise = makeBrush('mediumturquoise')
	mediumvioletred = makeBrush('mediumvioletred')
	midnightblue = makeBrush('midnightblue')
	mintcream = makeBrush('mintcream')
	mistyrose = makeBrush('mistyrose')
	moccasin = makeBrush('moccasin')
	navajowhite = makeBrush('navajowhite')
	navy = makeBrush('navy')
	oldlace = makeBrush('oldlace')
	olive = makeBrush('olive')
	olivedrab = makeBrush('olivedrab')
	orange = makeBrush('orange')
	orangered = makeBrush('orangered')
	orchid = makeBrush('orchid')
	palegoldenrod = makeBrush('palegoldenrod')
	palegreen = makeBrush('palegreen')
	paleturquoise = makeBrush('paleturquoise')
	palevioletred = makeBrush('palevioletred')
	papayawhip = makeBrush('papayawhip')
	peachpuff = makeBrush('peachpuff')
	peru = makeBrush('peru')
	pink = makeBrush('pink')
	plum = makeBrush('plum')
	powderblue = makeBrush('powderblue')
	purple = makeBrush('purple')
	red = makeBrush('red')
	rosybrown = makeBrush('rosybrown')
	royalblue = makeBrush('royalblue')
	saddlebrown = makeBrush('saddlebrown')
	salmon = makeBrush('salmon')
	sandybrown = makeBrush('sandybrown')
	seagreen = makeBrush('seagreen')
	seashell = makeBrush('seashell')
	sienna = makeBrush('sienna')
	silver = makeBrush('silver')
	skyblue = makeBrush('skyblue')
	slateblue = makeBrush('slateblue')
	slategray = makeBrush('slategray')
	snow = makeBrush('snow')
	springgreen = makeBrush('springgreen')
	steelblue = makeBrush('steelblue')
	tan = makeBrush('tan')
	teal = makeBrush('teal')
	thistle = makeBrush('thistle')
	tomato = makeBrush('tomato')
	transparent = makeBrush('transparent')
	turquoise = makeBrush('turquoise')
	violet = makeBrush('violet')
	wheat = makeBrush('wheat')
	white = makeBrush('white')
	whitesmoke = makeBrush('whitesmoke')
	yellow = makeBrush('yellow')
	yellowgreen = makeBrush('yellowgreen')
	default = transparent


class CatPainter(WithBlock):

	def __init__(self, widget: RenderArea, antiAliased: bool = True):
		super().__init__()
		self.renderArea: RenderArea = widget

		self.currentWidgetSize = widget.currentCanvasSize

		self.painter: QPainter = QPainter()
		self.transformationStack: Stack[Matrix] = Stack()
		self.transformationStack.push(makeTransformationMatrix())
		self.antiAliased: bool = antiAliased
		self.painter.setRenderHint(QPainter.Antialiasing, self.antiAliased)
		self.boundingSize = Vector(1, 1)

	def setBoundingSize(self, width: float, height: float):
		self.boundingSize = Vector(width, height)
		self.renderArea.picture.setBoundingRect(QRect(0, 0, int(self.boundingSize[0]), int(self.boundingSize[1])))

	def scaled(self, scale: Vector = Vector(1., 1.), translation: Vector = Vector(0., 0.)) -> ScaledContext:
		return ScaledContext(self, scale, translation)

	def point(self, point: Vector, pen: QPen = Pens.default):
		self.painter.setPen(pen)
		self.points((point,), pen)

	def points(self, points: Iterable[Vector], pen: QPen = Pens.default):
		self.painter.setPen(pen)
		qLine = QPolygonF(p.values for p in points)
		self.painter.drawPoints(qLine)

	def line(self, line: Line, pen: QPen = Pens.default):
		self.painter.setPen(pen)
		qLine = QLineF(line.start.values, line.end.values)
		self.painter.drawLine(qLine)

	def polyline(self, line: Polyline, pen: QPen = Pens.default):
		self.painter.setPen(pen)
		qLine = QPolygonF(p.values for p in line)
		self.painter.drawPolyline(qLine)

	def spline(self, line: Polyline, pen: QPen = Pens.default):
		self.painter.setPen(pen)
		qPath: QPainterPath = QPainterPath(line[0].values)
		for i in range(1, ((len(line) - 1) // 3) * 3 + 1, 3):
			qPath.cubicTo(line[i].values, line[i + 1].values, line[i + 2].values)
		self.painter.drawPath(qPath)

	def drawArrowlike(self, tip: Vector, base: Vector, scale: float, arrowType: ArrowType, inverted: bool, empty: bool, pen: QPen = Pens.default, brush: QBrush = Brushes.default):
		arrowWidthHalf = 0.3333333333
		if inverted:
			tip, base = base, tip
		dir = (tip - base).normalized * scale

		def drawArrow() -> Vector:
			M = Matrix(Vector(0., -1.), Vector(1., 0.))  # rotate counter-clockwise
			p1 = M @ dir * arrowWidthHalf
			p2 = tip - dir - p1
			p1 = tip - dir + p1
			if pen.joinStyle() == Qt.MiterJoin:
				w = pen.widthF()
				D = (tip - p1).normalized
				G = Vector(dir.y, -dir.x) / scale
				miterLen = min(pen.miterLimit(), abs(-w * D.magnitudeSqr / dot(D, G)))
				border = Polyline([tip - miterLen * dir / scale, p1, p2], isClosed=True)
			else:
				border = Polyline([tip, p1, p2], isClosed=True)
			if empty:
				self.polygon(border, pen, Brushes.transparent)
			else:
				self.polygon(border, pen, brush)
			return tip - dir

		def drawDot() -> Vector:
			if empty:
				self.ellipse2(tip - dir * arrowWidthHalf, Vector(arrowWidthHalf, arrowWidthHalf) * scale, pen, Brushes.transparent)
			else:
				self.ellipse2(tip - dir * arrowWidthHalf, Vector(arrowWidthHalf, arrowWidthHalf) * scale, pen, brush)
			return tip - dir * arrowWidthHalf * 2

		def drawBox() -> Vector:
			M = Matrix(Vector(0., -1.), Vector(1., 0.))  # rotate counter-clockwise
			dir2 = dir * arrowWidthHalf * 2
			a = M @ dir2 * 0.5
			border = Polyline([tip + a, tip - a, tip - dir2 - a, tip - dir2 + a], isClosed=True)
			if empty:
				self.polygon(border, pen, Brushes.transparent)
			else:
				self.polygon(border, pen, brush)
			return tip - dir * arrowWidthHalf

		def drawDiamond() -> Vector:
			M = Matrix(Vector(0., -1.), Vector(1., 0.))  # rotate counter-clockwise
			a = M @ dir * arrowWidthHalf - dir / 2
			border = Polyline([tip, tip + a, tip - dir, tip - dir - a], isClosed=True)
			if empty:
				self.polygon(border, pen, Brushes.transparent)
			else:
				self.polygon(border, pen, brush)
			return tip - dir

		arrowPainters = {
			ArrowType.none   : lambda: None,
			ArrowType.arrow  : drawArrow,
			ArrowType.dot    : drawDot,
			ArrowType.box    : drawBox,
			ArrowType.diamond: drawDiamond,
		}

		return arrowPainters[arrowType]()

	@Deprecated(msg="use drawArrowlike(...) instead.")
	def arrowHead(self, tip: Vector, baseDir: Vector, arrowSize: float, pen: QPen = Pens.default, brush: QBrush = Brushes.default):
		dir = tip - baseDir
		angle = atan2(dir.y, dir.x) + pi
		arrowP1 = tip + Vector(cos(angle + pi / 12), sin(angle + pi / 12)) * arrowSize
		arrowP2 = tip + Vector(cos(angle - pi / 12), sin(angle - pi / 12)) * arrowSize
		self.polygon(Polyline([tip, arrowP1, arrowP2], isClosed=True), pen, brush)

	def polygon(self, line: Polyline, pen: QPen = Pens.default, brush: QBrush = Brushes.default):
		self.polygons((line,), pen, brush)

	def polygons(self, lines: Iterable[Polyline], pen: QPen = Pens.default, brush: QBrush = Brushes.default):
		self.painter.setPen(pen)
		self.painter.setBrush(brush)
		for line in lines:
			qLine = QPolygonF(p.values for p in line.values)
			self.painter.drawPolygon(qLine)

	def rect(self, rect: Rect, pen: QPen = Pens.default, brush: QBrush = Brushes.default):
		self.painter.setPen(pen)
		self.painter.setBrush(brush)
		self.painter.drawRect(QRectF(rect[0].values, rect[1].values))

	def borderRect(self, rect: Rect, pen: QPen = Pens.default):
		self.painter.setPen(pen)
		self.painter.setBrush(Brushes.transparent)
		self.painter.drawRect(QRectF(rect[0].values, rect[1].values))

	def ellipse(self, rect: Rect, pen: QPen = Pens.default, brush: QBrush = Brushes.default):
		self.painter.setPen(pen)
		self.painter.setBrush(brush)
		qRect = QRectF(rect[0].values, rect[1].values)
		self.painter.drawEllipse(qRect)

	def ellipse2(self, pos: Vector, radius: Vector, pen: QPen = Pens.default, brush: QBrush = Brushes.default):
		self.painter.setPen(pen)
		self.painter.setBrush(brush)
		self.painter.drawEllipse(pos.values, radius[0], radius[1])

	def ellipses(self, points: list[Vector], radius: Vector, pen: QPen = Pens.default, brush: QBrush = Brushes.default):
		self.painter.setPen(pen)
		self.painter.setBrush(brush)
		r = radius
		for p in points:
			self.painter.drawEllipse(p.values, r[0], r[1])

	def setFont(self, font: str = None, size: float = None) -> None:
		qFont = self.painter.font()
		size = round(size)
		fontChanged = False
		if font:
			if qFont.family() != font:
				fontChanged = True
			qFont.setFamily(font)
		if size is not None:
			if qFont.pixelSize() != size:
				fontChanged = True
			qFont.setPixelSize(size)
		if fontChanged:
			qFont.setHintingPreference(QFont.PreferNoHinting)
			self.painter.setFont(qFont)

	def text(self, text: str, rect: Union[Rect, Vector], alignment: Qt.Alignment = Qt.AlignCenter, font: str = None, size: float = None, pen: QPen = Pens.default):
		self.painter.setPen(pen)
		self.setFont(font, size)

		isRect = isinstance(rect, Rect)
		if isRect:
			qRect = QRectF(
				QPointF(min(rect[0].x, rect[1].x), min(rect[0].y, rect[1].y)),
				QPointF(max(rect[1].x, rect[0].x), max(rect[1].y, rect[0].y))
			)
			textOption = QTextOption(alignment)
			self.painter.drawText(qRect, text, textOption)
		else:
			qPoint = QPointF(rect.x, rect.y)
			self.painter.drawText(qPoint, text)

	def richText(self, html: str, rect: Union[Rect, Vector], alignment: Qt.Alignment = Qt.AlignCenter, font: str = None, size: float = None, pen: QPen = Pens.default):
		doc = self.getTextDocument(html, alignment, font, size)
		self.drawTextDocument(doc, rect, pen)

	def getTextDocument(self, html: str, alignment: Qt.Alignment = Qt.AlignCenter, font: str = None, size: float = None) -> QTextDocument:
		self.setFont(font, size)
		qFont = self.painter.font()

		doc = QTextDocument()
		doc.setDefaultTextOption(QTextOption(alignment))
		doc.setDocumentMargin(0)
		doc.setDefaultFont(qFont)
		doc.setHtml(html)
		return doc

	def drawTextDocument(self, doc: QTextDocument, rect: Union[Rect, Vector], pen: QPen = Pens.default):
		self.painter.setPen(pen)
		if isinstance(rect, Rect):
			topLeft = Vector(min(rect[0].x, rect[1].x), min(rect[0].y, rect[1].y))
			bottomRight = Vector(max(rect[1].x, rect[0].x), max(rect[1].y, rect[0].y))
			qRect = QRectF(QPointF(0, 0), (bottomRight - topLeft).values)
		else:
			topLeft = rect
			qRect = QRectF()

		with self.scaled(translation=topLeft):
			doc.drawContents(self.painter, qRect)

	def __enter__(self) -> CatPainter:
		super().__enter__()
		self.currentWidgetSize = self.renderArea.currentCanvasSize
		self.painter.begin(self.renderArea.picture)
		self.painter.setWorldMatrixEnabled(True)
		self.painter.setRenderHint(QPainter.Antialiasing, self.antiAliased)
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.painter.end()
		self.renderArea.update()
		return super().__exit__(exc_type, exc_val, exc_tb)


class RenderArea(QWidget, CatFramedWidgetMixin, CatScalableWidgetMixin, CatStyledWidgetMixin):

	def __init__(self, parent: Optional[QWidget] = None):
		super(RenderArea, self).__init__(parent)
		self.picture = QPicture()
		self.currentCanvasSize = QPointF(1., 1.)

		self.currentZoom: float = 1.
		self.center = QPointF(0., 0.)
		self.lastWheelEventTime: float = 0.
		self.avgWheelVelocity: float = 0.

		self.setBackgroundRole(QPalette.Base)
		self.setAutoFillBackground(False)
		self._roundedCorners = CORNERS.ALL
		self.setColorPalette(palettes.windowPanelColorPalette)

	def minimumSizeHint(self):
		return QSize(100, 100)

	def sizeHint(self):
		return QSize(400, 200)

	def _getBaseScaling(self) -> float:
		paintDstRect = self.currentCanvasSize
		boundingRect = self.picture.boundingRect()
		boundingWidth = max(1, boundingRect.width())
		boundingHeight = max(1, boundingRect.height())
		scaling = min(paintDstRect.x() / boundingWidth, paintDstRect.y() / boundingHeight)
		return max(0.0001, scaling)

	def _canvasToWorld(self, p: QPointF) -> QPointF:
		canvasSize = self.currentCanvasSize
		baseScaling = self._getBaseScaling()
		p2 = p - canvasSize * 0.5
		p2 /= baseScaling
		p2 /= self.currentZoom
		return p2 + self.center

	def _worldToCanvas(self, p: QPointF) -> QPointF:
		canvasSize = self.currentCanvasSize
		baseScaling = self._getBaseScaling()
		p2 = p - self.center
		p2 *= self.currentZoom
		p2 *= baseScaling
		return p2 + canvasSize * 0.5

	@CrashReportWrapped
	@PaintEventDebug
	def paintEvent(self, event: QPaintEvent):
		self.updateScaleFromFontMetrics()
		rect = self.adjustRectByOverlap(self.rect())

		# get Colors:
		bkgBrush = self.getBackgroundBrush(rect)
		borderBrush = self.getBorderBrush()

		paintDstRect = event.rect()
		boundingRect = self.picture.boundingRect()
		canvasSize = QPointF(paintDstRect.width(), paintDstRect.height())
		self.currentCanvasSize = canvasSize
		with QPainter(self) as p:
			p.setRenderHint(QPainter.Antialiasing, True)
			p.save()
			if boundingRect.width() != 0 or boundingRect.height() != 0:
				scaling = self._getBaseScaling() * self.currentZoom
				p.translate(canvasSize * 0.5)
				p.scale(scaling, scaling)
				p.translate(self.center)
			self.picture.play(p)
			p.restore()

			p.setPen(QPen(borderBrush, 1))
			p.setBrush(Brushes.transparent)
			borderPath = self.getBorderPath(rect)
			p.drawPath(borderPath)

	def wheelEvent(self, event: QWheelEvent) -> None:
		if event.angleDelta().y() == 0:
			event.ignore()
		# accelerated scrolling:
		zoomDelta = event.angleDelta().y() / 120

		newTime = perf_counter_ns() / 1_000_000_000
		deltaT = newTime - self.lastWheelEventTime
		self.lastWheelEventTime = newTime

		avgWheelVelocityHalfLife = 0.125  # in s
		localDecayFactor = 1 - (1 - 0.5) ** (deltaT / avgWheelVelocityHalfLife)

		self.avgWheelVelocity *= (1 - localDecayFactor)
		self.avgWheelVelocity += zoomDelta

		preFactor2 = zoomDelta + (self.avgWheelVelocity - zoomDelta) ** 3
		factor2 = copysign(abs(preFactor2) ** (1 / 3), preFactor2)

		# zoom to where the mouse points:
		wPos = self._canvasToWorld(event.position())
		self.currentZoom *= 2 ** (factor2 * 0.1)
		w2Pos = self._canvasToWorld(event.position())
		self.center += w2Pos - wPos

		self.update()
