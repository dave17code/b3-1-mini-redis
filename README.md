# 🗄️ MiniRedis B3-1

MiniRedis의 **3대 핵심 알고리즘**인 기본 CRUD, TTL 만료 정책, LRU 메모리 축출을 구현하고 이를 CLI 환경에서 검증하는 프로젝트입니다.

---

# 📦 PART 1. MiniRedis 내부 5대 데이터 보관 구조

> 🧠 **MiniRedis 런타임 인메모리 관리 체계**
>
> * 📚 *$\color{red}{\textsf{3대 자료구조 저장소:}}$* `HashMap` (검색) · `DoublyLinkedList` (LRU) · `MinHeap` (만료)
> * 📊 **$\color{red}{\textsf{2대 메모리 관리 변수:}}$** `used_memory` (사용량) · `maxmemory` (한도)

### 1. 🗺️ `self.hash_map` (HashMap)

- **저장 실체:** 고정 크기 1차원 리스트 `self.buckets = [None] * capacity` 📦

- **내부 데이터 규격:** `HashItem(key: str, value_node: Node_Address, next: HashItem | None)`

```text
self.hash_map.buckets
┌───────┬────────────────────────────────────────────────────────────────────────┐
│ Index │ 실제 저장된 데이터 형태 (체이닝 단방향 연결)                           │
├───────┼────────────────────────────────────────────────────────────────────────┤
│  [0]  │ None                                                                   │
│  [1]  │ HashItem(key="user:1", value_node=0x01, next=None)                     │
│  [2]  │ None                                                                   │
│  [3]  │ HashItem(key="session", value_node=0x02, next=HashItem(key="auth", ...))│
└───────┴────────────────────────────────────────────────────────────────────────┘
```

- **핵심 역할:** 키 문자열을 다항 롤링 해시 연산하여 **`DoublyLinkedList`에 있는 실제 노드 메모리 주소(`0x01`)를 $O(1)$로 즉시 반환** ⚡

---

### 2. 🔗 `self.lru_list` (DoublyLinkedList)

- **저장 실체:** 더미 `Head`와 `Tail` 사이에 연결된 **양방향 포인터 노드 체인** ⛓️

- **내부 데이터 규격:** `Node(prev: Node, next: Node, data: Entry(key, value, expire_at))`

```text
                      [ self.head ] (더미 헤드)
                            ▲
                            ▼
      ┌─────────────► [ Node @0x01 ] (MRU: 가장 최근에 사용됨)
      │  • prev: self.head  /  next: 0x02
      │  • data: Entry(key="user:1", value="Dave", expire_at=None)
      │                     ▲
      │                     ▼
      │               [ Node @0x02 ] (LRU: 가장 오래됨 / 축출 1순위)
      │  • prev: 0x01       /  next: self.tail
      │  • data: Entry(key="session", value="abc", expire_at=172345678.0)
      │                     ▲
      │                     ▼
      └─────────────── [ self.tail ] (더미 테일)
```

- **핵심 역할:** 최근 사용된 노드는 Head 바로 뒤(MRU)로 승격시키고, 용량 초과 시 **Tail 바로 앞(LRU) 노드를 $O(1)$로 축출(Eviction)** 🚪

---

### 3. ⏱️ `self.min_heap` (MinHeap)

- **저장 실체:** 파이썬 1차원 동적 리스트 `self.heap = []` 🌲

- **내부 데이터 규격:** `(expire_at: float, key: str)` 형태의 **2-튜플**

```text
self.min_heap.heap = [ (172345678.0, "session"), (172345999.0, "temp:k") ]

[배열 및 완전 이진 트리 구조]
              Index 0: (172345678.0, "session")   <-- Root (가장 먼저 만료될 항목)
                    ┌─────────┴─────────┐
      Index 1: (172345999.0, "temp:k")  Index 2: ...
```

