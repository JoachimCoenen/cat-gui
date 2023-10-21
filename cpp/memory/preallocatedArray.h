#ifndef PREALLOCATED_ARRAY_H_INCLUDED
#define PREALLOCATED_ARRAY_H_INCLUDED

#include <string>
#include <stdexcept>

namespace cat {

namespace memory {

template<typename T>
class DefaultCtorDtor
{
public:
	static inline void initialize(T* address) {
		new(address) T();
	}

	template<class... Args>
	static inline void create(T* address, Args&&... args) {
		new(address) T(std::forward<Args>(args)...);
	}

	static inline void destroy(T* object) {
		object->~T();
	}
};

template<typename T>
class WeakPointerCtorDtor
{
public:
	static inline void initialize(T** address) {
		*address = nullptr;
	}

	static inline void create(T** address, T* object) {
		*address = object;
	}

	static inline void destroy(T** object) {
		*object = nullptr;
	}
};


template<typename PAA>
class PreallocatedArrayCtorDtor
{
public:
	const size_t _itemCount;
	// size_t createCount = 0;
	// size_t destroyCount = 0;
	// void (*_printStats)(size_t, size_t, size_t);

	PreallocatedArrayCtorDtor(size_t itemCount
	//	, void (*printStats)(size_t, size_t, size_t)
	)
	: _itemCount(itemCount)
	//, _printStats(printStats)
	{ }

	inline void create(void* address, PAA* paaAddress) {
		//new(paaAddress) PAA(reinterpret_cast<PAA::T*>(address), _itemCount);
		*paaAddress = PAA(reinterpret_cast<PAA::T*>(address), _itemCount);
		//createCount++;
		//(*_printStats)(getItemSize(), 0, 0);
	}

	inline typename void* destroy(PAA* paa) {
		typename PAA::T* pooledData = paa->_values;  // data() - 1;
		//paa->~PAA();
		*paa = PAA();
		//new(object) PAA(); // fill with nill-array
		//destroyCount++;
		//(*_printStats)(0, getItemSize(), 0);
		return pooledData;
	}

	inline size_t getItemSize() const {
		return PAA::byteSizeForCount(_itemCount);
	}
};


template<typename _T, class _CtorDtor=DefaultCtorDtor<T>>
class PreallocatedArray
{
	friend class PreallocatedArrayCtorDtor<PreallocatedArray>;
public:
	using CtorDtor = _CtorDtor;
	using T = _T;
private:
	static_assert(sizeof(size_t) <= sizeof(T), "T is too small");

	//const size_t& _size;
	T* _values;


	size_t unsafe_size() const noexcept {
		return *reinterpret_cast<size_t*>(_values);
	}

public:

	using iterator = T*;
	using const_iterator = const T*;
	using reverse_iterator = std::reverse_iterator<iterator>;
	using const_reverse_iterator = std::reverse_iterator<const_iterator>;


	static size_t byteSizeForCount(size_t elementCount) {
		const size_t singeItemSize = ((sizeof(T) + sizeof(void *)-1) / sizeof(void *)) * sizeof(void *);
		return singeItemSize * (1 + elementCount);
	}

	PreallocatedArray() 
	: _values(nullptr)
	{ }

	PreallocatedArray(T* address, size_t size) 
	: //_size(*reinterpret_cast<size_t*>(address)),
	  _values(address)
	{
		(*reinterpret_cast<size_t*>(_values)) = size;

		for (size_t i = 0; i < size; ++i) {
			CtorDtor::initialize(&(data()[i]));
		}
	}

	PreallocatedArray(T* address, size_t size, const T& initVal) 
	: PreallocatedArray(address, size)
	{
		for (size_t i = 0; i < size; ++i) {
			data()[i] = initVal;
		}
	}

	~PreallocatedArray() {
		if (_values == nullptr) {
			return;
		}
		for (size_t i = 0; i < size(); ++i) {
			CtorDtor::destroy(&(data()[i]));
		}
		(*reinterpret_cast<size_t*>(_values)) = 0;
		_values = nullptr;
	}
 
