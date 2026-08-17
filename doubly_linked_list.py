"""
이중 연결 리스트 (Doubly Linked List) 구현 모듈.

내장 컬렉션(deque, list의 삽입/삭제 메서드 등)을 사용하지 않고
노드 간 prev, next 포인터를 직접 조작하여 O(1) 시간 복잡도로 노드를 삽입, 삭제, 이동합니다.
"""

from typing import Any, Optional


class Node:
    """이중 연결 리스트의 노드 클래스."""

    def __init__(self, data: Any = None):
        self.data: Any = data
        self.prev: Optional["Node"] = None
        self.next: Optional["Node"] = None


class DoublyLinkedList:
    """
    더미 헤드(dummy head)와 더미 테일(dummy tail)을 활용한 이중 연결 리스트.
    모든 삽입, 삭제, 이동 연산을 O(1)에 수행합니다.
    """

    def __init__(self):
        # 경계 조건 처리를 단순화하기 위한 더미 노드 설정
        self._head = Node()
        self._tail = Node()
        self._head.next = self._tail
        self._tail.prev = self._head
        self._size = 0

    def is_empty(self) -> bool:
        """리스트가 비어있는지 확인합니다."""
        return self._size == 0

    def size(self) -> int:
        """리스트에 포함된 노드 수를 반환합니다."""
        return self._size

    def insert_front(self, data: Any) -> Node:
        """
        리스트 맨 앞(더미 헤드 바로 뒤)에 새 노드를 O(1)으로 삽입합니다.
        LRU 캐시에서 최근 참조된 데이터를 맨 앞으로 보낼 때 사용됩니다.
        """
        node = Node(data)
        self._insert_after(self._head, node)
        return node

    def insert_back(self, data: Any) -> Node:
        """
        리스트 맨 뒤(더미 테일 바로 앞)에 새 노드를 O(1)으로 삽입합니다.
        """
        node = Node(data)
        self._insert_after(self._tail.prev, node)
        return node

    def remove_front(self) -> Optional[Any]:
        """
        리스트 맨 앞의 노드를 O(1)으로 제거하고 데이터를 반환합니다.
        """
        if self.is_empty():
            return None
        first_node = self._head.next
        return self.remove_node(first_node)

    def remove_back(self) -> Optional[Any]:
        """
        리스트 맨 뒤(가장 오래된 노드)를 O(1)으로 제거하고 데이터를 반환합니다.
        LRU 메모리 초과 시 가장 오래된 키를 제거(Eviction)할 때 사용됩니다.
        """
        if self.is_empty():
            return None
        last_node = self._tail.prev
        return self.remove_node(last_node)

    def remove_node(self, node: Node) -> Any:
        """
        특정 노드를 O(1)으로 리스트에서 제거합니다.
        """
        if node is None or node.prev is None or node.next is None:
            return None
        
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

        node.prev = None
        node.next = None
        self._size -= 1
        return node.data

    def move_to_front(self, node: Node) -> None:
        """
        기존에 존재하는 노드를 O(1)으로 맨 앞(더미 헤드 바로 뒤)으로 이동시킵니다.
        LRU 캐시 갱신 시 노드 재생성 없이 포인터 조작만으로 처리합니다.
        """
        if node is None or node == self._head.next:
            return

        # 1. 현재 위치에서 분리
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

        # 2. 헤드 바로 뒤에 삽입
        first_node = self._head.next
        self._head.next = node
        node.prev = self._head
        node.next = first_node
        first_node.prev = node

    def _insert_after(self, prev_node: Node, new_node: Node) -> None:
        """내부 헬퍼: 지정한 노드 바로 뒤에 새 노드를 연결합니다."""
        next_node = prev_node.next
        prev_node.next = new_node
        new_node.prev = prev_node
        new_node.next = next_node
        next_node.prev = new_node
        self._size += 1

    def to_list(self) -> list:
        """디버깅 및 순회를 위해 노드 데이터 목록을 기본 배열로 반환합니다."""
        result = []
        curr = self._head.next
        while curr != self._tail:
            result.append(curr.data)
            curr = curr.next
        return result
