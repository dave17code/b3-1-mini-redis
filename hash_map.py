"""
해시맵 (Hash Map with Separate Chaining) 구현 모듈.

내장 dict, set, collections를 일절 사용하지 않고,
직접 구현한 해시 함수와 이중 연결 리스트(DoublyLinkedList)를 이용한 체이닝 방식으로 충돌을 해결합니다.
로드 팩터(0.75) 초과 시 버킷 크기를 2배로 확장(Rehash)합니다.
"""

from typing import Any, List, Optional
from doubly_linked_list import DoublyLinkedList


class Entry:
    """해시맵 버킷 체인에 저장될 키-값 엔트리."""

    def __init__(self, key: Any, value: Any):
        self.key: Any = key
        self.value: Any = value


class HashMap:
    """
    체이닝 기반 커스텀 해시맵.
    """

    DEFAULT_INITIAL_CAPACITY = 16
    LOAD_FACTOR_THRESHOLD = 0.75

    def __init__(self, initial_capacity: int = DEFAULT_INITIAL_CAPACITY):
        self._capacity = max(4, initial_capacity)
        # 고정 길이 버킷 배열을 초기화 (각 버킷은 독립된 체이닝용 이중 연결 리스트)
        self._buckets: List[DoublyLinkedList] = [DoublyLinkedList() for _ in range(self._capacity)]
        self._size = 0

    def _hash(self, key: Any) -> int:
        """
        직접 설계한 FNV-1a 기반 해시 함수.
        문자열 바이트의 비트 분포를 고르게 섞어 충돌을 최소화합니다.
        """
        key_str = str(key)
        h = 2166136261  # 32-bit FNV offset basis
        for ch in key_str:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF  # 32-bit FNV prime
        return h

    def _get_bucket_index(self, key: Any) -> int:
        """키의 해시값을 기반으로 버킷 인덱스를 계산합니다."""
        return self._hash(key) % self._capacity

    def size(self) -> int:
        """저장된 전체 키-값 쌍의 개수를 반환합니다."""
        return self._size

    def is_empty(self) -> bool:
        """해시맵이 비어있는지 확인합니다."""
        return self._size == 0

    def put(self, key: Any, value: Any) -> None:
        """
        키-값 쌍을 저장하거나 기존 키의 값을 갱신합니다.
        로드 팩터가 0.75를 초과하면 버킷 용량을 2배로 동적 확장합니다.
        """
        index = self._get_bucket_index(key)
        bucket = self._buckets[index]

        # 1. 이미 존재하는 키인지 체인 순회로 확인 (기존 값 갱신)
        curr = bucket._head.next
        while curr != bucket._tail:
            entry: Entry = curr.data
            if entry.key == key:
                entry.value = value
                return
            curr = curr.next

        # 2. 신규 키 삽입
        bucket.insert_front(Entry(key, value))
        self._size += 1

        # 3. 로드 팩터 초과 여부 확인 후 리사이징
        if self._size / self._capacity > self.LOAD_FACTOR_THRESHOLD:
            self._resize(self._capacity * 2)

    def get(self, key: Any, default: Any = None) -> Any:
        """
        키에 해당하는 값을 조회합니다.
        키가 존재하지 않으면 default 값을 반환합니다.
        """
        index = self._get_bucket_index(key)
        bucket = self._buckets[index]

        curr = bucket._head.next
        while curr != bucket._tail:
            entry: Entry = curr.data
            if entry.key == key:
                return entry.value
            curr = curr.next
        return default

    def remove(self, key: Any) -> bool:
        """
        키에 해당하는 엔트리를 버킷 체인에서 찾아 제거합니다.
        성공 시 True, 키가 없으면 False를 반환합니다.
        """
        index = self._get_bucket_index(key)
        bucket = self._buckets[index]

        curr = bucket._head.next
        while curr != bucket._tail:
            entry: Entry = curr.data
            if entry.key == key:
                bucket.remove_node(curr)
                self._size -= 1
                return True
            curr = curr.next
        return False

    def contains(self, key: Any) -> bool:
        """해당 키가 해시맵에 존재하는지 확인합니다."""
        index = self._get_bucket_index(key)
        bucket = self._buckets[index]

        curr = bucket._head.next
        while curr != bucket._tail:
            entry: Entry = curr.data
            if entry.key == key:
                return True
            curr = curr.next
        return False

    def keys(self) -> List[Any]:
        """해시맵에 저장된 모든 키를 배열로 반환합니다."""
        all_keys = []
        for bucket in self._buckets:
            curr = bucket._head.next
            while curr != bucket._tail:
                all_keys.append(curr.data.key)
                curr = curr.next
        return all_keys

    def values(self) -> List[Any]:
        """해시맵에 저장된 모든 값을 배열로 반환합니다."""
        all_values = []
        for bucket in self._buckets:
            curr = bucket._head.next
            while curr != bucket._tail:
                all_values.append(curr.data.value)
                curr = curr.next
        return all_values

    def _resize(self, new_capacity: int) -> None:
        """
        버킷 크기를 확장하고 기존 엔트리들을 새로운 버킷 위치로 재배치(Rehash)합니다.
        """
        old_buckets = self._buckets
        self._capacity = new_capacity
        self._buckets = [DoublyLinkedList() for _ in range(new_capacity)]
        self._size = 0

        for bucket in old_buckets:
            curr = bucket._head.next
            while curr != bucket._tail:
                entry: Entry = curr.data
                self.put(entry.key, entry.value)
                curr = curr.next
