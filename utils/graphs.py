#  Copyright (c) 2021 Joachim Coenen. All Rights Reserved
from collections import defaultdict, deque
from typing import Callable, Hashable, Iterable, TypeVar

from Cat.utils.collections_ import OrderedMultiDict, Stack


# class _TK:
# 	pass
#
#
# class _TNode:
# 	pass


_TK = TypeVar('_TK', bound=Hashable)
_TNode = TypeVar('_TNode')
KeyNNode = tuple[_TK, _TNode]


DestinationGetter = Callable[[_TNode], Iterable[_TNode]]
DestinationGetter2 = Callable[[KeyNNode], Iterable[KeyNNode]]
IdGetter = Callable[[_TNode], _TK]


def getStronglyConnectedComponents(rootNodes: Iterable[_TNode], getDestinations: DestinationGetter, getId: IdGetter) -> list[list[_TNode]]:
	"""
	Tarjan's algorithm for finding the strongly connected components (SCCs) of a directed graph.
	It runs in linear time.
	:param rootNodes:
	:param getDestinations:
	:param getId:
	:return:
	"""
	# output: set of strongly connected components (sets of vertices)

	index: int = 0
	S: Stack[_TNode] = Stack()
	scComponents: list[list[_TNode]] = []  # strongly connected components

	indexes: dict[_TK, int] = defaultdict(lambda: -1)
	lowLinks: dict[_TK, int] = defaultdict(lambda: -1)
	onStack: set[_TK] = set()

	def strongConnect(src: _TNode, srcId: _TK):
		nonlocal S, index, indexes, lowLinks, onStack
		# Set the depth index for src to the smallest unused index
		indexes[srcId] = index
		lowLinks[srcId] = index
		index += 1
		S.push(src)
		onStack.add(srcId)

		# Consider successors of src
		for dst in getDestinations(src):
			dstId: _TK = getId(dst)
			if indexes[dstId] == -1:
				# Successor dst has not yet been visited; recurse on it
				strongConnect(dst, dstId)
				lowLinks[srcId] = min(lowLinks[srcId], lowLinks[dstId])
			elif dstId in onStack:
				# Successor dst is in stack S and hence in the current SCC
				# If dst is not on stack, then (src, dst) is an edge pointing to an SCC already found and must be ignored
				# Note: The next line may look odd - but is correct.
				# It says dst.index not dst.lowLink; that is deliberate and from the original paper
				lowLinks[srcId] = min(lowLinks[srcId], indexes[dstId])

		# If src is a root node, pop the stack and generate an SCC
		if lowLinks[srcId] == indexes[srcId]:
			cycle = []
			scComponents.append(cycle)
			while True:
				dst = S.pop()
				dstId: _TK = getId(dst)
				onStack.remove(dstId)
				cycle.append(dst)
				if dstId == srcId:
					break
			return cycle

	for node in rootNodes:
		nodeId: _TK = getId(node)
		if indexes[nodeId] == -1:
			strongConnect(node, nodeId)

	return scComponents


def getCycles(rootNodes: Iterable[_TNode], getDestinations: DestinationGetter, getId: IdGetter) -> list[list[_TNode]]:
	"""
	Finds all cycles in a directed graph.
	:param rootNodes:
	:param getDestinations:
	:param getId:
	:return:
	"""
	sccs = getStronglyConnectedComponents(rootNodes, getDestinations, getId)

	cycles: list[list[_TNode]] = []
	for scc in sccs:
		if len(scc) > 1:
			cycles.append(scc)
		else:  # scc of length 1
			nodeId = getId(scc[0])
			if any(nodeId == getId(dst) for dst in getDestinations(scc[0])):
				cycles.append(scc)  # cycle of length 1
	return cycles


