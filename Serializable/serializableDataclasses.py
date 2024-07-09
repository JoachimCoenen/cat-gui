import builtins
import copy
import enum
import json
import sys
from dataclasses import Field, fields, MISSING
from typing import Any, Self, Union, Type, Optional, Callable, ForwardRef, ClassVar, IO, Iterator, Hashable

from better_orderedmultidict import OrderedMultiDict

from ..GUI import propertyDecorators as pd
from .utils import MemoForDeserialization, MemoForSerialization, SerializationPath, get_args, SerializationError, getRef, \
	typeHintMatchesType, valueMatchesType, BASIC_TYPES_ENUM, BASIC_TYPES, PropertyDecorator, _eval_type
from ..utils import SINGLETON_FIELD, NoneType, format_full_exc, Nothing
from ..utils.collections_ import FrozenDict
from ..utils.formatters import formatVal
from ..utils.logging_ import logError


type Dataclass = Any  # a @dataclasses.dataclass annotated class


_FIELDS_BY_NAME = '__dataclass_fields_by_name__'


def _fixAnnotations(cls_annotations: dict[str, ForwardRef | str], module: str) -> dict[str, ForwardRef]:
	new_annotations = {}
	for name, typeHint in cls_annotations.items():
		if isinstance(typeHint, str) and not typeHint.startswith('ClassVar'):
			typeHint = ForwardRef(typeHint, is_argument=False, module=module)
		new_annotations[name] = typeHint
	return new_annotations


# No @dataclass decorator for SerializableDataclass to allow for frozen inheritors.
class SerializableDataclass:
	__ignoredFieldsForDeserialization: ClassVar[frozenset[str]]

	def __init_subclass__(cls, *, ignoredFieldsForDeserialization: set[str] = (), **kwargs):
		"""
		:param ignoredFieldsForDeserialization: field names that should not be attempted to be deserialized. Add removed fields here, if you want to deserialize old data.
		:param kwargs: **kwargs
		:return:
		"""
		super(SerializableDataclass, cls).__init_subclass__(**kwargs)
		cls.__fixAnnotations()
		cls._subclasses = {}
		cls._registerSubclass(cls.__name__, cls)
		cls.__initFieldsDecorators()

		# check type of ignoreFieldsDeserialization:
		if not all(isinstance(name, str) for name in ignoredFieldsForDeserialization):
			TypeError(f"ignoreFieldsDeserialization contains non-strings.")

		cls.__ignoredFieldsForDeserialization: frozenset[str] = frozenset(ignoredFieldsForDeserialization)

	@classmethod
	def __fixAnnotations(cls) -> None:
		cls_annotations = cls.__dict__.get('__annotations__', {})
		new_annotations = _fixAnnotations(cls_annotations, module=cls.__module__)
		cls.__annotations__ = new_annotations

	@classmethod
	def __initFieldsDecorators(cls) -> None:
		for name, member in cls.__dict__.items():
			if isinstance(member, Field):
				decorators = getDecorators(member)
				lastDecorator = None
				for decorator in decorators:
					decorator.innerDecorator = lastDecorator  # getDecorator(prop)
					lastDecorator = decorator  # setDecorator(prop, self)
				setDecorator(member, lastDecorator)

	@classmethod
	def _getIgnoredFieldsForDeserialization(cls) -> frozenset[str]:
		return cls.__ignoredFieldsForDeserialization

	def serializeJson(self, strict: bool, memo: MemoForSerialization, path: tuple[Union[str, int], ...]) -> dict[str, Any]:
		return serializeJson(self, strict, memo, path)

	def dumpJson(self, outFile: IO[str]):
		json.dump(
			self.serializeJson(
				strict=True,
				memo={},
				path=()
			),
			outFile,
			skipkeys=False,
			ensure_ascii=True,
			check_circular=True,
			allow_nan=True,
			sort_keys=False,
			indent=2,
			separators=None
		)  # , default=default, cls=None)

	def toJson(self, outFile):
		self.dumpJson(outFile)

	@classmethod
	def fromJSONDict(cls, jsonDict: dict, memo: MemoForDeserialization, path: tuple[Union[str, int], ...], onError: Callable[[Exception, str], None] | None = None) -> Self:
		cls2 = cls._getCls(jsonDict)
		return _fromJSONDict(cls2, jsonDict, memo, path, onError=onError)

	@classmethod
	def fromJson(cls, string: str, onError: Callable[[Exception, str], None] | None = None) -> Self:
		decoder = json.JSONDecoder(object_hook=None, parse_float=None, parse_int=None, parse_constant=None, strict=True, object_pairs_hook=None)
		jsonDict = decoder.decode(string)
		return cls.fromJSONDict(jsonDict, {}, tuple(), onError=onError)

	def validate(self) -> list[pd.ValidatorResult]:
		"""
		errors are always first in the list.
		:return:
		"""
		fields_ = fields(self)
		results = []
		for f in fields_:
			results.extend(self.validateField(f))
		return results

	def validateField(self, f: Field) -> list[pd.ValidatorResult]:
		decorators = getDecorators(f)
		validators = [d for d in decorators if isinstance(d, pd.Validator)]
		value = getattr(self, f.name)
		return list(filter(None, (validator.validator(value) for validator in validators)))

	def copyFrom(self: Self, other: Self) -> None:
		"""sets self to a shallow copy of other"""
		if self is other:  # handle singletons
			return
		if not isinstance(other, SerializableDataclass):
			raise TypeError(f"expected a SerializableDataclass, but got {other}")
		for aField in fields(self):
			if shouldSerialize(aField, None):
				otherVal = getattr(other, aField.name)
				selfValIt = createCopy(otherVal)
				setattr(self, aField.name, next(selfValIt))
				next(selfValIt, None)

	_subclasses: ClassVar[dict[str, Type['SerializableDataclass']]] = {}

	@classmethod
	def _registerSubclass(cls, name: str, subCls: Type[Self]) -> None:
		cls._subclasses[name] = subCls
		for base in cls.__bases__:
			_registerSubclass = getattr(base, '_registerSubclass', None)
			if _registerSubclass is not None:
				_registerSubclass(name, subCls)

	@classmethod
	def _getCls(cls, jsonDict: dict[str, Any]):
		clsName = jsonDict.get("@class")
		if clsName is None:
			return cls
		subCls = cls._subclasses.get(clsName, None)
		if subCls is None:
			registeredSubclassesStr = f"{cls.__name__}._subclasses = {formatVal(cls._subclasses)}"
			print(registeredSubclassesStr)
			msg = (
				f"Unknown SerializableContainer class '{clsName}' not registered as subclass of '{cls.__qualname__}'.\n"
				f"{registeredSubclassesStr}")
			raise TypeError(msg)
		else:
			return subCls


