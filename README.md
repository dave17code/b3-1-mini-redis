# ⚡ Mini Redis (B3-1 Mission)

> **Python 내장 컬렉션(`dict`, `set`, `collections`, `heapq` 등)을 전혀 사용하지 않고, 밑바닥(Scratch)부터 직접 구현한 기초 자료구조들을 결합하여 구축한 CLI 기반 In-Memory Key-Value 데이터 스토리지입니다.**

---

## 📖 1. 프로젝트 개요 (Overview)

### 🎯 미션 목표
본 프로젝트는 Redis의 핵심 메커니즘인 **String Key-Value 데이터 입출력**, **LRU(Least Recently Used) 기반 메모리 방출(Eviction)**, 그리고 **TTL(Time-To-Live) 기반 만료 처리**를 고수준 라이브러리의 도움 없이 순수 자료구조 간의 유기적 결합으로 재현하는 것을 목표로 합니다.

### 🔑 핵심 특징
1. **No Built-in Collections**: 파이썬의 `dict`, `set`, `heapq`, `deque` 등의 내장 모듈을 배제하고 `DoublyLinkedList`, `HashMap`, `MinHeap`을 직접 구현.
2. **O(1) LRU Cache Tracking**: 이중 연결 리스트와 해시맵 노드 인덱싱을 결합하여 데이터 접근 및 순서 갱신을 $O(1)$에 수행.
3. **Dual Expiration Strategy (Lazy + Active TTL)**: 
   - **Lazy Expiration**: 데이터 접근 시점에 만료 여부 확인 후 삭제.
   - **Active Expiration**: 커스텀 최소 힙(Min-Heap)의 루트 노드를 활용하여 가장 임박한 만료 키를 선제적으로 제거.
4. **Dynamic Resizing Hash Map**: FNV-1a 해시 알고리즘과 개별 체이닝(Separate Chaining)을 적용하고, 로드 팩터(0.75) 초과 시 2배 동적 확장(Rehash).
5. **Redis CLI REPL 지원**: 공백 및 따옴표(`"`, `'`), 이스케이프 문자를 정밀하게 파싱하는 토크나이저와 표준 Redis 응답 포맷 지원.

---

## 🏗️ 2. 프로그램 전체 설계도 (Architecture)

### 📐 컴포넌트 아키텍처 다이어그램

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLI / REPL Layer (cli.py)                       │
│      - 사용자 입력 파싱 (tokenize_command) & 따옴표/이스케이프 처리               │
│      - Redis 표준 응답 포맷팅 (OK, (nil), (integer) N, (error) ERR)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Command Routing
┌───────────────────────────────────▼────────────────────────────────────┐
│                    Mini Redis Core Engine (mini_redis.py)              │
│                                                                        │
│  ┌───────────────────────┐ ┌───────────────────┐ ┌──────────────────┐  │
│  │   Key-Value Storage   │ │    LRU Tracking   │ │   TTL Management │  │
│  │       (HashMap)       │ │  (List + HashMap) │ │  (Heap + HashMap)│  │
│  │                       │ │                   │ │                  │  │
│  │  - 메인 데이터 저장       │ │  - DoublyLinked   │ │  - MinHeap       │   │
│  │  - key -> value       │ │    List (순서)     │ │    (expire_at)   │   │
│  │                       │ │  - HashMap        │ │  - HashMap       │  │
│  │                       │ │    (key -> Node)  │ │    (key -> time) │  │
│  └───────────────────────┘ └───────────────────┘ └──────────────────┘  │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                       Memory Manager                             │  │
│  │  - used_memory = Σ (len(utf8(k)) + len(utf8(v)))                 │  │
│  │  - maxmemory 초과 시 LRU Tail 노드 자동 Eviction 방출                 │   │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                    │ Data Structures
┌───────────────────────────────────▼────────────────────────────────────┐
│                    Custom Data Structures Layer                        │
│                                                                        │
│  ┌────────────────────────┐ ┌──────────────────┐ ┌──────────────────┐  │
│  │   doubly_linked_list   │ │     hash_map     │ │     min_heap     │  │
│  │  - Dummy Head & Tail   │ │  - FNV-1a Hash   │ │  - Binary Tree   │  │
│  │  - O(1) Node Insertion │ │  - DLL Chaining  │ │    Array Index   │  │
│  │  - O(1) Node Removal   │ │  - Dynamic 2x    │ │  - Sift-up/down  │  │
│  │  - O(1) Move to Front  │ │    Rehashing     │ │  - O(1) Peek     │  │
│  └────────────────────────┘ └──────────────────┘ └──────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### 📁 모듈별 역할 및 파일 구조