- **핵심 역할:** 만료 시각이 설정된 키들만 모아 **루트(`heap[0]`)에 가장 수명이 짧은 키를 $O(1)$로 대기**시켜 신속하게 만료 청소 ⏳

---

### 4. 🔢 `self.used_memory` (현재 사용량 변수)

- **저장 실체:** 파이썬 기본 정수형 (`int`)

- **내부 데이터:** 현재 저장된 모든 키와 값의 **순수 UTF-8 바이트 누적 합산값** (예: `150` Bytes) 📈

- **핵심 역할:** `SET`, `DEL`, 만료, 축출 시 실시간으로 바이트를 증감 관리

---

### 5. 🛑 `self.maxmemory` (용량 한도 변수)

- **저장 실체:** 파이썬 기본 정수형 (`int`)

- **내부 데이터:** 인메모리 캐시의 **최대 허용 바이트 한도** (예: `1000` Bytes, `0`이면 무제한) 🚨

- **핵심 역할:** `used_memory > maxmemory`가 되는 순간 **LRU 축출 루프를 작동시키는 기준선**

---

# 🚀 PART 2. B3-1 미션 필수 명령어 동작 설명

### 1. 💾 `SET key value`

새로운 키-값을 캐시에 저장하거나 기존 키의 값을 갱신합니다. (인자 2개 고정)

- **실행 과정:**

  1. **만료 청소:** 힙을 확인하여 수명이 다한 키를 먼저 제거합니다.
  2. **기존 데이터 덮어쓰기:** 해시맵에 이미 존재하는 키라면 이전 노드를 리스트와 메모리에서 완전히 회수합니다.
  3. **노드 생성 및 배치:** 새 `Entry`와 `Node`를 생성해 `self.lru_list`의 맨 앞(Head/MRU)에 넣고, `self.hash_map` 버킷에 등록합니다.
  4. **LRU 축출:** 메모리 사용량이 `maxmemory`를 넘어서면 `self.lru_list.remove_tail()`로 가장 오래된 노드를 연속으로 잘라냅니다.

- **반환값:** `"OK"`

### 2. 🔍 `GET key`

키에 매핑된 값을 조회하고 최근 사용 상태로 승격시킵니다. (인자 1개 고정)

- **실행 과정:**

  1. **$O(1)$ 탐색:** `self.hash_map.get(key)`로 노드의 메모리 주소를 즉시 가져옵니다.
  2. **지연 만료 검증 (Lazy Expiration):** 노드에 설정된 만료 시각이 현재 시각보다 과거라면 즉시 삭제하고 `None`을 반환합니다.
  3. **MRU 승격:** 정상 데이터라면 `self.lru_list.move_to_front(node)`를 호출해 연결 리스트 맨 앞으로 옮겨 수명을 연장합니다.

- **반환값:** 문자열 값 (`"Dave"`) 또는 없으면 `(nil)`

### 3. 🗑️ `DEL key`

전달된 단일 키를 캐시에서 완전히 제거합니다. (인자 1개 고정)

- **실행 과정:**

  1. 전달받은 키를 `self.hash_map`에서 조회합니다.
  2. 존재하는 노드는 `self.lru_list.remove_node(node)`로 포인터를 끊고, `self.hash_map.delete(key)`로 버킷에서 분리합니다.
  3. 해제된 키와 값의 바이트만큼 `self.used_memory`를 차감합니다.

- **반환값:** 삭제 성공 시 `1`, 키가 없으면 `0`

### 4. ❓ `EXISTS key`

전달된 단일 키가 캐시에 유효하게 존재하는지 확인합니다. (인자 1개 고정)

- **실행 과정:**

  1. 키를 조회하여 존재 여부를 확인합니다.
  2. 존재하는 키라도 만료 시각이 지났다면 즉시 정리하고 카운트에서 제외합니다.

- **반환값:** 현재 유효하게 존재하면 `1`, 없으면 `0`

### 5. ⏳ `EXPIRE key seconds`