def serializeJson(instance: Dataclass, strict, memo: MemoForSerialization, path: tuple[Union[str, int], ...]) -> dict[str, Any]:
	allFields: tuple[Field, ...] = fields(instance)
	mc = type(instance)

	result = {'@class': mc.__name__}
	if hasattr(mc, SINGLETON_FIELD):  # handle singletons
		return result

	for field in allFields:
		if shouldSerialize(field, instance):
			serializedName = getSerializedName(field)
			result[serializedName] = serializeJsonField(field, instance, strict=strict, memo=memo, path=path)

	return result


def serializeJsonField(field: Field, instance: Dataclass, strict: bool, memo: MemoForSerialization, path: SerializationPath):
	"""
	:param field: The field to be serialized
	:param instance: The instance containing the value to be serialized
	:param strict: whether to apply strict type checking or not
	:param memo:
	:param path:
	:raise: KeyError if there is no value for this property stored in the instances __values__ dict.
	:return:
	"""
	serializedName = getSerializedName(field)
	path = path + (serializedName,)

	rawValue = getattr(instance, field.name)
	return _encodeOrSerializeJsonValue(field, instance, rawValue, strict, memo, path)


def _encodeOrSerializeJsonValue(field: Field, instance: Dataclass, rawValue: Any, strict: bool, memo: MemoForSerialization, path: SerializationPath):
	typeHint: Type = getType(field)
	if typeHint is NoneType or typeHint is Any:
		logError(f"No Typehint specified for field {field.name} in dataclass {type(instance).__name__}")
		typeHint = NoneType

	if (encode := getEncode(field)) is not None:
		if not isinstance(rawValue, BASIC_TYPES_ENUM):
			if id(rawValue) in memo:
				return {'@ref': memo[id(rawValue)]}
			else:
				memo.setdefault(id(rawValue), path)
		encodedValue = encode(instance, rawValue)
	else:
		encodedValue = serializeJsonValue(typeHint, rawValue, strict, memo, path)
	return encodedValue


