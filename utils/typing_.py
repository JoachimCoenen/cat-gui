from typing import _type_repr, TypeVar, NamedTuple

from Cat.utils.utils import Decorator


_TT = TypeVar('_TT')


typeRepr = _type_repr


NoneType = type(None)


def is_namedtuple(x) -> bool:
	t = x if isinstance(x, type) else type(x)
	b = t.__bases__
	if len(b) != 1 or b[0] != tuple:
		return False
	f = getattr(t, '_fields', None)
	if not isinstance(f, tuple):
		return False
	return all(type(n) is str for n in f)


def replace_tuple(obj: NamedTuple, /, **changes):
	"""Return a new object replacing specified fields with new values."""

	# We're going to mutate 'changes', but that's okay because it's a
	# new dict, even if called with 'replace(obj, **my_changes)'.

	if not is_namedtuple(obj):
		raise TypeError("replace_tuple() should be called on NamedTuple instances")

	# It's an error to have init=False fields in 'changes'.
	# If a field is not in 'changes', read its value from the provided obj.
	fields: tuple[str, ...] = getattr(type(obj), '_fields', None)
	for f in fields:
		if f not in changes:
			changes[f] = getattr(obj, f)
	return type(obj)(**changes)


@Decorator
def override(func: _TT) -> _TT:
	"""
	documents that a method overrides a method in a supertype.
	This is an identity operation.
	"""
	return func


__all__ = [
	'typeRepr',
	'NoneType',
	'is_namedtuple',
	'replace_tuple',
	'override',
]