def getStronglyConnectedComponents2(allNodes: list[KeyNNode], destinationsById: dict[_TK, list[KeyNNode]]) -> list[list[KeyNNode]]:
	"""
	Tarjan's algorithm for finding the strongly connected components (SCCs) of a directed graph.
	It runs in linear time.
	:param allNodes:
	:param destinationsById:
	:return:
	"""
	# output: set of strongly connected components (sets of vertices)

	index: int = 0
	S: Stack[KeyNNode] = Stack()
	scComponents: list[list[KeyNNode]] = []  # strongly connected components

	indexes: dict[_TK, int] = defaultdict(lambda: -1)
	lowLinks: dict[_TK, int] = defaultdict(lambda: -1)
	onStack: set[_TK] = set()

	def strongConnect(srcKey: _TK, src: _TNode):
		nonlocal S, index, indexes, lowLinks, onStack
		# Set the depth index for src to the smallest unused index
		indexes[srcKey] = index
		lowLinks[srcKey] = index
		index += 1
		S.push((srcKey, src))
		onStack.add(srcKey)

		# Consider successors of src
		for dstKey, dst in destinationsById[srcKey]:
			if indexes[dstKey] == -1:
				# Successor dst has not yet been visited; recurse on it
				strongConnect(dstKey, dst)
				lowLinks[srcKey] = min(lowLinks[srcKey], lowLinks[dstKey])
			elif dstKey in onStack:
				# Successor dst is in stack S and hence in the current SCC
				# If dst is not on stack, then (src, dst) is an edge pointing to an SCC already found and must be ignored
				# Note: The next line may look odd - but is correct.
				# It says dst.index not dst.lowLink; that is deliberate and from the original paper
				lowLinks[srcKey] = min(lowLinks[srcKey], indexes[dstKey])

		# If src is a root node, pop the stack and generate an SCC
		if lowLinks[srcKey] == indexes[srcKey]:
			cycle: list[KeyNNode] = []
			scComponents.append(cycle)
			while True:
				dstKey, dst = S.pop()
				onStack.remove(dstKey)
				cycle.append((dstKey, dst))
				if dstKey == srcKey:
					break

	for nodeKey, node in allNodes:
		if indexes[nodeKey] == -1:
			strongConnect(nodeKey, node)

	return scComponents


def getStronglyConnectedComponents3(allNodes: list[KeyNNode], destinationsById: dict[_TK, list[KeyNNode]]) -> list[list[KeyNNode]]:
	"""
	Kosaraju-Sharir's algorithm for finding the strongly connected components (SCCs) of a directed graph.
	It runs in linear time.
	:param allNodes:
	:param destinationsById:
	:return:
	"""
	sourcesById: dict[_TK, list[KeyNNode]] = defaultdict(list)
	for node in allNodes:
		outs = destinationsById[node[0]]
		for dstKey, _ in outs:
			sourcesById[dstKey].append(node)

	L: list[KeyNNode] = []  # L is reversed!
	visited: set[_TK] = set()
	assigned: set[_TK] = set()
	components: dict[_TK, list[KeyNNode]] = defaultdict(list)

	def visit(nodeKey: _TK, node: _TNode):
		"""
		Visit(u) is the recursive subroutine:
			If u is unvisited then:
				1. Mark u as visited.
				2. For each out-neighbour v of u, if v is unvisited, do Visit(v).
				3. Prepend u to L.
			Otherwise do nothing.
		"""
		visited.add(nodeKey)
		for dstKey, dst in destinationsById[nodeKey]:
			if dstKey not in visited:
				visit(dstKey, dst)
		L.append((nodeKey, node))  # L is reversed!

	def assign(nodeKey: _TK, node: _TNode, component: list[KeyNNode]):
		"""
		Assign(u,root) is the recursive subroutine:
			If u has not been assigned to a component then:
				1. Assign u as belonging to the component whose root is root.
				2. For each in-neighbour v of u, do Assign(v,root).
			Otherwise do nothing.
		"""
		if nodeKey not in assigned:
			assigned.add(nodeKey)
			component.append((nodeKey, node))
			for srcKey, src in sourcesById[nodeKey]:
				if srcKey not in assigned:
					assign(srcKey, src, component)

	# 1. For each vertex u of the graph do Visit(u)
	for nodeKey, node in allNodes:
		if nodeKey not in visited:
			visit(nodeKey, node)

	# 2. For each element u of L in order, do Assign(u,u)
	for nodeKey, node in reversed(L):
		if nodeKey not in assigned:
			assign(nodeKey, node, components[nodeKey])

	return components