def serializeJsonValue(
		typeHint: Type,
		rawValue: Any,
		strict: bool,
		memo: MemoForSerialization,
		path: SerializationPath
):
	try:
		if not isinstance(rawValue, BASIC_TYPES_ENUM):
			if id(rawValue) in memo:
				return {'@ref': memo[id(rawValue)]}
			else:
				memo.setdefault(id(rawValue), path)
		# if isinstance(rawValue, SerializableContainerBase):
		if hasattr(rawValue, 'serializeJson'):
			return rawValue.serializeJson(strict=strict, memo=memo, path=path)
		elif isinstance(rawValue, list):
			innerTypeHint = get_args(typeHint)[0]
			return [serializeJsonValue(innerTypeHint, v, strict, memo, path=path + (i,)) for i, v in enumerate(rawValue)]
		elif isinstance(rawValue, tuple):
			innerTypeHint = get_args(typeHint)[0]
			return tuple(serializeJsonValue(innerTypeHint, v, strict, memo, path=path + (i,)) for i, v in enumerate(rawValue))
		elif isinstance(rawValue, set):
			innerTypeHint = get_args(typeHint)[0]
			return [serializeJsonValue(innerTypeHint, v, strict, memo, path=path + (i,)) for i, v in enumerate(rawValue)]
		elif isinstance(rawValue, dict):
			args = get_args(typeHint)
			keyTypeHint = args[0]
			valTypeHint = args[1]
			return {
				serializeJsonValue(keyTypeHint, k, strict, memo, path=path + (None,)): serializeJsonValue(valTypeHint, v, strict, memo, path + (k,))
				for k, v in rawValue.items()
			}
		elif isinstance(rawValue, OrderedMultiDict):
			args = get_args(typeHint)
			keyTypeHint = args[0]
			valTypeHint = args[1]
			return [
				(serializeJsonValue(keyTypeHint, k, strict, memo, path=path + (None,)), serializeJsonValue(valTypeHint, v, strict, memo, path + (k,)))
				for k, v in rawValue.items()
			]
		elif isinstance(rawValue, enum.Enum):
			if type(rawValue) is not typeHint and strict:
				raise SerializationError(
					f"Enum type of value ({formatVal(type(rawValue))}) is not declared type of serialized property ({formatVal(typeHint)}).",
					path=path
				)
			return rawValue.name
		elif isinstance(rawValue, BASIC_TYPES):
			return rawValue
		else:
			return rawValue
	except Exception as e:
		if not isinstance(e, SerializationError):
			raise SerializationError(str(e), path=path, typeHint=typeHint) from e
		else:
			raise


class __Missing:
	pass


__MISSING = __Missing()


def _fromJSONDict[T](cls: Type[T], jsonDict: dict, memo: MemoForDeserialization, path: tuple[Union[str, int], ...], onError: Callable[[Exception, str], None] | None = None) -> T:
	allFields = fields(cls)
	kwArgs = {}
	setLater = []
	try:
		for field in allFields:
			name = field.name
			if shouldSerialize(field, None):
				if shouldDeferLoading(field):
					setLater.append(field)
					if field.init is True and field.default is MISSING and field.default_factory is MISSING:
						kwArgs[name] = Nothing
				else:
					serializedName = getSerializedName(field)
					jsonValue = jsonDict.get(serializedName, __MISSING)
					if jsonValue is __MISSING:
						ifMissing = getIfMissing(field)
						if ifMissing is not None:
							jsonValue = ifMissing(None)
						elif field.init is True and field.default is MISSING and field.default_factory is MISSING:
							raise SerializationError(
								f"Missing mandatory constructor kwarg '{name}', (serializedName: '{serializedName}') for type {formatVal(cls)}.",
								path=path)
						else:
							continue

					_safeDeserializeJsonField(field, None, cls, jsonValue, memo, path, kwArgs.__setitem__, onError=onError)

		memo[path] = instance = cls(**kwArgs)

		def setValue(name: str, value: Any):
			setattr(instance, name, value)

		for field in setLater:
			serializedName = getSerializedName(field)
			jsonValue = jsonDict.get(serializedName, __MISSING)
			if jsonValue is __MISSING:
				ifMissing = getIfMissing(field)
				if ifMissing is not None:
					jsonValue: Any = ifMissing(instance)
			if jsonValue is not __MISSING:
				_safeDeserializeJsonField(field, instance, cls, jsonValue, memo, path, setValue, onError=onError)

		return instance

	except Exception as e:
		print("================ _fillFromJSONDict(...) ================")
		print(f"type(self) = {cls}")
		print(f"fields = {[f.name for f in allFields]}")
		print(f"jsonDict = {jsonDict}")
		print(format_full_exc(e))
		raise