이미 존재하는 키에 유효 수명(TTL)을 초 단위로 부여합니다. (인자 2개 고정)

- **실행 과정:**

  1. `self.hash_map.get(key)`로 노드를 찾습니다 (없으면 `0` 반환).
  2. 노드의 `expire_at` 필드에 `현재시간 + seconds`를 기록합니다.
  3. `self.min_heap.push(expire_at, key)`로 만료 스케줄러에 등록합니다.

- **반환값:** 성공 시 `1`, 키가 없으면 `0`

### 6. ⏱️ `TTL key`

키의 남은 유효 시간을 초 단위로 조회합니다. (인자 1개 고정)

- **실행 과정:**

  1. 키가 존재하지 않거나 이미 만료된 경우: `-2` 반환
  2. 키는 존재하지만 만료 시간이 설정되지 않은 영구 데이터인 경우: `-1` 반환
  3. 만료 시간이 남아있는 경우: `int(expire_at - 현재시간)` 계산 후 반환

- **반환값:** 남은 초 정수, `-1`, 또는 `-2`

### 7. 📋 `KEYS`

캐시에 등록된 모든 유효한 키 목록을 조회합니다. (인자 없이 단독 실행)

- **실행 과정:**

  - `self.hash_map.buckets` 전체를 순회하며 체이닝된 노드들의 키를 모읍니다. (만료된 노드는 자동 필터링 및 청소)

- **반환값:** 키 문자열들의 배열

### 8. 🔢 `DBSIZE`

현재 캐시에 저장된 유효 데이터의 총 개수를 반환합니다. (인자 없이 단독 실행)

- **실행 과정:**

  - 만료되지 않은 실제 유효 키 목록의 길이를 계산하여 반환합니다.

- **반환값:** 키 총 개수 정수

### 9. ⚙️ `CONFIG SET maxmemory <bytes>`

실행 중인 서버의 최대 메모리 한도를 동적으로 설정하고, 한도가 줄어들었을 경우 즉시 초과분을 축출합니다.

- **실행 과정:**

  1. 전달받은 바이트 정수 값으로 `self.maxmemory` 한도를 즉시 갱신합니다.
  2. 새로 설정된 한도가 현재 사용량(`self.used_memory`)보다 작을 경우, 한도를 만족할 때까지 `self.lru_list.remove_tail()`을 반복 호출하여 가장 오래된 데이터를 즉시 축출하고 메모리를 회수합니다.
  3. 축출된 노드의 개수를 누적 카운터(`self.evicted_keys`)에 반영합니다.

- **반환값:** `"OK"`

### 10. 📊 `INFO memory`

현재 캐시 서버의 메모리 사용량, 설정 한도, 누적 축출 통계를 표준 포맷으로 확인합니다. (인자 없이 단독 실행)

- **실행 과정:**

  1. 만료된 키들을 선제 정리한 후 현재 메모리 상태를 확인합니다.
  2. 현재 사용 바이트(`used_memory`), 최대 한도(`maxmemory`), 지금까지 LRU로 제거된 누적 키 개수(`evicted_keys`)를 줄바꿈 포맷으로 조합하여 반환합니다.

- **반환값:** `# Memory\r\nused_memory:...\r\nmaxmemory:...\r\nevicted_keys:...` 형식의 문자열

---

## 🎬 MiniRedis 피어 평가 시연 로드맵

```text
[ 0단계: CLI 프로그램 실행 ] ──► [ 1단계: 초기화 & 기본 CRUD ] ──► [ 2단계: TTL & 만료 청소 ] ──► [ 3단계: LRU 축출 & 메모리 제어 ] ──► [ 4단계: 잔여 키 순차 삭제 ]
       (python main.py)            (HashMap + DoublyLinkedList)         (MinHeap + Lazy/Active)             (CONFIG SET + Eviction)                 (DEL 단일 키 반복)
```

