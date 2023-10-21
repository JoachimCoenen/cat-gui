#ifndef OBJECT_POOL2_H
#define OBJECT_POOL2_H


#include <stdexcept>
#include <type_traits>
#include <utility>
#include <unordered_map>
#include <iostream>

namespace cat {

namespace memory {

class DefaultMemoryAllocator
{
public:
	static inline void *Allocate(size_t size) {
		// if (size < 1000) {
		// 	std::cout << "Allocate Memory Block of size " << size << " bytes.\n";
		// } else {
		// 	std::cout << "Allocate Memory Block of size " << size / 1000 << " k bytes.\n";
		// }
		return ::operator new(size, ::std::nothrow);
	}

	static inline void Deallocate(void *pointer, size_t size) {
		::operator delete(pointer);
	}
};


template<typename T>
class DefaultOPCtorDtor
{
public:
	template<class... Args>
	inline void create(void* address, Args&&... args) {
		new(address) T(std::forward<Args>(args)...);
	}

	inline void* destroy(T* object) {
		object->~T();
		return object;
	}

	constexpr inline size_t getItemSize() const {
		// padds to ptr size
		return ((sizeof(T) + sizeof(void *)-1) / sizeof(void *)) * sizeof(void *);
	}
};


template<typename T, class _CtorDtor=DefaultOPCtorDtor<T>, class TMemoryAllocator=DefaultMemoryAllocator>
class ObjectPool
{
// public:
// 	using CtorDtor = _CtorDtor;
private:
	struct _Node
	{
	private:
		_Node *_nextNode;
		size_t _itemSize;
		size_t _itemCount;
	public:
		_Node(size_t capacity, size_t itemSize) {
			// std::clog << "}} _Node(capacity=" << capacity << ", itemSize=" << itemSize << ")" << std::endl;
			if (capacity < 1) {
				std::clog << "  }} ERROR: capacity must be at least 1." << std::endl;
				throw std::invalid_argument("capacity must be at least 1.");
			}
			_nextNode = nullptr;
			_itemSize = itemSize;
			_itemCount = 0;
			// std::clog << "}} _Node(...) DONE!" << std::endl;
		}

		~_Node() {
			// const size_t itemSize = itemSize();
			// char* memory = (char *)memory();
			// const char* end = memory + memorySize();
			// for (char* ptr = memory; ptr < end; ptr += itemSize) {
			// 	if (*((void**)ptr) != nullptr) {
			// 		_ctorDtor.destroy((T*)ptr);
			// 	}
			// }
			// std::clog << "}} ~_Node()" << std::endl;
			if (_nextNode != nullptr) {
				delete _nextNode;
				_nextNode = nullptr;
			}
			// TMemoryAllocator::Deallocate(_memory, memorySize());
		}

		inline void* memory() { return nullptr; }
		inline const void* memory() const { return nullptr; }

		inline void setNextNode(_Node* aNode) { _nextNode = aNode; }

		inline _Node* nextNode() { return _nextNode; }
		inline const _Node* nextNode() const { return _nextNode; }

		inline constexpr size_t itemSize() const { return _itemSize; }
		inline size_t capacity() const { return 256; }
		inline size_t emptySlots() const { return 128; }
		inline size_t memorySize() const { return _itemCount * _itemSize; }
		inline const void* lastSlot() const { return nullptr; }
		inline bool hasSlots() const { return true; }
		inline bool isEmpty() const { return false; }

	public:
		void destroy(void *deletedObj) {
			// std::clog << "}} _Node.destroy(" << (size_t)deletedObj << ")" << std::endl;
			if (isEmpty()) {
				std::clog << "  }} ERROR: node already empty. emptySlots=" << emptySlots() << ", capacity=" << capacity() << std::endl;
				throw std::length_error("node already empty");
			}
			TMemoryAllocator::Deallocate(deletedObj, itemSize());
			_itemCount--;
		}

		void* getNextWithoutInitializing() {
			// std::clog << "}} _Node.getNextWithoutInitializing()" << std::endl;
			void* result = TMemoryAllocator::Allocate(itemSize());
			if (result == nullptr) {
				std::clog << "  }} ERROR: std::bad_alloc()" << std::endl;
				throw std::bad_alloc();
			}
			_itemCount++;
			return result;
		}

		void clearDeletedChain() {
			// std::clog << "}} _Node.clearDeletedChain()" << std::endl;
			// pass
		}

	};

	_CtorDtor _ctorDtor;
	// void *_nodeMemory;  // non-owning, never null
	// void *_firstDeleted;  // non-owning, might be null
	//size_t _nodeCapacity;
	_Node *_firstNode;
	_Node *_lastNode;  // non-owning, never null
	size_t _maxBlockLength;

	size_t _totalAllocations = 0;
	size_t _totalDestroyed = 0;
	size_t _currentlyAlive = 0;

	// size_t _poolIdx = 0;

	//static const size_t _itemSize;

	// ObjectPool(const ObjectPool<T, TMemoryAllocator> &source);
	// void operator = (const ObjectPool<T, TMemoryAllocator> &source);