def getStronglyConnectedComponents2X(allNodes: list[KeyNNode], destinationsById: dict[_TK, list[KeyNNode]]) -> list[KeyNNode]:
	"""
	Tarjan's algorithm for finding the strongly connected components (SCCs) of a directed graph.
	It runs in linear time.
	:param allNodes:
	:param destinationsById:
	:return:
	"""
	# output: set of strongly connected components (sets of vertices)

	index: int = 0
	S: Stack[KeyNNode] = Stack()
	scComponents: list[KeyNNode] = []  # strongly connected components

	indexes: dict[_TK, int] = defaultdict(lambda: -1)
	lowLinks: dict[_TK, int] = defaultdict(lambda: -1)
	onStack: set[_TK] = set()

	def strongConnect(srcKey: _TK, src: _TNode):
		nonlocal S, index, indexes, lowLinks, onStack
		# Set the depth index for src to the smallest unused index
		indexes[srcKey] = index
		lowLinks[srcKey] = index
		index += 1
		S.push((srcKey, src))
		onStack.add(srcKey)

		# Consider successors of src
		for dstKey, dst in destinationsById[srcKey]:
			if indexes[dstKey] == -1:
				# Successor dst has not yet been visited; recurse on it
				strongConnect(dstKey, dst)
				lowLinks[srcKey] = min(lowLinks[srcKey], lowLinks[dstKey])
			elif dstKey in onStack:
				# Successor dst is in stack S and hence in the current SCC
				# If dst is not on stack, then (src, dst) is an edge pointing to an SCC already found and must be ignored
				# Note: The next line may look odd - but is correct.
				# It says dst.index not dst.lowLink; that is deliberate and from the original paper
				lowLinks[srcKey] = min(lowLinks[srcKey], indexes[dstKey])

		# If src is a root node, pop the stack and generate an SCC
		if lowLinks[srcKey] == indexes[srcKey]:
			scComponents.append(S.peek())
			while True:
				dstKey = S.pop()[0]
				onStack.remove(dstKey)
				if dstKey == srcKey:
					break

	for nodeKey, node in allNodes:
		if indexes[nodeKey] == -1:
			strongConnect(nodeKey, node)

	return scComponents


def _getStartNodes(allNodes: list[KeyNNode], destinationsById: dict[_TK, list[KeyNNode]]) -> list[KeyNNode]:
	"""
	Finds all cycles in a directed graph.
	:param allNodes:
	:param destinationsById:
	:return:
	"""
	byKey: dict[_TK, KeyNNode] = {node[0]: node for node in allNodes}
	L1: dict[_TK, KeyNNode] = byKey.copy()
	L2: dict[_TK, KeyNNode] = {}

	def removeSubgraph(nodeKey: _TK):
		destinations = destinationsById[nodeKey]
		for dstKey, _ in destinations:
			if L1.pop(dstKey, None) is not None:
				removeSubgraph(dstKey)
			L2.pop(dstKey, None)

	while L1:
		nodeKey, node = L1.popitem()[1]
		removeSubgraph(nodeKey)
		L2[nodeKey] = (nodeKey, node)

	return list(L2.values())