def _safeDeserializeJsonField(
		field: Field,
		instance: Dataclass | None,
		cls: Type[Dataclass],
		jsonValue: Any,
		memo: MemoForDeserialization,
		path: SerializationPath,
		setValue: Callable[[str, Any], None],
		onError: Callable[[Exception, str], None] | None = None
):
	try:
		value = deserializeJsonField(field, instance, jsonValue, memo, path, onError=onError)
		setValue(field.name, value)
	except Exception as ex:
		_handleError(field, instance, cls, ex, onError)


def _handleError(
		field: Field,
		instance: Dataclass | None,
		cls: Type[Dataclass],
		ex: Exception,
		onError: Callable[[Exception, str], None] | None
) -> None:
	msg = f'{formatVal(cls)}.{field.name} in {type(instance) if instance is not None else cls.__name__}, serializedName="{getSerializedName(field)}"'
	if True and onError is not None:
		onError(ex, msg)
	else:
		ex.add_note(msg)
		raise


def deserializeJsonField(
		field: Field,
		instance: Dataclass | None,
		rawValue: Any,
		memo: MemoForDeserialization,
		path: SerializationPath,
		onError: Callable[[Exception, str], None] | None = None
):
	serializedName = getSerializedName(field)
	path = path + (serializedName,)

	typeHint: Type = getType(field)
	if typeHint is NoneType or typeHint is Any:
		logError(f"No Typehint specified for field {field.name} in dataclass {type(instance).__name__}")
		typeHint = NoneType

	if (decode := getDecode(field)) is not None:
		decodedValue = decode(instance, rawValue)
	else:
		decodedValue = rawValue
	propValue = deserializeJsonValue(field, typeHint, decodedValue, memo, path, onError)
	return propValue


