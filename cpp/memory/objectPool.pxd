cdef extern from "objectPool2.h" namespace "cat::memory":
	cdef cppclass DefaultOPCtorDtor[T]:
		pass

	cdef cppclass ObjectPool[T, _CtorDtor=*, TMemoryAllocator=*]:
		ObjectPool(_CtorDtor&&)
		ObjectPool(_CtorDtor&&, size_t, size_t)
		ObjectPool(size_t, size_t)
		T* create() except +
		T* create[Arg1]                  (Arg1&&) except +
		T* create[Arg1, Arg2]            (Arg1&&, Arg2&&) except +
		T* create[Arg1, Arg2, Arg3]      (Arg1&&, Arg2&&, Arg3&&) except +
		T* create[Arg1, Arg2, Arg3, Arg4](Arg1&&, Arg2&&, Arg3&&, Arg4&&) except +
		T* getNextWithoutInitializing() except +
		void destroy(T *object) except +

		inline size_t totalAllocations() const
		inline size_t totalDestroyed() const
		inline size_t currentlyAlive() const
		
		inline size_t itemSize() const
		size_t totalMemorySize() const
		size_t totalNodesSize() const
		size_t totalSize() const
