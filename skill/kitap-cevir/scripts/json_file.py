"""Projenin elle de okunan JSON dosyaları: UTF-8, Türkçe karakterler kaçışsız, iki boşluk girinti."""
import json
import os


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, payload):
    """Klasörü gerekirse kurar; yazılan yolu döndürür."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path