def deserializeJsonValue(
		field: Field,
		typeHint: Type,
		decodedValue: Any,
		memo: MemoForDeserialization,
		path: SerializationPath,
		onError: Callable[[Exception, str], None] | None = None
) -> Any:
	try:
		if typeHint is NoneType or typeHint is Any:
			logError(f"No Typehint specified for field {field.name} in a dataclass")
			typeHint = NoneType
		propValue = Nothing
		if isinstance(decodedValue, dict):
			if '@ref' in decodedValue:
				propValue = getRef(decodedValue['@ref'], memo)
				return propValue

			# elif isinstance(typeHint, MetaContainer):  # typeHintMatchesType(typeHint, SerializableContainerBase) and type(typeHint).__name__ == 'MetaContainer':
			elif hasattr(typeHint, 'fromJSONDict'):  # typeHintMatchesType(typeHint, SerializableContainerBase) and type(typeHint).__name__ == 'MetaContainer':
				propValue = typeHint.fromJSONDict(decodedValue, memo, path, onError=onError)
			elif '@class' in decodedValue and getattr(getattr(typeHint, '__origin__', None), '_name', None) == 'Union':
				for tArg in get_args(typeHint):
					# if isinstance(tArg, MetaContainer) and decodedValue['@class'] in tArg._subclasses:
					if hasattr(tArg, 'fromJSONDict') and decodedValue['@class'] in tArg._subclasses:
						propValue = tArg.fromJSONDict(decodedValue, memo, path, onError=onError)
						break
			if propValue is Nothing:
				if typeHintMatchesType(typeHint, dict):
					args = get_args(typeHint)
					keyTypeHint = args[0]
					valTypeHint = args[1]
					propValue = {}
					memo[path] = propValue
					propValue.update({
						deserializeJsonValue(field, keyTypeHint, k, memo, path + (None,), onError=onError):
							deserializeJsonValue(field, valTypeHint, v, memo, path + (k,), onError=onError)
						for k, v in decodedValue.items()
					})
				else:
					raise SerializationError(
						f"Invalid type while loading field '{field.name}'. Type was {type(decodedValue)}, but required type is {repr(typeHint)}",
						path=path, typeHint=typeHint
					)

		# if propValue is Nothing and typeHintMatchesType(typeHint, SerializableContainerBase):
		# 	if valueMatchesType(decodedValue, getType(field)):
		# 		propValue = decodedValue
		# 		memo[path] = propValue
		if propValue is Nothing and typeHintMatchesType(typeHint, enum.Enum):
			propValue = typeHint[decodedValue]
		if propValue is Nothing and isinstance(decodedValue, (list, tuple)):
			containerType = None
			if typeHintMatchesType(typeHint, list):
				containerType = list
			elif typeHintMatchesType(typeHint, tuple):
				containerType = tuple
			elif typeHintMatchesType(typeHint, builtins.set):
				containerType = builtins.set

			if containerType is not None:
				memo[path] = propValue
				innerTypeHint = get_args(typeHint)[0]
				propValueGen = (deserializeJsonValue(field, innerTypeHint, v, memo, path + (i,), onError=onError) for i, v in enumerate(decodedValue))
				propValue = containerType(v for v in propValueGen if v is not Nothing)

		if propValue is Nothing and (typeHintMatchesType(typeHint, OrderedMultiDict)):
			args = get_args(typeHint)
			keyTypeHint = args[0]
			valTypeHint = args[1]
			propValue = OrderedMultiDict()
			memo[path] = propValue
			propValue.update(
				(
					deserializeJsonValue(field, keyTypeHint, k, memo, path + (None,), onError=onError),
					deserializeJsonValue(field, valTypeHint, v, memo, path + (k,), onError=onError)
				)
				for k, v in decodedValue
			)

		if propValue is Nothing and typeHintMatchesType(typeHint, enum.Enum):
			propValue = typeHint[decodedValue]
		if propValue is Nothing and valueMatchesType(decodedValue, typeHint):
			propValue = decodedValue
			memo[path] = propValue
		if propValue is Nothing:
			if typeHint is not NoneType:
				raise SerializationError(
					f"Invalid type while loading field '{field.name}'. Type was {type(decodedValue)}, but required type is {repr(typeHint)}",
					path=path, typeHint=typeHint
				)
			# raise RuntimeError(f"Invalid type while loading SerializedProperty '{prop.label_ if hasattr(prop, 'label_') else type(prop)}' in ???. Type was {type(decodedValue)}, but typeHint is {repr(typeHint)}")
			else:
				# for now raise RuntimeError(f"Invalid type while loading SerializedProperty '{sprop.label_ if hasattr(prop, 'label_') else type(prop)}' in ???. Type was {type(decodedValue)}, but typeHint is {repr(typeHint)}")
				propValue = None
		memo[path] = propValue
		return propValue
	except Exception as e:
		if not isinstance(e, SerializationError):
			raise SerializationError(str(e), path=path, typeHint=typeHint) from e
		else:
			raise


def createCopy[T](otherVal: T) -> Iterator[T]:
	if isinstance(otherVal, SerializableDataclass):
		return createCopySerializableDataclass(otherVal)
	elif isinstance(otherVal, list):
		return createCopyList(otherVal)
	elif isinstance(otherVal, tuple):
		return createCopyTuple(otherVal)
	elif isinstance(otherVal, dict):
		return createCopyDict(otherVal)
	else:
		return createCopySimple(otherVal)


def createCopySerializableDataclass(other: SerializableDataclass) -> Iterator[SerializableDataclass]:
	self = type(other)()
	yield self
	self.copyFrom(other)