	_Node *_allocateNewNode() {
		// std::clog << "}} ObjectPool._allocateNewNode()" << std::endl;
		const size_t lastCapacity = _lastNode->capacity();
		size_t newCapacity;
		if (lastCapacity >= _maxBlockLength) {
			newCapacity = _maxBlockLength;
		} else {
			// newCapacity = lastCapacity * 2;
			newCapacity = lastCapacity + lastCapacity / 2;
			newCapacity = newCapacity > lastCapacity ? newCapacity : lastCapacity + 1;

			if (newCapacity < lastCapacity) {
				throw std::overflow_error("capacity became too big (integer overflow).");
			}

			if (newCapacity >= _maxBlockLength) {
				newCapacity = _maxBlockLength;
			}
		}

		_Node *newNode = new _Node(newCapacity, _ctorDtor.getItemSize());
		// std::clog << "  }} _lastNode=" << (size_t)_lastNode << std::endl;
		_lastNode->setNextNode(newNode);
		_lastNode = newNode;
		return newNode;
	}

	// static std::unordered_map<size_t, ObjectPool*> _allPools;
	// static size_t _lastPoolIdx;

	static size_t registerPool(ObjectPool* pool) {
		return 0;
		// if (pool-> _poolIdx == 0) {
		// 	_lastPoolIdx++;
		// 	pool->_poolIdx = _lastPoolIdx;
		// }
		// _allPools[pool->_poolIdx] = pool;
		// return pool->_poolIdx;
	}

	static void unregisterPool(ObjectPool* pool) {
		// if (pool-> _poolIdx != 0) {
		// 	_allPools.erase(pool->_poolIdx);
		// }
	}

public:
	explicit ObjectPool(_CtorDtor&& ctorDtor, size_t initialCapacity=32, size_t maxBlockLength=1000000)
	: _ctorDtor(std::move(ctorDtor)),
	  _firstNode(new _Node(initialCapacity, _ctorDtor.getItemSize())),
	  _maxBlockLength(maxBlockLength) 
	{
		// std::clog << "}} ObjectPool()" << std::endl;
		if (maxBlockLength < 1) {
			throw std::invalid_argument("maxBlockLength must be at least 1.");
		}

		_lastNode = _firstNode;
		registerPool(this);
	}

	explicit ObjectPool(size_t initialCapacity=32, size_t maxBlockLength=1000000)
	: ObjectPool(_CtorDtor(), initialCapacity, maxBlockLength)
	{}

	~ObjectPool() {
		// std::clog << "}} ~ObjectPool()" << std::endl;
		_Node* aNode = _firstNode;
		while (aNode != nullptr) {
			clearNode(*aNode);
			aNode = aNode->nextNode();
		}
		if (_firstNode) {
			delete _firstNode;
		}
		unregisterPool(this);
	}

	ObjectPool(ObjectPool&& other)
	: _ctorDtor(std::move(other._ctorDtor)),
	  _firstNode(std::move(other._firstNode)),
	  _lastNode(std::move(other._lastNode)),  // non-owning, never null
	  _maxBlockLength(other._maxBlockLength),
	  _totalAllocations(other._totalAllocations),
	  _totalDestroyed(other._totalDestroyed),
	  _currentlyAlive(other._currentlyAlive),
	  //_poolIdx(other._poolIdx)
	{
		// std::clog << "}} ObjectPool(&&)" << std::endl;
		other._firstNode = NULL;
		other._lastNode = NULL;
		//other._poolIdx = 0;
		registerPool(this);
	}

	inline ObjectPool& operator = (ObjectPool&& other) {
		// std::clog << "}} ObjectPool.operator=(&&)" << std::endl;
		swap(_ctorDtor, other._ctorDtor);
		swap(_firstNode, other._firstNode);
		swap(_lastNode, other._lastNode);
		swap(_maxBlockLength, other._maxBlockLength);
		swap(_totalAllocations, other._totalAllocations);
		swap(_totalDestroyed, other._totalDestroyed);
		swap(_currentlyAlive, other._currentlyAlive);
		//swap(_poolIdx, other._poolIdx);
		registerPool(this);
		registerPool(other);
		// _ctorDtor = std::move(other._ctorDtor);
		// _firstNode = std::move(other._firstNode);
		// _lastNode = std::move(other._lastNode);  // non-owning, never null
		// _maxBlockLength = other._maxBlockLength;
		// _totalAllocations = other._totalAllocations;
		// _totalDestroyed = other._totalDestroyed;
		// _currentlyAlive = other._currentlyAlive;
	}

	template<class... Args>
	T* create(Args&&... args) {
		// std::clog << "}} ObjectPool.create(...)" << std::endl;
		void* result1 = getNextWithoutInitializing();
		void* result = result1;
		_ctorDtor.create(result, std::forward<Args>(args)...);
		return (T*)result;
	}

