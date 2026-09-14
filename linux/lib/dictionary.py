#!/usr/bin/env python3
"""Словник користувача — слова, які авто-режим не має права конвертувати.

Авто-режим вирішує лише за правдоподібністю (``looks_like_wrong_layout_strict``
у ``langswitcher.py``): слово без голосної у власній абетці, яке отримує
голосну в іншій, переписується. Це правило не може знати, що ``kbd`` чи ``ssh``
— потрібне слово, тому кожне слово, яке користувач відкинув, запам'ятовується
тут і більше не чіпається.

Файл — користувача: звичайний JSON, один запис на рядок, правиться руками.

    {"version": 1,
     "entries": [{"word": "kbd", "source": "seed", "ts": 0},
                 {"word": "ghbdsn", "source": "learned", "ts": 1789...}]}

``source`` — ``seed`` (з коробки), ``learned`` (авто-режим побачив, що слово
набрали знову після виправлення) або ``manual`` (вписане у файл руками). Seed
записується у файл при першому використанні, тож кожне слово видно й можна
видалити — у коді після появи файлу нічого не ховається.

Збіг — точний, без урахування регістру, по буквено-цифровому ядру слова, тож
"Kbd." і "kbd" — одне слово. Список обмежений (``CAP``): найстаріші ``learned``
витісняються першими, далі ``seed``; ``manual`` не видаляється ніколи.

Цей файл навмисно продубльовано в бандлах omarchy-plugin і linux; тримайте
обидві копії байт-у-байт ідентичними.

Без залежностей, тільки stdlib.
"""
import json
import os
import time

DEFAULT_PATH = "~/.config/omarchy/langswitcher-dictionary.json"
VERSION = 1
CAP = 1000

# Латинські скорочення без жодної латинської голосної: саме вони підпадають під
# строгу перевірку (``looks_like_wrong_layout_strict``) і переписуються в
# кирилицю, хоч це очевидні слова. Слово з голосною сюди не потрапляє — його й
# так не чіпають, і воно лише маскувало б те, як працює список (це перевіряє
# test_dictionary.py). Усе, чого тут немає, користувач додає сам: файл, відкат
# або автонавчання.
SEED_WORDS = (
    "cfg", "cmd", "css", "csv", "ctrl", "dbg", "dns", "fmt", "ftp", "gcc",
    "gdb", "gpg", "hdd", "html", "http", "https", "jpg", "jwt", "kbd", "kvm",
    "lsp", "lvm", "mnt", "msg", "npm", "nth", "ntp", "npx", "pdf", "php",
    "png", "psql", "ptr", "rgb", "rpm", "sdk", "sftp", "sql", "src", "ssd",
    "ssh", "str", "tmp", "ttl", "txt", "vnc", "vpn", "xml", "zsh",
)


def _expand(path: str) -> str:
    return os.path.expanduser(path) if path.startswith("~") else path


def core(word: str) -> str:
    """Буквено-цифрове ядро слова: "Kbd." -> "Kbd", "(ssh)" -> "ssh"."""
    text = str(word or "").strip()
    start, end = 0, len(text)
    while start < end and not text[start].isalnum():
        start += 1
    while end > start and not text[end - 1].isalnum():
        end -= 1
    return text[start:end]


def _key(word: str) -> str:
    return core(word).casefold()


def _entry(word: str, source: str, ts: int) -> dict:
    return {"word": core(word), "source": source, "ts": int(ts)}


def normalize(document) -> dict:
    """Документ, безпечний для використання навіть після правок руками.

    Приймає і повний формат, і голий рядок у ``entries`` (щоб файл можна було
    скоротити до ``["kbd", "ssh"]``), мовчки відкидає сміття й дублікати.
    """
    entries: list[dict] = []
    seen: set[str] = set()
    raw_entries = (document or {}).get("entries") if isinstance(document, dict) else None
    for raw in raw_entries or []:
        if isinstance(raw, str):
            word, source, ts = raw, "manual", 0
        elif isinstance(raw, dict):
            word = str(raw.get("word") or "")
            source = str(raw.get("source") or "manual")
            ts = raw.get("ts") or 0
        else:
            continue
        key = _key(word)
        if not key or key in seen:
            continue
        if source not in ("seed", "learned", "manual"):
            source = "manual"
        seen.add(key)
        entries.append(_entry(word, source, ts))
    return {"version": VERSION, "entries": entries}