def createCopyList[T](other: list[T]) -> Iterator[list[T]]:
	self = type(other)()
	yield self
	for otherVal in other:
		selfValIt = createCopy(otherVal)
		self.append(next(selfValIt))
		next(selfValIt, None)


def createCopyTuple(other: tuple) -> Iterator[tuple]:
	iters = tuple(createCopy(otherVal) for otherVal in other)
	if type(other) is tuple:
		self = tuple(next(selfValIt) for selfValIt in iters)
	else:
		self = type(other)(*(next(selfValIt) for selfValIt in iters))
	yield self
	for selfValIt in iters:
		next(selfValIt, None)


def createCopyDict[K: Hashable, T](other: dict[K, T]) -> Iterator[dict[K, T]]:
	self = type(other)()
	yield self
	for otherKey, otherVal in other.items():
		selfKeyIt = createCopy(otherKey)
		selfValIt = createCopy(otherVal)
		selfKey = next(selfKeyIt)
		next(selfKeyIt, None)
		self[selfKey] = next(selfValIt)
		next(selfValIt, None)


def createCopySimple[T](other: list[T]) -> Iterator[list[T]]:
	self = copy.deepcopy(other)
	yield self


def fieldsByName(class_or_instance: Dataclass | type[Dataclass]) -> dict[str, Field]:
	"""Return a dict describing the fields of this dataclass by their name.

	Accepts a dataclass or an instance of one; raises a TypeError otherwise.
	The result is cached per class.
	"""

	_fieldsByName = getattr(class_or_instance, _FIELDS_BY_NAME, None)
	if _fieldsByName is None:
		_fields = fields(class_or_instance)
		_fieldsByName = {field.name: field for field in _fields}

		cls = class_or_instance if isinstance(class_or_instance, type) else type(class_or_instance)
		setattr(cls, _FIELDS_BY_NAME, _fieldsByName)

	return _fieldsByName


def getField(class_or_instance: Dataclass | type[Dataclass], name: str) -> Field:
	"""Return the field of this dataclass that has the given name.

	Raises a KeyError if there is no such field.
	Accepts a dataclass or an instance of one; raises a TypeError otherwise.
	"""
	return fieldsByName(class_or_instance)[name]


def getFieldOptional(class_or_instance: Dataclass | type[Dataclass], name: str) -> Field | None:
	"""Return the field of this dataclass that has the given name.

	Returns None if there is no such field.
	Accepts a dataclass or an instance of one; raises a TypeError otherwise.
	"""
	return fieldsByName(class_or_instance).get(name)


__EMPTY_DICT = FrozenDict.EMPTY
__EMPTY_LIST = []

__SENTINEL = object()


def catMeta(
		*,
		readOnly: Optional[bool] = __SENTINEL,
		serialize: Optional[bool] = __SENTINEL,
		serializedName: Optional[str] = __SENTINEL,
		deferLoading: Optional[bool] = __SENTINEL,
		ifMissing: Optional[Callable[[Dataclass], Any]] = __SENTINEL,
		formatVal: bool | Callable[[Any], bool] = __SENTINEL,
		customPrintFunc: Optional[Callable[[SerializableDataclass], Any]] = __SENTINEL,
		encode: Optional[Callable[[Dataclass, Any], Any]] = __SENTINEL,
		decode: Optional[Callable[[Optional[Dataclass], Any], Any]] = __SENTINEL,
		# --------------------------------------------------------------------------------
		decorators: list[PropertyDecorator] = __SENTINEL,
		# --------------------------------------------------------------------------------
		kwargs: dict[str, Any] = __SENTINEL,
) -> dict[str, Any]:
	"""

	:param readOnly: default is False
	:param serialize: default is (not readOnly)
	:param serializedName:
	:param deferLoading:
	:param ifMissing:
	:param formatVal:
	:param customPrintFunc:
	:param encode:
	:param decode:
	:param decorators:
	:param kwargs:
	:return:
	"""
	catDict = {}
	if readOnly is not __SENTINEL:
		catDict['readOnly'] = readOnly

	if serialize is __SENTINEL and isinstance(readOnly, bool):
		serialize = readOnly

	if serialize is not __SENTINEL:
		catDict['serialize'] = serialize

	if serializedName is not __SENTINEL:
		catDict['serializedName'] = serializedName

	if deferLoading is not __SENTINEL:
		catDict['deferLoading'] = deferLoading

	if ifMissing is not __SENTINEL:
		catDict['ifMissing'] = ifMissing

	if formatVal is not __SENTINEL:
		catDict['formatVal'] = formatVal

	if customPrintFunc is not __SENTINEL:
		catDict['customPrintFunc'] = customPrintFunc

	if encode is not __SENTINEL:
		catDict['encode'] = encode

	if decode is not __SENTINEL:
		catDict['decode'] = decode

	if decorators is not __SENTINEL:
		catDict['decorators'] = decorators

	if kwargs is not __SENTINEL:
		catDict['kwargs'] = kwargs

	return dict(cat=catDict)


