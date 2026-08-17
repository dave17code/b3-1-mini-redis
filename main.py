"""
Mini Redis 애플리케이션 진입점 (Entrypoint).
"""

import sys
from cli import RedisCLI


def main():
    cli = RedisCLI()
    cli.run()


if __name__ == "__main__":
    main()
