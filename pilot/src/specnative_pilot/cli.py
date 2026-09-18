from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .controller import Controller


def main() -> int:
    parser = argparse.ArgumentParser(description="Piloto interactivo de definición SpecNative")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--initiative")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--question-mode", choices=["single", "batch"])
    args = parser.parse_args()
    repo = args.repo.resolve()
    config = load_config(repo, args.config, args.question_mode)
    try:
        return Controller(config).run(args.initiative)
    except KeyboardInterrupt:
        print("\nSesión cancelada.")
        return 130
    except (OSError, RuntimeError) as error:
        print(f"Error del piloto: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