def _getStartNodes2(allNodes: list[KeyNNode], destinationsById: dict[_TK, list[KeyNNode]]) -> list[KeyNNode]:
	"""
	Kosaraju-Sharir's algorithm for finding the strongly connected components (SCCs) of a directed graph.
	It runs in linear time.
	:param allNodes:
	:param destinationsById:
	:return:
	"""
	sourcesById: dict[_TK, set[_TK]] = defaultdict(set)
	for nodeKey, _ in allNodes:
		outs = destinationsById[nodeKey]
		for dstKey, _ in outs:
			sourcesById[dstKey].add(nodeKey)

	L: list[KeyNNode] = []  # L is reversed!
	visited: set[_TK] = set()
	assigned: set[_TK] = set()
	startNodes: list[KeyNNode] = []

	def visit(nodes: list[KeyNNode]):
		"""
		Visit(u) is the recursive subroutine:
			If u is unvisited then:
				1. Mark u as visited.
				2. For each out-neighbour v of u, if v is unvisited, do Visit(v).
				3. Prepend u to L.
			Otherwise do nothing.
		"""
		for nodeKey, node in (nodes):
			if nodeKey not in visited:
				visited.add(nodeKey)
				visit(destinationsById[nodeKey])
				L.append((nodeKey, node))  # L is reversed!

	def assign(unassignedNodeKeys: set[_TK]):
		"""
		Assign(u,root) is the recursive subroutine:
			If u has not been assigned to a component then:
				1. Assign u as belonging to the component whose root is root.
				2. For each in-neighbour v of u, do Assign(v,root).
			Otherwise do nothing.
		"""
		assigned.update(unassignedNodeKeys)
		for nodeKey in unassignedNodeKeys:
			assign({dstKey for dstKey, _ in destinationsById[nodeKey]}.difference(assigned))
			# assign(sourcesById[nodeKey].difference(assigned))

	# 1. For each vertex u of the graph do Visit(u)
	visit(allNodes)

	# 2. For each element u of L in order, do Assign(u,u)
	for nodeKey, node in reversed(L):
		if nodeKey not in assigned:
			sources = {dstKey for dstKey, _ in destinationsById[nodeKey]}
			# sources = sourcesById[nodeKey]
			unassignedSources = sources.difference(assigned)
			if unassignedSources or not sources:
				startNodes.append((nodeKey, node))
				assigned.add(nodeKey)
				assign(unassignedSources)

	return startNodes


def collectOutgoingEdges(allNodes: Iterable[KeyNNode], getDestinations: DestinationGetter, getId: IdGetter) -> dict[_TK, list[KeyNNode]]:
	allNodeIds = {k for k, _ in allNodes}
	destinationsById: dict[_TK, list[KeyNNode]] = {}
	for srcKey, src in allNodes:
		dests = destinationsById[srcKey] = []
		for dst in getDestinations(src):
			dstKey = getId(dst)
			if getId(dst) in allNodeIds:
				dests.append((dstKey, dst))
	return destinationsById


def collectIncomingEdges(allNodes: Iterable[KeyNNode], getDestinations: DestinationGetter, getId: IdGetter) -> OrderedMultiDict[_TK, KeyNNode]:
	incomingEdges: OrderedMultiDict[_TK, KeyNNode] = OrderedMultiDict()
	for keyNNode in allNodes:
		for dest in getDestinations(keyNNode[1]):
			incomingEdges.add(getId(dest), keyNNode)
	return incomingEdges


def _countIncomingEdges(destinationsById: dict[_TK, list[KeyNNode]]) -> dict[_TK, int]:
	"""
	count all incoming edges
	:param destinationsById:
	:return:
	"""
	incomingCnt: dict[_TK, int] = defaultdict(int)
	for out in destinationsById.values():
		for dstKey, _ in out:
			incomingCnt[dstKey] += 1
	return incomingCnt


def innerSemiTopologicalSort(start: Iterable[KeyNNode], destinationsById: dict[_TK, list[KeyNNode]], incomingCnt: dict[_TK, int], allNodes: list[KeyNNode]) -> list[_TNode]:
	"""
	TopologicalSort that allows circular references.
	:param incomingCnt:
	:param start:
	:param destinationsById:
	:return:
	"""
	byKey: dict[_TK, KeyNNode] = {node[0]: node for node in allNodes}

	L: list[_TNode] = []  # Empty list that will contain the sorted elements
	S: deque[KeyNNode] = deque()  # Set of all nodes with no incoming edge
	S.extend(start)
	seenNodes = {k for k, _ in start}

	mss: dict[_TK, KeyNNode] = {}
	ms: list[KeyNNode] = []
	while S:
		while S:
			srcKey, src = S.pop()
			L.append(src)
			mss.pop(srcKey, None)
			byKey.pop(srcKey, None)

			# for each node m with an edge e from n to m do
			destinations = destinationsById[srcKey]
			dst: _TNode
			for dstKey, dst in destinations:
				if dstKey not in seenNodes:
					# del out[dstKey] not necessary, because we will never look at this again anyway.
					inCnt = incomingCnt[dstKey] = incomingCnt[dstKey] - 1
					# if m has no other incoming edges then
					if inCnt == 0:
						seenNodes.add(dstKey)  # ?? seems a good idea, but it's untested
						S.append((dstKey, dst))
					else:
						ms.append((dstKey, dst))
			if not S:
				seenNodes.update(k for k, _ in ms)
				S.extend(ms)
			else:
				mss.update({node[0]: node for node in ms})
			ms.clear()

		if byKey:
			S.extend(_getStartNodes(list(byKey.values()), destinationsById))
			#S.append(mss.popitem()[1])
		# for key, node in mss.values():
		# 	if cnt > 0 and key not in seenNodes:
		# 		seenNodes.add(key)
		# 		node = byKey[key]
		# 		S.append(node)

	return L


