#include <Python.h>
#include <functional>

struct PyObjectPtrHash {
	size_t operator()(PyObject *o) const {
		return PyObject_Hash(o);
	}
};

struct PyObjectPtrHashEqual {
	bool operator()(PyObject *lhs, PyObject *rhs) const 
	{
		PyObjectPtrHash hash;
		return hash(lhs) == hash(rhs);
	}
};