"""
Mini Redis 핵심 엔진 모듈.

메모리 내 Key-Value 데이터베이스 엔진으로,
1. 커스텀 해시맵(HashMap) 기반 Key-Value 저장소
2. 이중 연결 리스트(DoublyLinkedList) 및 해시맵을 결합한 O(1) LRU(Least Recently Used) 추적 및 메모리 초과 시 자동 제거(Eviction)
3. 최소 힙(MinHeap) 및 TTL 맵을 결합한 효율적인 TTL(Time-To-Live) 만료 시간 관리
를 수행합니다.
"""

import math
import time
from typing import List, Optional

from doubly_linked_list import DoublyLinkedList, Node
from hash_map import HashMap
from min_heap import MinHeap


class MiniRedis:
    """Mini Redis 엔진 클래스."""

    def __init__(self):
        # 1. 메인 Key-Value 저장소 (커스텀 해시맵)
        self.db = HashMap()

        # 2. LRU 추적용 자료구조 (Front = 최신 사용, Back = 가장 오래 미사용)
        self.lru_list = DoublyLinkedList()
        # key -> Node 매핑으로 특정 키의 리스트 노드를 O(1)에 탐색
        self.lru_nodes = HashMap()

        # 3. TTL 관리용 자료구조
        self.ttl_map = HashMap()  # key -> 만료 시각(float timestamp)
        self.ttl_heap = MinHeap()  # (expire_at, key) 튜플 저장

        # 4. 메모리 관리 변수
        self.maxmemory = 0  # 0이면 무제한, 양수이면 바이트 단위 제한
        self.used_memory = 0  # 현재 사용 중인 데이터 메모리 (Σ len(utf8(key)) + len(utf8(value)))
        self.evicted_keys = 0  # maxmemory 초과로 LRU 제거된 키의 총 개수

    # =========================================================================
    # 내부 헬퍼 메서드: 만료 처리 및 키 삭제
    # =========================================================================

    def _delete_key_internal(self, key: str) -> bool:
        """
        데이터베이스, LRU 리스트, TTL 맵에서 키를 완전히 삭제하고 메모리를 갱신합니다.
        키가 존재하여 삭제되었으면 True, 없으면 False를 반환합니다.
        """
        if not self.db.contains(key):
            return False

        # 1. 사용 메모리 차감
        val = self.db.get(key)
        if val is not None:
            self.used_memory -= (len(key.encode("utf-8")) + len(str(val).encode("utf-8")))

        # 2. 해시맵에서 제거
        self.db.remove(key)

        # 3. LRU 구조에서 제거
        if self.lru_nodes.contains(key):
            node: Optional[Node] = self.lru_nodes.get(key)
            if node is not None:
                self.lru_list.remove_node(node)
            self.lru_nodes.remove(key)

        # 4. TTL 맵에서 제거
        if self.ttl_map.contains(key):
            self.ttl_map.remove(key)

        return True

    def _is_expired(self, key: str) -> bool:
        """
        키의 만료 여부를 검사(Lazy Expiration)하고 만료 시 즉시 삭제합니다.
        만료되어 삭제되었으면 True를 반환합니다.
        """
        if not self.ttl_map.contains(key):
            return False

        expire_at = self.ttl_map.get(key)
        now = time.time()
        if now >= expire_at:
            self._delete_key_internal(key)
            return True
        return False

    def _purge_expired_heap(self) -> None:
        """
        최소 힙의 루트를 확인하여 만료 시각이 지난 키들을 능동적으로 정리합니다.
        """
        now = time.time()
        while self.ttl_heap.size() > 0:
            exp_at, k = self.ttl_heap.peek()
            if exp_at <= now:
                self.ttl_heap.pop()
                # 힙의 만료 정보가 현재 ttl_map의 최신 만료 정보와 일치하는 경우에만 삭제
                if self.ttl_map.contains(k) and self.ttl_map.get(k) == exp_at:
                    self._delete_key_internal(k)
            else:
                break

    def _purge_all_expired(self) -> None:
        """현재 저장된 모든 만료 키를 전수 검사하여 제거합니다 (DBSIZE, KEYS 전용)."""
        self._purge_expired_heap()
        all_keys = self.db.keys()
        for k in all_keys:
            self._is_expired(k)

    def _evict_if_needed(self) -> None:
        """
        maxmemory 제한이 설정되어 있고 used_memory가 초과한 경우,
        used_memory <= maxmemory가 될 때까지 LRU(가장 오래 사용되지 않은 키)부터 제거합니다.
        """
        if self.maxmemory <= 0:
            return

        while self.used_memory > self.maxmemory and self.lru_list.size() > 0:
            # 이중 연결 리스트의 맨 뒤(가장 오래된 키) 추출
            lru_key = self.lru_list.remove_back()
            if lru_key is None:
                break

            lru_val = self.db.get(lru_key)
            if lru_val is not None:
                self.used_memory -= (len(lru_key.encode("utf-8")) + len(str(lru_val).encode("utf-8")))

            self.db.remove(lru_key)
            self.lru_nodes.remove(lru_key)
            if self.ttl_map.contains(lru_key):
                self.ttl_map.remove(lru_key)

            self.evicted_keys += 1

    # =========================================================================
    # String 타입 기본 명령어
    # =========================================================================

    def set(self, key: str, value: str) -> str:
        """
        SET key value
        - 성공 시 'OK'
        - 단일 엔트리 크기가 maxmemory 초과 시 OOM 에러
        - 기존 키 덮어쓰기 시 기존 TTL 초기화
        - 메모리 초과 시 LRU 제거 수행
        """
        self._purge_expired_heap()
        self._is_expired(key)

        key_bytes = len(key.encode("utf-8"))
        val_bytes = len(value.encode("utf-8"))
        entry_bytes = key_bytes + val_bytes

        # 단일 엔트리 자체가 maxmemory를 초과하는 경우 에러 반환
        if self.maxmemory > 0 and entry_bytes > self.maxmemory:
            return "(error) OOM command not allowed when used_memory > 'maxmemory'"

        if self.db.contains(key):
            # 기존 키 갱신: 기존 메모리 차감 및 새 메모리 추가
            old_val = self.db.get(key)
            old_val_bytes = len(str(old_val).encode("utf-8"))
            self.used_memory += (val_bytes - old_val_bytes)
            self.db.put(key, value)

            # 기존 TTL 초기화(삭제)
            if self.ttl_map.contains(key):
                self.ttl_map.remove(key)

            # LRU 위치를 최신(맨 앞)으로 갱신
            node = self.lru_nodes.get(key)
            if node:
                self.lru_list.move_to_front(node)
        else:
            # 신규 키 추가
            self.db.put(key, value)
            self.used_memory += entry_bytes

            # LRU 맨 앞에 삽입
            node = self.lru_list.insert_front(key)
            self.lru_nodes.put(key, node)

        # 메모리 제한 검사 및 LRU 자동 방출
        self._evict_if_needed()
        return "OK"

    def get(self, key: str) -> str:
        """
        GET key
        - 존재하지 않거나 만료된 경우 '(nil)'
        - 존재하는 경우 '"value"' 반환 및 LRU 갱신
        """
        self._purge_expired_heap()
        if self._is_expired(key) or not self.db.contains(key):
            return "(nil)"

        # LRU 갱신 (맨 앞으로 이동)
        node = self.lru_nodes.get(key)
        if node:
            self.lru_list.move_to_front(node)

        val = self.db.get(key)
        return f'"{val}"'

    def delete(self, key: str) -> str:
        """
        DEL key
        - 삭제 성공 시 '(integer) 1'
        - 키가 없거나 이미 만료된 경우 '(integer) 0'
        """
        self._purge_expired_heap()
        if self._is_expired(key) or not self.db.contains(key):
            return "(integer) 0"

        self._delete_key_internal(key)
        return "(integer) 1"

    def exists(self, key: str) -> str:
        """
        EXISTS key
        - 존재하면 '(integer) 1', 없으면 '(integer) 0'
        """
        self._purge_expired_heap()
        if self._is_expired(key) or not self.db.contains(key):
            return "(integer) 0"
        return "(integer) 1"

    def dbsize(self) -> str:
        """
        DBSIZE
        - 현재 저장된 유효 키 개수를 '(integer) N' 형태로 반환
        """
        self._purge_all_expired()
        return f"(integer) {self.db.size()}"

    def keys(self) -> str:
        """
        KEYS
        - 전체 키 목록을 배열 형식으로 출력
        """
        self._purge_all_expired()
        all_keys = self.db.keys()
        if len(all_keys) == 0:
            return "(empty array)"

        lines = []
        for idx, k in enumerate(all_keys, 1):
            lines.append(f'{idx}. "{k}"')
        return "\n".join(lines)

    # =========================================================================
    # 메모리 관리 명령어
    # =========================================================================

    def config_set_maxmemory(self, bytes_val: int) -> str:
        """
        CONFIG SET maxmemory <bytes>
        - bytes >= 0
        - 0은 무제한
        """
        if bytes_val < 0:
            return "(error) ERR value is not an integer or out of range"

        self.maxmemory = bytes_val
        self._evict_if_needed()
        return "OK"

    def info_memory(self) -> str:
        """
        INFO memory
        - used_memory, maxmemory, evicted_keys 출력
        """
        return f"used_memory:{self.used_memory}\nmaxmemory:{self.maxmemory}\nevicted_keys:{self.evicted_keys}"

    # =========================================================================
    # TTL 관리 명령어
    # =========================================================================

    def expire(self, key: str, seconds: int) -> str:
        """
        EXPIRE key seconds
        - key가 없으면 '(integer) 0'
        - seconds <= 0 이면 즉시 삭제 후 '(integer) 1'
        - 정상 설정 시 '(integer) 1'
        """
        self._purge_expired_heap()
        if self._is_expired(key) or not self.db.contains(key):
            return "(integer) 0"

        if seconds <= 0:
            # 0 이하 초는 즉시 만료 처리
            self._delete_key_internal(key)
            return "(integer) 1"

        expire_at = time.time() + seconds
        self.ttl_map.put(key, expire_at)
        self.ttl_heap.push((expire_at, key))
        return "(integer) 1"

    def ttl(self, key: str) -> str:
        """
        TTL key
        - 키가 없거나 만료된 경우 '(integer) -2'
        - 키는 존재하지만 만료 시간이 없는 경우 '(integer) -1'
        - 만료 시간이 설정된 경우 남은 초 '(integer) N'
        """
        self._purge_expired_heap()
        if self._is_expired(key) or not self.db.contains(key):
            return "(integer) -2"

        if not self.ttl_map.contains(key):
            return "(integer) -1"

        expire_at = self.ttl_map.get(key)
        remaining = int(math.ceil(expire_at - time.time()))

        if remaining <= 0:
            self._delete_key_internal(key)
            return "(integer) -2"

        return f"(integer) {remaining}"