def innerSemiTopologicalSort3(start: Iterable[KeyNNode], destinationsById: dict[_TK, list[KeyNNode]], incomingCnt: dict[_TK, int]) -> list[KeyNNode]:
	"""
	TopologicalSort that allows circular references.
	(same as innerSemiTopologicalSort(..), but also returns the keys.)
	:param incomingCnt:
	:param start:
	:param destinationsById:
	:return:
	"""

	L: list[KeyNNode] = []  # Empty list that will contain the sorted elements
	S: deque[KeyNNode] = deque()  # Set of all nodes with no incoming edge
	S.extend(start)
	seenNodes = {k for k, _ in start}

	ms: list[KeyNNode] = []
	while S:
		srcKey, src = S.pop()
		L.append((srcKey, src))

		# for each node m with an edge e from n to m do
		destinations = destinationsById[srcKey]
		dst: _TNode
		for dstKey, dst in destinations:
			# del out[dstKey] not necessary, because we will never look at this again anyway.
			inCnt = incomingCnt[dstKey] = incomingCnt[dstKey] - 1

			# if m has no other incoming edges then
			if dstKey not in seenNodes:
				if inCnt == 0:
					seenNodes.add(dstKey)  # ?? seems a good idea, but it's untested
					S.append((dstKey, dst))
				else:
					ms.append((dstKey, dst))
		if not S:
			seenNodes.update(k for k, _ in ms)
			S.extend(ms)
		ms.clear()

	return L


def semiTopologicalSort(start: Iterable[_TNode], allNodes: Iterable[_TNode], getDestinations: DestinationGetter, getId: IdGetter) -> list[_TNode]:
	"""
	TopologicalSort that allows circular references.
	:param start:
	:param allNodes:
	:param getDestinations:
	:param getId:
	:return:
	"""
	# start must already be part of allNodes!  allNodes.append(start)
	allNodes2 = [(getId(n), n) for n in allNodes]
	destinationsById = collectOutgoingEdges(allNodes2, getDestinations, getId)
	incomingCnt = _countIncomingEdges(destinationsById)
	start2 = [(getId(n), n) for n in start]
	return innerSemiTopologicalSort(start2, destinationsById, incomingCnt, allNodes2)


def semiTopologicalSort2(allNodes: Iterable[_TNode], getDestinations: DestinationGetter, getId: IdGetter, *, reverse: bool = False) -> list[_TNode]:
	"""
	TopologicalSort that allows circular references.
	:param allNodes:
	:param getDestinations:
	:param getId:
	:return:
	"""
	allNodes2 = [(getId(n), n) for n in allNodes]
	destinationsById = collectOutgoingEdges(allNodes2, getDestinations, getId)

	if reverse:
		sourcesById: dict[_TK, list[KeyNNode]] = defaultdict(list)
		for nodeKey, node in allNodes2:
			destinations = destinationsById[nodeKey]
			for destKey, dest in destinations:
				sourcesById[destKey].append((nodeKey, node))
		destinationsById = sourcesById

	incomingCnt = _countIncomingEdges(destinationsById)
	# find start nodes:
	start = _getStartNodes(allNodes2, destinationsById)  # [nodeKey for nodeKey in allNodes2 if nodeKey[0] not in incomingCnt]
	return innerSemiTopologicalSort(start, destinationsById, incomingCnt, allNodes2)