def getCatMeta(field: Field, key: str, default=None) -> Any:
	return field.metadata.get('cat', __EMPTY_DICT).get(key, default)


def setCatMeta(field: Field, key: str, value: Any) -> None:
	if (cat := field.metadata.get('cat')) is not None:
		cat[key] = value


def shouldSerialize(field: Field, dc: Dataclass) -> bool:
	sf = getCatMeta(field, 'serialize')
	if sf is True or (sf is None and field.init is True):
		return field.default is MISSING or dc is None or getattr(dc, field.name) != field.default
	else:
		return False  # sf is not False and sf(getattr(dc, field.name))


def getEncode(field: Field) -> Optional[Callable[[Dataclass, Any], Any]]:
	sf = getCatMeta(field, 'encode')
	return sf


def getDecode(field: Field) -> Optional[Callable[[Optional[Dataclass], Any], Any]]:
	sf = getCatMeta(field, 'decode')
	return sf


def getSerializedName(field: Field) -> str:
	sf = getCatMeta(field, 'serializedName', field.name)
	return sf


def shouldDeferLoading(field: Field) -> bool:
	sf = getCatMeta(field, 'deferLoading')
	return field.init is False or sf is True


def getIfMissing(field: Field) -> Optional[Callable[[Dataclass], Any]]:
	sf = getCatMeta(field, 'ifMissing')
	return sf


def shouldFormatVal(field: Field, val: Any) -> bool:
	sf = getCatMeta(field, 'formatVal')
	if sf is None:
		return field.repr is True
	else:
		return sf is True or (sf is not False and sf(val))


def isReadOnly(field: Field) -> bool:
	return getCatMeta(field, 'readOnly', False)


def getDecorators(field: Field) -> list[PropertyDecorator]:
	return getCatMeta(field, 'decorators', __EMPTY_LIST)


def getDecorator(field: Field) -> Optional[PropertyDecorator]:
	return getCatMeta(field, 'decorator', None)


def setDecorator(field: Field, decorator: Optional[PropertyDecorator]) -> None:
	return setCatMeta(field, 'decorator', decorator)


def getType(field: Field) -> Type[Any]:
	typeHint = field.type
	# handle forward references:
	if type(typeHint) is str:
		typeHint = ForwardRef(typeHint, is_argument=False)
	if type(typeHint) is ForwardRef:
		base_globals = sys.modules[field.__module__].__dict__
		typeHint = _eval_type(typeHint, base_globals, None)
		field.type = typeHint
	return typeHint


def getKwargs(field: Field) -> dict[str, Any]:
	return getCatMeta(field, 'kwargs', __EMPTY_DICT)


def getKWArg[T](field: Field, key: str, default: T) -> Any | T:
	return getCatMeta(field, 'kwargs', __EMPTY_DICT).get(key, default)


__all__ = [
	'SerializableDataclass',
	'fieldsByName',
	'getField',
	'getFieldOptional',

	'catMeta',
	'getCatMeta',
	'setCatMeta',
	'shouldSerialize',
	'getEncode',
	'getDecode',
	'getSerializedName',
	'shouldDeferLoading',
	'shouldFormatVal',
	'isReadOnly',
	'getDecorators',
	'getDecorator',
	'setDecorator',
	'getType',
	'getKwargs',
	'getKWArg',
]