def seeded() -> dict:
    """Словник із самих лише вбудованих слів (``ts`` 0 — найстаріші)."""
    return {"version": VERSION, "entries": [_entry(w, "seed", 0) for w in SEED_WORDS]}


def read(path: str | None = None) -> dict | None:
    """Словник із файлу, або None, якщо файлу немає / він зіпсований."""
    try:
        with open(_expand(path or DEFAULT_PATH), encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(loaded, dict):
        return None
    return normalize(loaded)


def ensure(path: str | None = None) -> dict:
    """Словник, який точно існує: при першому використанні пише seed у файл."""
    document = read(path)
    if document is None:
        document = seeded()
        save(document, path=path)
    return document


def _dumps(document: dict) -> str:
    """JSON, який приємно правити руками: один запис на рядок."""
    entries = document.get("entries") or []
    lines = ["{", ' "version": %d,' % int(document.get("version") or VERSION), ' "entries": [']
    for index, entry in enumerate(entries):
        comma = "," if index < len(entries) - 1 else ""
        lines.append("  " + json.dumps(entry, ensure_ascii=False) + comma)
    lines += [" ]", "}"]
    return "\n".join(lines) + "\n"


def save(document: dict, path: str | None = None) -> bool:
    """Атомарний запис: недописаний файл не має лишитись на диску."""
    target = _expand(path or DEFAULT_PATH)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        temporary = target + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(_dumps(document))
        os.replace(temporary, target)
        return True
    except OSError:
        return False


def keys(document: dict) -> set[str]:
    """Множина згорнутих ядер — те, з чим порівнюється набране слово."""
    return {_key(entry.get("word")) for entry in (document or {}).get("entries") or []}


def covers(document: dict, word: str) -> bool:
    """Чи є слово у словнику (точно, без урахування регістру, по ядру)."""
    key = _key(word)
    return bool(key) and key in keys(document)


def add(document: dict, word: str, source: str = "learned", now: int | None = None) -> dict:
    """Додати слово (або освіжити існуючий запис). Повертає той самий документ."""
    key = _key(word)
    if not key:
        return document
    stamp = int(now if now is not None else time.time() * 1000)
    entries = document.setdefault("entries", [])
    for entry in entries:
        if _key(entry.get("word")) != key:
            continue
        # Вбудоване слово лишається вбудованим: оновлення seed у коді має
        # доходити до файлу, а не перетворюватись на "learned".
        if entry.get("source") == "seed":
            return document
        entry["source"] = source if source in ("seed", "learned", "manual") else "manual"
        entry["ts"] = stamp
        return document
    entries.append(_entry(word, source if source in ("seed", "learned", "manual") else "manual",
                          stamp))
    return document


def trim(document: dict) -> dict:
    """Вписатися в ``CAP``, витісняючи найстаріші learned, далі seed.

    ``manual`` не видаляється ніколи: якщо файл переповнений самими лише
    ручними записами, він таким і лишиться — краще великий файл, ніж тихо
    загублене слово, яке користувач вписав сам.
    """
    entries = document.get("entries") or []
    overflow = len(entries) - CAP
    if overflow <= 0:
        return document
    drop: set[int] = set()
    for source in ("learned", "seed"):
        order = sorted((index for index, entry in enumerate(entries)
                        if index not in drop and entry.get("source") == source),
                       key=lambda index: entries[index].get("ts") or 0)
        for index in order:
            if len(drop) >= overflow:
                break
            drop.add(index)
        if len(drop) >= overflow:
            break
    if drop:
        document["entries"] = [entry for index, entry in enumerate(entries)
                               if index not in drop]
    return document
