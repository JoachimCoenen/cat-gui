from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, ClassVar


class OperationKind(enum.Enum):
	PREFIX = 1
	INFIX = 2
	POSTFIX = 3
	FUNCTION = 4


class OperationType(enum.Enum):
	NUMBER = 0
	SUM = 10
	MULTIPLICATIVE = 20
	POWER = 30
	FUNCTION = 1000


@dataclass(frozen=True, slots=True)
class Displayable:
	display: str
	type: OperationType


class Curryable[T: Displayable](ABC):
	@abstractmethod
	def curry(self, operand: Result) -> T:
		...


@dataclass(frozen=True, slots=True)
class Result(Displayable):
	value: float | None

	def asOperandStrForOperation(self, operationType: OperationType, isRhs: bool) -> str:
		if self.type in {OperationType.NUMBER, OperationType.FUNCTION}:
			return self.display
		if operationType is OperationType.FUNCTION:
			return self.display

		if self.type is operationType:
			if isRhs or self.type is OperationType.POWER:
				return f"({self.display})"
			else:
				return self.display

		if self.type.value < operationType.value or (isRhs and self.type is operationType):
			return f"({self.display})"
		else:
			return self.display


@dataclass(frozen=True, slots=True)
class UnaryOperator(Displayable, Curryable[Result]):
	kind: OperationKind
	operation: Callable[[float], float | None]

	def _toStr(self, operand: Result) -> str:
		isRhs = self.kind == OperationKind.INFIX
		operand = operand.asOperandStrForOperation(self.type, isRhs)
		match self.kind:
			case OperationKind.PREFIX:
				return f"{self.display}{operand}"
			case OperationKind.INFIX:  # right hand side argument of infix operation
				return f"{self.display} {operand}"
			case OperationKind.POSTFIX:
				return f"{operand}{self.display}"
			case OperationKind.FUNCTION:
				return f"{self.display}({operand})"
		raise ValueError(f"Unhandled OperationKind: {self.kind}")

	def curry(self, operand: Result) -> Result:
		rhs = operand.value
		return Result(self._toStr(operand), self.type, None if rhs is None else self.operation(rhs))


@dataclass(frozen=True, slots=True)
class BinaryOperator(Displayable, Curryable[UnaryOperator]):
	kind: ClassVar[OperationKind] = OperationKind.INFIX  # binary operators are always infix operators.
	operation: Callable[[float, float], float | None]

	def _toStr(self, operand: Result) -> str:
		operand = operand.asOperandStrForOperation(self.type, False)
		return f"{operand} {self.display}"

	def curry(self, operand: Result) -> UnaryOperator:
		partialStr = self._toStr(operand)
		lhs = operand.value
		return UnaryOperator(partialStr, self.type, self.kind, lambda rhs: None if lhs is None else self.operation(lhs, rhs))


@dataclass
class CalculatorCore:
	_display: str = "0"
	_value: Result = field(default_factory=lambda: Result("0", OperationType.NUMBER, 0.0))

	sumInMemory: float = 0.0
	history: deque[Result] = field(default_factory=deque)

	pendingOperation: UnaryOperator | None = None
	waitingForOperand: bool = True
	lastOperationStr: str = ""

	@property
	def display(self) -> str:
		return self._display

	@display.setter
	def display(self, display: str) -> None:
		self._display = display
		try:
			value = float(display)
		except ValueError:
			value = None
		self._value = Result(display, OperationType.NUMBER, value)

	@property
	def value(self) -> Result:
		return self._value

	@value.setter
	def value(self, value: Result) -> None:
		self._value = value
		self._display = str(value.value) if value.value is not None else "###"

	def _abortOperation(self) -> None:
		self.clearAll()
		self.display = "###"

	def clearAll(self) -> None:
		self.pendingOperation = None
		self.display = "0"
		self.lastOperationStr = ""
		self.waitingForOperand = True

	def clear(self) -> None:
		self.display = "0"
		self.waitingForOperand = True

	def _clearLastOpStr(self) -> None:
		if self.pendingOperation is None:
			self.lastOperationStr = ""

	def _resetWaitingForOperandAndClearDisplay(self) -> None:  # todo find better name
		if self.waitingForOperand:
			self.waitingForOperand = False
			self.display = ""  # also sets self.value = 0

	def addDigit(self, digit: str) -> None:
		assert len(digit) == 1
		assert digit in '0123456789'

		if self.display == '0' and digit == '0':
			return

		self._resetWaitingForOperandAndClearDisplay()
		self._clearLastOpStr()

		self.display += digit

	def setValue(self, value: float) -> None:
		self._resetWaitingForOperandAndClearDisplay()
		self._clearLastOpStr()

		self.value = Result(str(value), OperationType.NUMBER, value)

	def decimalSeparator(self) -> None:
		self._resetWaitingForOperandAndClearDisplay()
		self._clearLastOpStr()
		if '.' not in self.display:
			self.display = self.display + "."

	def backspace(self) -> None:
		if self.waitingForOperand:
			return
		self._clearLastOpStr()
		self.display = self.display[:-1]
		if not self.display:
			self.clear()

	def changeSign(self) -> None:
		self._clearLastOpStr()
		if self.display.startswith("-"):
			self.display = self.display[1:]
		else:
			self.display = "-" + self.display

	def _applyPendingOperator(self) -> None:
		if self.pendingOperation is not None:
			self.unaryOperator(self.pendingOperation)
			self.pendingOperation = None

	def unaryOperator(self, operator: UnaryOperator) -> None:
		operand = self._value
		result = operator.curry(operand)
		if result.value is not None:
			self.history.appendleft(result)
			self.waitingForOperand = True
		else:
			self._abortOperation()
		self.value = result
		self.lastOperationStr = f"{result.display} = "

	def binaryOperator(self, operator: BinaryOperator) -> None:
		self._applyPendingOperator()
		self.pendingOperation = operator.curry(self.value)
		self.lastOperationStr = self.pendingOperation.display
		self.waitingForOperand = True

	def operator(self, operator: Curryable) -> None:
		if isinstance(operator, BinaryOperator):
			self.binaryOperator(operator)
		elif isinstance(operator, UnaryOperator):
			self.unaryOperator(operator)

	def equals(self) -> None:
		self._applyPendingOperator()

	def clearMemory(self) -> None:
		self.sumInMemory = 0.0

	def readMemory(self) -> None:
		self.setValue(self.sumInMemory)
		self.waitingForOperand = True

	def setMemory(self) -> None:
		self.equals()
		if self.value.value is not None:
			self.sumInMemory = self.value.value

	def addToMemory(self) -> None:
		self.equals()
		if self.value.value is not None:
			self.sumInMemory += self.value.value
