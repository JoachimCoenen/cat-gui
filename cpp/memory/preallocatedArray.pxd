cdef extern from "preallocatedArray.h" namespace "cat::memory":
	cdef cppclass WeakPointerCtorDtor[T]:
		pass

	cdef cppclass PreallocatedArrayCtorDtor[PAA]:
		PreallocatedArrayCtorDtor(size_t itemCount
		#	, void (*printStats)(size_t, size_t, size_t)
		)

	cdef cppclass PreallocatedArray[T, _CtorDtor=*]:
		ctypedef _CtorDtor CtorDtor

		cppclass iterator:
			T& operator*()
			iterator operator++()
			iterator operator--()
			iterator operator+(size_t)
			iterator operator-(size_t)
			ptrdiff_t operator-(iterator)
			bint operator==(iterator)
			bint operator!=(iterator)
			bint operator<(iterator)
			bint operator>(iterator)
			bint operator<=(iterator)
			bint operator>=(iterator)
		cppclass reverse_iterator:
			T& operator*()
			reverse_iterator operator++()
			reverse_iterator operator--()
			reverse_iterator operator+(size_t)
			reverse_iterator operator-(size_t)
			ptrdiff_t operator-(reverse_iterator)
			bint operator==(reverse_iterator)
			bint operator!=(reverse_iterator)
			bint operator<(reverse_iterator)
			bint operator>(reverse_iterator)
			bint operator<=(reverse_iterator)
			bint operator>=(reverse_iterator)
		cppclass const_iterator(iterator):
			pass
		cppclass const_reverse_iterator(reverse_iterator):
			pass

		@staticmethod
		size_t byteSizeForCount(size_t)

		PreallocatedArray()
		PreallocatedArray(T*, size_t) except +
		PreallocatedArray(T*, size_t, T&) except +

		T& front()
		T& back()

		T& operator[](size_t)
		T& at(size_t) except +

		void assign(size_type, const T&)  # ???
		void assign[input_iterator](input_iterator, input_iterator) except +  # ???

		iterator begin()
		iterator end()

		const_iterator const_begin "begin"()
		const_iterator const_end "end"()

		reverse_iterator rbegin()
		reverse_iterator rend()

		const_reverse_iterator const_rbegin "crbegin"()
		const_reverse_iterator const_rend "crend"()

		# bint operator==(vector&, vector&)
		# bint operator!=(vector&, vector&)
		# bint operator<(vector&, vector&)
		# bint operator>(vector&, vector&)
		# bint operator<=(vector&, vector&)
		# bint operator>=(vector&, vector&)

		bint empty()
		size_t size()