def collectAllNodes(start: Iterable[_TNode], getDestinations: DestinationGetter, getId: IdGetter) -> list[_TNode]:
	"""
	collects all Nodes of a graph
	:param start:
	:param getDestinations:
	:param getId:
	:return:
	"""
	allNodes = list(start)

	seenNodes = {getId(n) for n in allNodes}
	for src in allNodes:
		destinations = getDestinations(src)

		for dst in destinations:
			dstKey = getId(dst)
			if dstKey not in seenNodes:
				seenNodes.add(dstKey)
				allNodes.append(dst)

	return allNodes


def collectAllNodes2(start: Iterable[KeyNNode], getDestinations: DestinationGetter, getId: IdGetter) -> tuple[list[KeyNNode], dict[_TK, list[KeyNNode]]]:
	"""
	collects all Nodes of a graph
	:param start:
	:param getDestinations:
	:param getId:
	:return:
	"""
	allNodes = list(start)
	destinationsById = {}
	seenNodes = {k for k, _ in allNodes}
	for srcId, src in allNodes:
		destinationsById[srcId] = [(getId(n), n) for n in getDestinations(src)]
		for dstDstKey in destinationsById[srcId]:
			if (dstKey := dstDstKey[0]) not in seenNodes:
				seenNodes.add(dstKey)
				allNodes.append(dstDstKey)

	return allNodes, destinationsById


def collectAllNodes3(start: Iterable[KeyNNode], getDestinations: DestinationGetter2) -> tuple[list[KeyNNode], dict[_TK, list[KeyNNode]]]:
	"""
	collects all Nodes of a graph
	:param start:
	:param getDestinations:
	:return:
	"""
	allNodes: list[KeyNNode] = list(start)
	destinationsById = {}
	seenNodes = {k for k, _ in allNodes}
	for srcKeySrc in allNodes:
		dests = destinationsById[srcKeySrc[0]] = list(getDestinations(srcKeySrc))
		for dstKeyDst in dests:
			if (dstKey := dstKeyDst[0]) not in seenNodes:
				seenNodes.add(dstKey)
				allNodes.append(dstKeyDst)

	return allNodes, destinationsById


def collectAndSemiTopolSortAllNodes(start: Iterable[_TNode], getDestinations: DestinationGetter, getId: IdGetter) -> list[_TNode]:
	"""
	Collects all Nodes of a graph and then sorts them topologically ina way that allows for circular references.
	This is the same as calling fist collectAllNodes() and then semiTopologicalSort(), but faster.
	:param start:
	:param getDestinations:
	:param getId:
	:return:
	"""
	start = [(getId(n), n) for n in start]
	allNodes, destinationsById = collectAllNodes2(start, getDestinations, getId)
	incomingCnt = _countIncomingEdges(destinationsById)
	allNodes = innerSemiTopologicalSort(start, destinationsById, incomingCnt, allNodes)
	return allNodes


def collectAndSemiTopolSortAllNodes3(start: Iterable[KeyNNode], getDestinations: DestinationGetter2) -> list[KeyNNode]:
	"""
	Collects all Nodes of a graph and then sorts them topologically ina way that allows for circular references.
	This is the same as calling fist collectAllNodes() and then semiTopologicalSort(), but faster.
	:param start:
	:param getDestinations:
	:return:
	"""
	allNodes, destinationsById = collectAllNodes3(start, getDestinations)
	incomingCnt = _countIncomingEdges(destinationsById)
	allNodes = innerSemiTopologicalSort3(start, destinationsById, incomingCnt)
	return allNodes


def _run():
	nodes = list('ABCD')
	destinations = {
		'A': list('BD'),
		'B': list('C'),
		'C': list('D'),
		'D': list('B'),
	}
	sortedNodes = semiTopologicalSort(
		'A',
		nodes,
		getDestinations=destinations.get,
		getId=lambda x: x
	)
	print(f"semiTopologicalSort(...) ->     {sortedNodes}")


if __name__ == '__main__':
	_run()

__all__ = [
	'getStronglyConnectedComponents',
	'getCycles',
	'collectOutgoingEdges',
	'collectIncomingEdges',
	'semiTopologicalSort',
	'semiTopologicalSort2',
	'collectAllNodes',
	'collectAllNodes2',
	'collectAndSemiTopolSortAllNodes',
	'collectAndSemiTopolSortAllNodes3',
]
