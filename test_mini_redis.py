"""
Mini Redis 종합 단위 테스트 및 통합 테스트 모듈.
"""

import time
import unittest

from doubly_linked_list import DoublyLinkedList, Node
from hash_map import HashMap
from min_heap import MinHeap
from mini_redis import MiniRedis
from cli import RedisCLI, tokenize_command


class TestDoublyLinkedList(unittest.TestCase):
    def test_insert_and_remove(self):
        dll = DoublyLinkedList()
        self.assertTrue(dll.is_empty())
        self.assertEqual(dll.size(), 0)

        n1 = dll.insert_front("A")
        self.assertEqual(dll.size(), 1)
        self.assertEqual(dll.to_list(), ["A"])

        n2 = dll.insert_front("B")
        self.assertEqual(dll.to_list(), ["B", "A"])

        n3 = dll.insert_back("C")
        self.assertEqual(dll.to_list(), ["B", "A", "C"])

        # move_to_front
        dll.move_to_front(n1)  # A moved to front
        self.assertEqual(dll.to_list(), ["A", "B", "C"])

        dll.move_to_front(n3)  # C moved to front
        self.assertEqual(dll.to_list(), ["C", "A", "B"])

        # remove_node
        removed = dll.remove_node(n1)
        self.assertEqual(removed, "A")
        self.assertEqual(dll.to_list(), ["C", "B"])
        self.assertEqual(dll.size(), 2)

        # remove_front & remove_back
        self.assertEqual(dll.remove_front(), "C")
        self.assertEqual(dll.remove_back(), "B")
        self.assertTrue(dll.is_empty())
        self.assertIsNone(dll.remove_front())
        self.assertIsNone(dll.remove_back())


class TestHashMap(unittest.TestCase):
    def test_basic_operations(self):
        hm = HashMap(initial_capacity=4)
        self.assertEqual(hm.size(), 0)
        self.assertFalse(hm.contains("key1"))

        hm.put("key1", "val1")
        hm.put("key2", "val2")
        self.assertEqual(hm.size(), 2)
        self.assertTrue(hm.contains("key1"))
        self.assertEqual(hm.get("key1"), "val1")
        self.assertEqual(hm.get("key2"), "val2")
        self.assertIsNone(hm.get("key3"))

        # Update existing
        hm.put("key1", "val1_updated")
        self.assertEqual(hm.size(), 2)
        self.assertEqual(hm.get("key1"), "val1_updated")

        # Remove
        self.assertTrue(hm.remove("key1"))
        self.assertFalse(hm.remove("key1"))
        self.assertEqual(hm.size(), 1)
        self.assertFalse(hm.contains("key1"))

    def test_resize_and_collision(self):
        hm = HashMap(initial_capacity=4)
        # Insert more items than threshold to trigger resize
        for i in range(20):
            hm.put(f"k{i}", f"v{i}")

        self.assertEqual(hm.size(), 20)
        for i in range(20):
            self.assertEqual(hm.get(f"k{i}"), f"v{i}")
            self.assertTrue(hm.contains(f"k{i}"))

        keys = hm.keys()
        self.assertEqual(len(keys), 20)


class TestMinHeap(unittest.TestCase):
    def test_heap_ordering(self):
        heap = MinHeap()
        self.assertTrue(heap.is_empty())
        self.assertEqual(heap.size(), 0)

        items = [(10, "c"), (3, "a"), (7, "b"), (1, "x"), (5, "y")]
        for item in items:
            heap.push(item)

        self.assertEqual(heap.size(), 5)
        self.assertEqual(heap.peek(), (1, "x"))

        popped = []
        while not heap.is_empty():
            popped.append(heap.pop())

        expected = [(1, "x"), (3, "a"), (5, "y"), (7, "b"), (10, "c")]
        self.assertEqual(popped, expected)


