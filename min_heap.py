"""
최소 힙 (Min Heap) 구현 모듈.

내장 heapq 라이브러리를 사용하지 않고 직접 완전 이진 트리 구조의 힙을 구현합니다.
_heapify_up 및 _heapify_down 연산을 통해 O(log N)으로 요소를 삽입 및 최소값 추출(Pop)합니다.
TTL(만료 시간) 관리를 위해 (expire_at, key) 형태의 데이터를 효율적으로 정렬 및 조회합니다.
"""

from typing import Any, List, Optional


class MinHeap:
    """배열 기반 최소 힙 자료구조."""

    def __init__(self):
        # 힙 요소를 저장할 기본 배열
        self._heap: List[Any] = []

    def size(self) -> int:
        """힙에 저장된 원소 개수를 반환합니다."""
        return len(self._heap)

    def is_empty(self) -> bool:
        """힙이 비어있는지 확인합니다."""
        return len(self._heap) == 0

    def push(self, item: Any) -> None:
        """
        새로운 요소를 힙에 삽입하고, 상향 힙화(_heapify_up)를 통해 힙 속성을 유지합니다.
        시간 복잡도: O(log N)
        """
        self._heap.append(item)
        self._heapify_up(len(self._heap) - 1)

    def pop(self) -> Optional[Any]:
        """
        가장 작은 요소(루트 노드)를 추출 및 제거하고, 하향 힙화(_heapify_down)를 수행합니다.
        시간 복잡도: O(log N)
        """
        if self.is_empty():
            return None
        if len(self._heap) == 1:
            return self._heap.pop()

        root = self._heap[0]
        # 맨 마지막 노드를 루트로 이동 후 하향 힙화
        self._heap[0] = self._heap.pop()
        self._heapify_down(0)
        return root

    def peek(self) -> Optional[Any]:
        """
        가장 작은 요소(루트 노드)를 제거하지 않고 조회합니다.
        시간 복잡도: O(1)
        """
        if self.is_empty():
            return None
        return self._heap[0]

    def _heapify_up(self, index: int) -> None:
        """
        새로 삽입된 노드를 부모와 비교하며 올바른 위치로 올립니다.
        """
        while index > 0:
            parent_idx = (index - 1) // 2
            # 자식 노드가 부모 노드보다 작으면 위치 교환
            if self._heap[index] < self._heap[parent_idx]:
                self._heap[index], self._heap[parent_idx] = self._heap[parent_idx], self._heap[index]
                index = parent_idx
            else:
                break

    def _heapify_down(self, index: int) -> None:
        """
        루트로 이동된 노드를 자식들과 비교하며 더 작은 자식과 위치를 바꿉니다.
        """
        heap_len = len(self._heap)
        while True:
            left_child_idx = 2 * index + 1
            right_child_idx = 2 * index + 2
            smallest = index

            # 왼쪽 자식 노드와 비교
            if left_child_idx < heap_len and self._heap[left_child_idx] < self._heap[smallest]:
                smallest = left_child_idx

            # 오른쪽 자식 노드와 비교
            if right_child_idx < heap_len and self._heap[right_child_idx] < self._heap[smallest]:
                smallest = right_child_idx

            # 더 작은 자식이 발견되면 스왑하고 계속 하향
            if smallest != index:
                self._heap[index], self._heap[smallest] = self._heap[smallest], self._heap[index]
                index = smallest
            else:
                break