	PreallocatedArray(PreallocatedArray&& other) noexcept // move constructor
	: _values(std::exchange(other._values, nullptr)) {}

	PreallocatedArray& operator=(PreallocatedArray&& other) noexcept {
		std::swap(_values, other._values);
		return *this;
	}

public:
	// element access
	inline const T& front() const { return data()[0]; }
	inline T& front()       { return data()[0]; }
	inline const T& back() const { return data()[size() - 1]; }
	inline T& back()       { return data()[size() - 1]; }

	inline const T& operator[ ](size_t i) const { 
		if (i >= size()) {
			_throwOutOfRange(i);
		}
		return data()[i]; }

	inline T& operator[ ](size_t i)       { 
		if (i >= size()) {
			_throwOutOfRange(i);
		}
		return data()[i]; }

	inline const T& at (size_t i) const {
		if (i >= size()) {
			_throwOutOfRange(i);
		}
		return data()[i];
	}

	inline T& at (size_t i) {
		if (i >= size()) {
			_throwOutOfRange(i);
		}
		return data()[i];
	}

	inline T* data() noexcept { return _values + 1; }
	inline const T* data() const noexcept { return _values + 1; }

public:
	// iterators
	iterator begin() noexcept { return data(); }
	iterator end() noexcept { return data() + size(); }

	const_iterator begin() const noexcept { return data(); }
	const_iterator end() const noexcept { return data() + size(); }

	const_iterator cbegin() const noexcept { return data(); }
	const_iterator cend() const noexcept { return data() + size(); }

	reverse_iterator rbegin() noexcept { return reverse_iterator(end()); }
	reverse_iterator rend() noexcept { return reverse_iterator(begin()); }

	const_reverse_iterator crbegin() const noexcept { return rbegin(); }
	const_reverse_iterator crend() const noexcept { return rend(); }


	// capacity
	inline size_t size() const noexcept { 
		if (_values == nullptr) {
			return 0;
		} else {
			return unsafe_size();
		}
	}

	bool empty() const noexcept { return size() == 0; }

private:
	[[noreturn]] void _throwOutOfRange(size_t index) const {
		throw std::out_of_range("Index " + std::to_string(index) + " is out of range. (size is " + std::to_string(size()) + ")");
	}

public:


	// Vector<T>& operator=(Vector<T>);
	// Vector<T>& operator=(Vector<T>&&) noexcept;


	// Non-Member Functions
	// template<typename H> friend bool operator==(const Vector<H>& lhs, const Vector<H>& rhs);

	/*
		// see https://stackoverflow.com/questions/3279543/what-is-the-copy-and-swap-idiom
		friend void swap(Vector& first, Vector& second)
		{
			using std::swap;

			swap(first.v_size, second.v_size);
			swap(first.v_capacity, second.v_capacity);
			swap(first.values, second.values);
		}
	*/
};


// template<typename T>
// inline Vector<T>::Vector(const Vector<T>& src) : v_size(src.v_size), v_capacity(src.v_capacity),
// 	values(new T[v_capacity])
// {
// 	for (int i = 0; i < v_size; ++i) {
// 		values[ i ] = src.values[ i ];
// 	}
// }

// template<typename T>
// inline Vector<T>::Vector(const Vector<T>&& mv)
// {
// 	swap(*this, mv);
// }

// template<typename T>
// inline Vector<T>& Vector<T>::operator=(Vector<T> src)
// {
// 	swap(*this, src);

// 	return *this;
// }

// template<typename T>
// inline Vector<T>& Vector<T>::operator=(Vector<T>&& mv) noexcept
// {
// 	swap(*this, mv);

// 	return *this;
// }


// template<typename H>
// inline bool operator==(const Vector<H>& lhs, const Vector<H>& rhs)
// {
// 	if (lhs.v_size != rhs.v_size) {
// 		return false;
// 	}

// 	for (int i = 0; i < lhs.v_size; ++i) {
// 		if (lhs.values[ i ] != rhs.values[ i ]) {
// 			return false;
// 		}
// 	}

// 	return true;
// }

}
}

#endif // PREALLOCATED_ARRAY_H_INCLUDED