	/// This method is useful if you want to call a non-default constructor.
	/// It should be used like this:
	/// new (pool.getNextWithoutInitializing()) ObjectType(... parameters ...);
	T* getNextWithoutInitializing() {
		// std::clog << "}} ObjectPool.getNextWithoutInitializing()" << std::endl;
		// find first non-full node:
		_Node* aNode = _firstNode;
		while (aNode != nullptr) {
			if (aNode->hasSlots()) {
				break;
			}
			aNode = aNode->nextNode();
		}

		if (!aNode) {
			aNode = _allocateNewNode();
		}

		void* address = aNode->getNextWithoutInitializing();

		_totalAllocations++;
		_currentlyAlive++;
		return (T *)address;
	}

	void destroy(T *object) {
		// std::clog << "}} ObjectPool.destroy(" << (size_t)object << ")" << std::endl;
		void* deletedObj = _ctorDtor.destroy(object);
		std::pair<_Node*, _Node*> nodes = findNodeForPtr(deletedObj);
		_Node* prevNode = nodes.first;
		_Node* aNode = nodes.second;
		// std::clog << "  }} aNode == " << (size_t)aNode << std::endl;
		aNode->destroy(deletedObj);
		// std::clog << "  }} past Destruction! " << std::endl;
		_totalDestroyed++;
		_currentlyAlive--;

		_Node* nextNode = aNode->nextNode();
		if (aNode->isEmpty() && !(_firstNode == aNode && nextNode == nullptr)) {
			// std::clog << "}} aNode is empty! " << aNode->emptySlots() << ")" << std::endl;
			aNode->setNextNode(nullptr);
			if (prevNode) {
				prevNode->setNextNode(nextNode);
			}
			if (_firstNode == aNode) {
				_firstNode = nextNode;
			}
			if (_lastNode == aNode) {
				_lastNode = prevNode;
			}
			delete aNode;
		}
	}

public:
	inline size_t totalAllocations() const { return _totalAllocations; }
	inline size_t totalDestroyed() const { return _totalDestroyed; }
	inline size_t currentlyAlive() const { return _currentlyAlive; }


	inline size_t itemSize() const { return _ctorDtor.getItemSize(); }
	size_t totalMemorySize() const {
		size_t total = 0;
		const _Node* aNode = _firstNode;
		while (aNode != nullptr) {
			total += aNode->memorySize();
			aNode = aNode->nextNode();
		}
		return total;
	}

	size_t totalNodesSize() const {
		size_t total = 0;
		const _Node* aNode = _firstNode;
		while (aNode != nullptr) {
			total += aNode->memorySize();
			total += sizeof *aNode;
			aNode = aNode->nextNode();
		}
		return total;
	}

	size_t totalSize() const {
		size_t total = 0;
		total += totalNodesSize();
		total += sizeof *this;
		// not neccessary if _firstNode is a pointer: total -= sizeof _firstNode;  // _firstNode already accounted for in totalNodesSize()
		return total;
	}

	// static const std::unordered_map<size_t, ObjectPool*> allPools() {
	// 	return _allPools;
	// }

private:
	std::pair<_Node*, _Node*> findNodeForPtr(void* pointer) {
		// std::clog << "}} ObjectPool.findNodeForPtr(" << (size_t)pointer << ")" << std::endl;
		_Node* prevNode = nullptr;
		_Node* aNode = _firstNode;
		while (aNode != nullptr) {
			if (true || (aNode->memory() <= pointer && pointer <= aNode->lastSlot())) {
				return std::pair<_Node*, _Node*>(prevNode, aNode);
			}
			prevNode = aNode;
			aNode = aNode->nextNode();
		}
		return std::pair<_Node*, _Node*>(nullptr, nullptr);
	}


	void clearNode(_Node& aNode) {
		// std::clog << "}} ObjectPool.clearNode(...)" << std::endl;
		// set entire deleted chain to null:
		aNode.clearDeletedChain();

		const size_t itemSize = aNode.itemSize();
		char* memory = (char *)aNode.memory();
		const char* end = memory + aNode.memorySize();

		for (char* ptr = memory; ptr < end; ptr += itemSize) {
			if (*((void**)ptr) != nullptr) {
				_ctorDtor.destroy((T*)ptr);
			}
		}
	}

};

// template<class T, class _CtorDtor, class TMemoryAllocator>
// std::unordered_map<size_t, ObjectPool<T, _CtorDtor, TMemoryAllocator>*> ObjectPool<T, _CtorDtor, TMemoryAllocator>::_allPools = std::unordered_map<size_t, ObjectPool<T, _CtorDtor, TMemoryAllocator>*>();

// template<class T, class _CtorDtor, class TMemoryAllocator>
// size_t ObjectPool<T, _CtorDtor, TMemoryAllocator>::_lastPoolIdx = 0;

// template<typename T, class CtorDtor, class TMemoryAllocator>
// const size_t ObjectPool<T,CtorDtor, TMemoryAllocator>::_itemSize = ((sizeof(T) + sizeof(void *)-1) / sizeof(void *)) * sizeof(void *);

}
}

#endif // OBJECT_POOL2_H
