#!/usr/bin/env python3
"""CLI для конвертації тексту між розкладками. Читає stdin/аргумент, пише в stdout."""
import argparse
import sys

from langswitcher import (
    DEFAULT_LAYOUTS,
    convert,
    convert_greedy,
    convert_selected,
    looks_like_wrong_layout_strict,
)


def parse_args():
    p = argparse.ArgumentParser(description="LangSwitcher Linux — конвертер неправильної розкладки")
    p.add_argument("text", nargs="?", help="текст (якщо нема — читаємо stdin)")
    p.add_argument("--layouts", default=",".join(DEFAULT_LAYOUTS),
                   help=f"кандидатні розкладки через кому (default: {','.join(DEFAULT_LAYOUTS)})")
    p.add_argument("--from", dest="from_layout", default=None, help="явна source-розкладка")
    p.add_argument("--to", dest="to_layout", default=None, help="явна target-розкладка")
    p.add_argument("--mode", choices=["selection", "greedy", "last-word", "auto"],
                   default="selection",
                   help="greedy = Smart Conversion (Greedy Line), auto = only convert a word "
                        "that clearly looks wrong-layout (Punto-style, used by the Windows hook)")
    return p.parse_args()


def main() -> int:
    a = parse_args()
    layouts = [l.strip() for l in a.layouts.split(",") if l.strip()]
    text = a.text if a.text is not None else sys.stdin.read()
    if text.endswith("\n") and a.text is None:
        text = text[:-1]
    if not text:
        print("nothing to convert", file=sys.stderr)
        return 1

    if a.from_layout and a.to_layout:
        res = convert(text, a.from_layout, a.to_layout)
        if res is None:
            print("conversion failed", file=sys.stderr)
            return 1
        print(res, end="")
        return 0

    if a.mode == "auto":
        # Conservative single-word mode: leave normal English/Ukrainian alone.
        if not looks_like_wrong_layout_strict(text, layouts):
            print("no wrong layout detected", file=sys.stderr)
            return 2
        r = convert_selected(text, layouts)
        if r is None:
            print("no wrong layout detected", file=sys.stderr)
            return 2
        print(r[0], end="")
        return 0

    if a.mode in ("greedy", "last-word"):
        if a.mode == "last-word":
            # останнє слово — як режим Last Word у macOS-версії
            parts = text.rsplit(" ", 1)
            if len(parts) == 2:
                head, tail = parts
                r = convert_selected(tail, layouts)
                if r is None:
                    print("no wrong layout detected", file=sys.stderr)
                    return 2
                print(head + " " + r[0], end="")
                return 0
        r = convert_greedy(text, layouts)
        if r is None:
            # fallback: спробувати як звичайне виділення
            r = convert_selected(text, layouts)
        if r is None:
            print("no wrong layout detected", file=sys.stderr)
            return 2
        print(r[0], end="")
        return 0

    r = convert_selected(text, layouts)
    if r is None:
        print("no wrong layout detected", file=sys.stderr)
        return 2
    print(r[0], end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