class TestMiniRedisEngine(unittest.TestCase):
    def test_string_commands(self):
        redis = MiniRedis()
        self.assertEqual(redis.set("user:1", "Alice"), "OK")
        self.assertEqual(redis.get("user:1"), '"Alice"')
        self.assertEqual(redis.exists("user:1"), "(integer) 1")
        self.assertEqual(redis.exists("user:99"), "(integer) 0")
        self.assertEqual(redis.dbsize(), "(integer) 1")

        self.assertEqual(redis.set("user:2", "Bob"), "OK")
        self.assertEqual(redis.dbsize(), "(integer) 2")

        keys_out = redis.keys()
        self.assertIn('"user:1"', keys_out)
        self.assertIn('"user:2"', keys_out)

        self.assertEqual(redis.delete("user:1"), "(integer) 1")
        self.assertEqual(redis.delete("user:1"), "(integer) 0")
        self.assertEqual(redis.get("user:1"), "(nil)")
        self.assertEqual(redis.dbsize(), "(integer) 1")

    def test_memory_and_lru_eviction(self):
        """과제 명세서에 제시된 정확한 예시 시나리오 검증."""
        redis = MiniRedis()
        # CONFIG SET maxmemory 30
        self.assertEqual(redis.config_set_maxmemory(30), "OK")

        # user:1 (6 bytes) + Alice (5 bytes) = 11 bytes
        self.assertEqual(redis.set("user:1", "Alice"), "OK")
        # user:2 (6 bytes) + Bob (3 bytes) = 9 bytes -> Total 20 bytes
        self.assertEqual(redis.set("user:2", "Bob"), "OK")
        # user:3 (6 bytes) + Charlie (7 bytes) = 13 bytes -> Total 33 bytes > 30 bytes
        # LRU인 user:1 (11 bytes) 제거 -> 남은 메모리: 22 bytes
        self.assertEqual(redis.set("user:3", "Charlie"), "OK")

        # user:1은 LRU로 방출되어 없어야 함
        self.assertEqual(redis.get("user:1"), "(nil)")
        self.assertEqual(redis.get("user:2"), '"Bob"')
        self.assertEqual(redis.get("user:3"), '"Charlie"')

        info = redis.info_memory()
        self.assertIn("used_memory:22", info)
        self.assertIn("maxmemory:30", info)
        self.assertIn("evicted_keys:1", info)

        # 단일 엔트리가 maxmemory 초과하는 경우
        oom_res = redis.set("huge_key", "A" * 30)
        self.assertEqual(oom_res, "(error) OOM command not allowed when used_memory > 'maxmemory'")

    def test_lru_access_update(self):
        """GET 호출 시 LRU 순서가 갱신되어 나중에 방출되는지 확인."""
        redis = MiniRedis()
        redis.config_set_maxmemory(30)

        redis.set("k1", "val1")  # 2 + 4 = 6 bytes
        redis.set("k2", "val2")  # 2 + 4 = 6 bytes (Total 12)
        redis.set("k3", "val3")  # 2 + 4 = 6 bytes (Total 18)

        # k1을 GET하여 가장 최신으로 올림 -> LRU 순서는 이제 k2가 가장 오래됨
        redis.get("k1")

        # k4 (15 bytes) 삽입 -> Total 18 + 15 = 33 > 30
        # 가장 오래된 k2 (6 bytes) 방출 -> Total 27 <= 30
        redis.set("k4", "1234567890123")

        self.assertEqual(redis.get("k2"), "(nil)")  # k2가 방출됨
        self.assertEqual(redis.get("k1"), '"val1"')  # k1은 살아있음

    def test_ttl_and_expire(self):
        redis = MiniRedis()
        redis.set("temp", "data")
        self.assertEqual(redis.ttl("temp"), "(integer) -1")  # 만료 시간 없음

        self.assertEqual(redis.expire("temp", 2), "(integer) 1")
        ttl_val = redis.ttl("temp")
        self.assertTrue(ttl_val in ("(integer) 1", "(integer) 2"))

        # 없는 키에 대한 TTL/EXPIRE
        self.assertEqual(redis.expire("no_such_key", 5), "(integer) 0")
        self.assertEqual(redis.ttl("no_such_key"), "(integer) -2")

        # 0 이하 초로 EXPIRE 설정 시 즉시 만료
        redis.set("instant", "val")
        self.assertEqual(redis.expire("instant", 0), "(integer) 1")
        self.assertEqual(redis.get("instant"), "(nil)")

        # 기존 키 덮어쓰기 시 기존 TTL 초기화 검증
        redis.set("persistent", "val")
        redis.expire("persistent", 10)
        self.assertNotEqual(redis.ttl("persistent"), "(integer) -1")
        redis.set("persistent", "new_val")  # 덮어쓰기
        self.assertEqual(redis.ttl("persistent"), "(integer) -1")  # TTL 초기화됨

    def test_empty_state_and_config_update(self):
        redis = MiniRedis()
        self.assertEqual(redis.dbsize(), "(integer) 0")
        self.assertEqual(redis.keys(), "(empty array)")
        self.assertEqual(redis.exists("non_existent"), "(integer) 0")
        self.assertEqual(redis.delete("non_existent"), "(integer) 0")

        # config set maxmemory directly reducing memory below current used_memory
        redis.set("item1", "value1")  # 5 + 6 = 11 bytes
        redis.set("item2", "value2")  # 5 + 6 = 11 bytes (total 22 bytes)
        redis.config_set_maxmemory(15)  # should evict item1
        self.assertEqual(redis.get("item1"), "(nil)")
        self.assertEqual(redis.get("item2"), '"value2"')
        self.assertIn("evicted_keys:1", redis.info_memory())


class TestCLIParser(unittest.TestCase):
    def setUp(self):
        self.cli = RedisCLI()

    def test_tokenizer(self):
        tokens = tokenize_command('SET user:1 "Alice Smith"')
        self.assertEqual(tokens, ["SET", "user:1", "Alice Smith"])

        tokens2 = tokenize_command('CONFIG SET maxmemory 30')
        self.assertEqual(tokens2, ["CONFIG", "SET", "maxmemory", "30"])

    def test_error_outputs(self):
        # 알 수 없는 명령어
        res = self.cli.execute_command("HELLO")
        self.assertEqual(res, "(error) ERR unknown command 'HELLO'")

        # 인자 개수 오류
        res = self.cli.execute_command("GET")
        self.assertEqual(res, "(error) ERR wrong number of arguments for 'GET' command")

        res = self.cli.execute_command("SET user:1")
        self.assertEqual(res, "(error) ERR wrong number of arguments for 'SET' command")

        # 정수 파싱 실패
        res = self.cli.execute_command("CONFIG SET maxmemory abc")
        self.assertEqual(res, "(error) ERR value is not an integer or out of range")

        res = self.cli.execute_command("EXPIRE key abc")
        self.assertEqual(res, "(error) ERR value is not an integer or out of range")


if __name__ == "__main__":
    unittest.main()