| 파일명 | 역할 및 주요 책임 |
| :--- | :--- |
| `doubly_linked_list.py` | 더미 헤드/테일을 가진 이중 연결 리스트. $O(1)$ 노드 삽입, 삭제 및 `move_to_front` 연산 제공. |
| `hash_map.py` | FNV-1a 해시 함수와 이중 연결 리스트 체이닝으로 구현된 해시맵. 로드 팩터 0.75 초과 시 2배 리사이징. |
| `min_heap.py` | 배열 기반 완전 이진 트리 최소 힙. 만료 시간 기준 `(expire_at, key)` 우선순위 큐 관리 ($O(\log N)$). |
| `mini_redis.py` | Mini Redis 핵심 엔진. String CRUD, LRU 캐시 교체 정책, 지연/능동 TTL 만료 및 메모리 추적 총괄. |
| `cli.py` | 토크나이저, 명령어 유효성 검증, 에러 핸들링 및 대화형 REPL 환경 제공. |
| `main.py` | 프로그램 진입점(Entrypoint). |
| `test_mini_redis.py` | 자료구조 단위 테스트 및 메모리 방출, 만료 시나리오 통합 검증 테스트 스위트. |

---

## 🔄 3. 기능별 작동 흐름 (Detailed Workflows)

### 1) String 데이터 처리 흐름 (`SET`, `GET`, `DEL`)

```
[SET key value]
 1. Active 만료 검사: MinHeap 루트를 확인하여 지난 만료 키 선제 제거
 2. Lazy 만료 검사: 해당 key가 만료 대상인지 확인 후 만료 시 삭제
 3. 메모리 검증: (key + value) 바이트 크기 > maxmemory 인 경우 즉시 OOM 에러 반환
 4. 데이터 저장/갱신:
    - 신규 키: HashMap에 등록, used_memory 증가, LRU 리스트 Head에 노드 삽입 후 lru_nodes에 매핑
    - 기존 키: 값 변경 및 메모리 차이 반영, 기존 TTL 초기화, LRU 노드를 리스트 맨 앞으로 이동
 5. Eviction 체크: used_memory > maxmemory인 경우 LRU 정책에 따라 공간 확보

[GET key]
 1. Active 만료 검사 수행
 2. Lazy 만료 검사: 키의 TTL이 초과되었으면 즉시 삭제하고 '(nil)' 반환
 3. 키가 존재하면 lru_list.move_to_front(node)로 LRU 순위를 최신화(O(1))한 후 '"value"' 반환

[DEL key]
 1. HashMap(db), LRU(list & map), TTL(map)에서 키를 모두 제거
 2. used_memory에서 해당 키/값의 UTF-8 바이트 크기 차감 후 '(integer) 1' 반환
```

---

### 2) 메모리 관리 및 LRU Eviction 흐름 (`CONFIG SET maxmemory`, `INFO memory`)

- **메모리 계산 방식**: `used_memory = Σ (len(utf-8(key)) + len(utf-8(value)))`
- **방출 메커니즘**:

```
           [새 데이터 삽입 또는 maxmemory 축소 설정]
                               │
                               ▼
               ┌───────────────────────────────┐
               │ used_memory > maxmemory ?     │
               └───────────────┬───────────────┘
                               │ YES
                               ▼
        ┌─────────────────────────────────────────────┐
        │  lru_list.remove_back()                     │  <-- 가장 오래 접근되지 않은
        │  (LRU Tail 노드 추출)                        │      키를 O(1)에 획득
        └──────────────────────┬──────────────────────┘
                               │
                               ▼
        ┌─────────────────────────────────────────────┐
        │  1. db, lru_nodes, ttl_map 에서 제거        │
        │  2. used_memory -= (key_len + val_len)      │
        │  3. evicted_keys += 1                       │
        └──────────────────────┬──────────────────────┘
                               │
                               ▼
                 [조건 충족될 때까지 루프 반복]
```

---

### 3) TTL 만료 메커니즘 흐름 (`EXPIRE`, `TTL`)

Mini Redis는 **지연 만료(Lazy)**와 **능동 만료(Active)**를 함께 사용하여 메모리 효율과 응답성을 동시에 달성합니다.

