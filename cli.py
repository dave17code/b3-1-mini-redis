"""
Mini Redis CLI 인터페이스 및 명령어 파서 모듈.

사용자 입력을 토큰화(따옴표 처리 포함)하고, 유효한 명령어인지 검증한 후
MiniRedis 엔진을 호출하여 결과를 Redis 스타일로 출력하는 REPL 환경을 제공합니다.
"""

import sys
from typing import List, Optional
from mini_redis import MiniRedis


def tokenize_command(line: str) -> List[str]:
    """
    명령어 문자열을 공백 및 큰따옴표/작은따옴표 기준으로 파싱하여 토큰 목록을 생성합니다.
    예: SET user:1 "Alice Smith" -> ['SET', 'user:1', 'Alice Smith']
    """
    tokens = []
    curr = []
    in_quote = False
    quote_char = ""
    i = 0
    line_len = len(line)

    while i < line_len:
        ch = line[i]

        if in_quote:
            if ch == quote_char:
                # 닫는 따옴표 발견
                in_quote = False
                quote_char = ""
            elif ch == "\\" and i + 1 < line_len and line[i + 1] in (quote_char, "\\"):
                # 이스케이프 문자 처리
                i += 1
                curr.append(line[i])
            else:
                curr.append(ch)
        else:
            if ch in ('"', "'"):
                in_quote = True
                quote_char = ch
            elif ch.isspace():
                if len(curr) > 0:
                    tokens.append("".join(curr))
                    curr = []
            else:
                curr.append(ch)
        i += 1

    if len(curr) > 0:
        tokens.append("".join(curr))

    return tokens


class RedisCLI:
    """CLI REPL 및 명령어 라우팅 처리기."""

    def __init__(self, redis_engine: Optional[MiniRedis] = None):
        self.engine = redis_engine if redis_engine is not None else MiniRedis()

    def execute_command(self, raw_line: str) -> Optional[str]:
        """
        한 줄의 명령어를 파싱하고 적절한 메서드를 실행하여 결과 문자열을 반환합니다.
        빈 줄이나 주석은 None을 반환합니다.
        """
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return None

        tokens = tokenize_command(line)
        if not tokens:
            return None

        cmd = tokens[0].upper()

        # ---------------------------------------------------------------------
        # 1. 종료 명령어
        # ---------------------------------------------------------------------
        if cmd in ("EXIT", "QUIT"):
            return "BYE"

        # ---------------------------------------------------------------------
        # 2. String 기본 명령어
        # ---------------------------------------------------------------------
        if cmd == "SET":
            if len(tokens) != 3:
                return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
            return self.engine.set(tokens[1], tokens[2])

        if cmd == "GET":
            if len(tokens) != 2:
                return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
            return self.engine.get(tokens[1])

        if cmd == "DEL":
            if len(tokens) != 2:
                return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
            return self.engine.delete(tokens[1])

        if cmd == "EXISTS":
            if len(tokens) != 2:
                return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
            return self.engine.exists(tokens[1])

        if cmd == "DBSIZE":
            if len(tokens) != 1:
                return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
            return self.engine.dbsize()

        if cmd == "KEYS":
            if len(tokens) != 1:
                return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
            return self.engine.keys()

        # ---------------------------------------------------------------------
        # 3. 메모리 관리 명령어
        # ---------------------------------------------------------------------
        if cmd == "CONFIG":
            if len(tokens) < 2:
                return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
            sub_cmd = tokens[1].upper()
            if sub_cmd == "SET":
                if len(tokens) != 4 or tokens[2].lower() != "maxmemory":
                    if len(tokens) < 4:
                        return "(error) ERR wrong number of arguments for 'CONFIG SET' command"
                    return f"(error) ERR unsupported CONFIG parameter '{tokens[2]}'"
                
                try:
                    bytes_val = int(tokens[3])
                except ValueError:
                    return "(error) ERR value is not an integer or out of range"

                return self.engine.config_set_maxmemory(bytes_val)
            else:
                return f"(error) ERR unknown command 'CONFIG {tokens[1]}'"

        if cmd == "INFO":
            if len(tokens) != 2 or tokens[1].lower() != "memory":
                if len(tokens) != 2:
                    return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
                return f"(error) ERR unsupported section '{tokens[1]}'"
            return self.engine.info_memory()

        # ---------------------------------------------------------------------
        # 4. TTL 관리 명령어
        # ---------------------------------------------------------------------
        if cmd == "EXPIRE":
            if len(tokens) != 3:
                return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
            try:
                seconds_val = int(tokens[2])
            except ValueError:
                return "(error) ERR value is not an integer or out of range"
            return self.engine.expire(tokens[1], seconds_val)

        if cmd == "TTL":
            if len(tokens) != 2:
                return f"(error) ERR wrong number of arguments for '{tokens[0]}' command"
            return self.engine.ttl(tokens[1])

        # 알 수 없는 명령어 처리
        return f"(error) ERR unknown command '{tokens[0]}'"

    def run(self) -> None:
        """REPL(Read-Eval-Print Loop)을 실행합니다."""
        print("Mini Redis CLI Interface (Type 'exit' or 'quit' to close)")
        prompt = "mini-redis> "

        while True:
            try:
                line = input(prompt)
                result = self.execute_command(line)
                if result == "BYE":
                    break
                if result is not None:
                    print(result)
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"(error) ERR {e}")


if __name__ == "__main__":
    cli = RedisCLI()
    cli.run()