## 🚀 0단계. 프로그램 시작 (대화형 CLI 구동)

터미널에서 프로젝트의 메인 진입 스크립트를 실행하여 대화형 CLI 프롬프트를 활성화합니다.

### 💻 실행 명령어

```bash
python main.py
```

---

## 🏁 1단계. 기본 CRUD와 $O(1)$ 저장소 연결 증명

가장 기초적인 데이터 입출력과 키 존재 여부, 삭제 및 개수 카운팅을 시연합니다.

### 💻 실행 명령어 순서

```bash
# 1. 서버 메모리 초기 상태 확인 (0 bytes)
INFO memory

# 2. 데이터 2개 등록 (MRU: user:2 -> user:1)
SET user:1 Dave
SET user:2 Alex

# 3. 데이터 조회 및 MRU 승격 (user:1 조회 -> user:1이 Head 바로 뒤로 이동)
GET user:1

# 4. 단일 키 존재 여부 확인 (키 1개씩 단독 검사)
EXISTS user:1
EXISTS user:99

# 5. 전체 키 목록 및 데이터 개수 확인 (인자 없이 단독 실행)
KEYS
DBSIZE

# 6. 데이터 단건 삭제
DEL user:2
DBSIZE
```

---

## ⏳ 2단계. MinHeap 만료(TTL) 및 Active/Lazy Purge 증명

수명 제한 키가 힙에 등록되고, 만료 시간이 지난 뒤 자동 소멸되는 과정을 증명합니다.

### 💻 실행 명령어 순서

```bash
# 1. 키-값 먼저 저장 (인자 2개)
SET session:temp abc

# 2. 별도 명령어로 3초 만료 시간 부여 (인자 2개)
EXPIRE session:temp 3

# 3. 남은 TTL 확인 (2 또는 1초 출력 확인)
TTL session:temp

# 4. 3초 대기 후 조회 (지연 만료: Lazy Expiration 증명)
# (3초 후 실행)
TTL session:temp
GET session:temp

# 5. 기존 키에 EXPIRE 부여 테스트
SET persistent:key 1234
TTL persistent:key
EXPIRE persistent:key 5
TTL persistent:key
```

---

## 🚪 3단계. LRU 메모리 축출 및 CONFIG SET 동적 제어

메모리 한도를 설정하고, 용량 초과 시 가장 오래 사용되지 않은 키(LRU)만 정확히 골라 제거되는지 증명합니다.

### 💻 실행 명령어 순서

```bash
# 1. 3개 키 순차 등록 (사용 순서: k3(최신) -> k2 -> k1(가장 오래됨))
SET k1 v1
SET k2 v2
SET k3 v3

# 2. k1을 조회하여 MRU로 승격 (사용 순서 변경: k1(최신) -> k3 -> k2(가장 오래됨))
GET k1

# 3. 현재 메모리 사용량 확인 (키/값 총합 바이트 확인)
INFO memory

# 4. 메모리 한도를 현재 사용량보다 작게 강제 축출 설정 (예: 2개 분량 용량으로 축소)
# -> 가장 오래된 k2가 즉시 축출되어야 함!
CONFIG SET maxmemory 8

# 5. 축출 결과 검증
INFO memory
GET k2
GET k1
GET k3
```

---

## 🧹 4단계. 잔여 키 순차 삭제(`DEL`) 및 최종 정리 검증

남아있는 키들을 `DEL <key>`로 하나씩 단건 삭제하여 캐시를 완전히 비우고 메모리가 0으로 회수되는지 확인합니다.

### 💻 실행 명령어 순서

```bash
# 1. 현재 남아있는 전체 키 목록 확인
KEYS

# 2. 남아있는 키들 1개씩 순차 삭제 (단일 인자 규격)
DEL user:1
DEL persistent:key
DEL k1
DEL k3

# 3. 최종 상태 검증
DBSIZE
KEYS
INFO memory
```