1. **`EXPIRE <key> <seconds>`**:
   - 만료 시각 계산: `expire_at = current_timestamp + seconds`
   - `ttl_map`에 `(key -> expire_at)` 저장 및 `ttl_heap`에 `(expire_at, key)` Push ($O(\log N)$).
   - `seconds <= 0`인 경우 즉시 키를 삭제 처리.
2. **`TTL <key>`**:
   - 키가 없거나 이미 만료된 경우: `(integer) -2`
   - 키는 존재하나 만료 시간이 없는 경우: `(integer) -1`
   - 만료 시간이 설정된 경우: 올림(`ceil`) 계산된 남은 초 `(integer) N` 반환.
3. **만료 검사 전략**:
   - **Lazy Expiration**: 명령어가 들어올 때마다 타겟 키의 만료 시각과 현재 시각을 비교하여 삭제.
   - **Active Purge**: 모든 주요 작업 시작 시 최소 힙의 Root(`peek()`)를 확인하여 현재 시간보다 과거인 엔트리를 Pop하여 일괄 정리.

---

## ⏱️ 4. 자료구조 및 시간 복잡도

| 연산 | 주요 자료구조 | 시간 복잡도 | 설명 |
| :--- | :--- | :---: | :--- |
| **GET / EXISTS** | `HashMap` + `DoublyLinkedList` | **$O(1)$** | 해시 조회 및 노드 Head 이동 |
| **SET** | `HashMap` + `DoublyLinkedList` | **$O(1)$** amortized | 해시 삽입, LRU Head 삽입, 필요시 리사이징 |
| **DEL** | `HashMap` + `DoublyLinkedList` | **$O(1)$** | 해시 버킷 삭제 및 노드 포인터 단선 |
| **LRU Eviction** | `DoublyLinkedList` + `HashMap` | **$O(1)$** | Tail 노드 분리 및 해시 제거 |
| **EXPIRE** | `MinHeap` + `HashMap` | **$O(\log N)$** | 최소 힙 Push 및 TTL 맵 갱신 |
| **TTL** | `HashMap` | **$O(1)$** | TTL 맵 조회 및 타임스탬프 계산 |
| **Active Purge** | `MinHeap` | **$O(K \log N)$** | 만료된 $K$개 항목 추출 |
| **KEYS / DBSIZE**| `HashMap` | **$O(N)$** | 전체 버킷 순회 및 유효 키 추출 |

---

## 💻 5. 지원 명령어 명세 (Command Reference)

### String 명령어
```bash
SET <key> <value>     # 키에 값을 저장 (문자열 내 공백은 따옴표로 감싸서 입력)
GET <key>             # 키의 값을 조회 (존재하지 않거나 만료 시 (nil))
DEL <key>             # 키 삭제 (성공: 1, 실패: 0)
EXISTS <key>          # 키 존재 여부 확인 (존재: 1, 미존재: 0)
DBSIZE                # 저장된 유효 키의 총 개수 반환
KEYS                  # 저장된 모든 키 목록 출력
```

### 메모리 관리 명령어
```bash
CONFIG SET maxmemory <bytes>  # 최대 메모리 제한 설정 (0 = 무제한)
INFO memory                   # used_memory, maxmemory, evicted_keys 통계 조회
```

### TTL 관리 명령어
```bash
EXPIRE <key> <seconds>        # 키의 유효 시간(초) 설정
TTL <key>                     # 남은 만료 시간(초) 조회
```

---

## 🚀 6. 실행 및 테스트 방법

### 1) CLI REPL 실행
```bash
python3 main.py
```
**실행 예시:**
```text
Mini Redis CLI Interface (Type 'exit' or 'quit' to close)
mini-redis> CONFIG SET maxmemory 30
OK
mini-redis> SET user:1 "Alice"
OK
mini-redis> SET user:2 "Bob"
OK
mini-redis> SET user:3 "Charlie"
OK
mini-redis> GET user:1
(nil)
mini-redis> INFO memory
used_memory:22
maxmemory:30
evicted_keys:1
mini-redis> EXPIRE user:2 10
(integer) 1
mini-redis> TTL user:2
(integer) 10
mini-redis> exit
BYE
```

### 2) 단위 및 통합 테스트 실행
```bash
python3 test_mini_redis.py
```
```text
......
----------------------------------------------------------------------
Ran 6 tests in 0.012s

OK
```
