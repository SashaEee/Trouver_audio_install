"""Event catalogue for a model: id -> {phrase, category, title}.

Built from the transcribed official pack (data/<model>_events.json). The UI
shows meanings, never raw ids.
"""
import json
import os
import re

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

CATEGORIES = ["cleaning", "battery", "maintenance", "errors", "system"]
CATEGORY_LABELS = {
    "cleaning": "Уборка",
    "battery": "Батарея и база",
    "maintenance": "Обслуживание",
    "errors": "Ошибки",
    "system": "Система",
}

# ordered: first matching group wins
_RULES = [
    ("errors", ["ошибк", "сбой", "збой", "застрял", "подвешен", "бампер", "амортизатор",
                "перегрев", "переохлажд", "колес", "не касаются", "запретн", "недоступн",
                "поврежден", "наклон", "неисправ", "застрявш"]),
    ("maintenance", ["контейнер", "фильтр", "щетк", "швабр", "мешок", "воздуховод", "насос",
                     "датчик", "лазер", "очистите", "прочистите", "опораж", "опуст", "автоочист", "бак", "вода", "воды"]),
    ("battery", ["заряд", "аккумулятор", "док", "базу", "базе", "базы", "станц", "выключ"]),
    ("cleaning", ["уборк", "убир", "пауз", "точечн", "комнат", "планов", "продолжить задачу",
                  "построени", "карт", "удаленн", "мопп", "мытьё", "мытье"]),
    ("system", ["включ", "обновлен", "обновит", "обновл", "сет", "wi-fi", "wifi", "блок",
                "калибр", "тест", "музыка", "телефон", "заводск", "позиционир", "местоположен",
                "язык", "режим", "восстановл"]),
]

# curated short titles for the events users actually hear
_TITLES = {
    "003": "Включение", "006": "Начало уборки", "007": "Пауза", "008": "Продолжить уборку",
    "009": "Точечная уборка", "010": "Уборка завершена", "011": "Низкий заряд, на базу",
    "012": "Еду на базу", "013": "Пауза", "014": "Начать зарядку", "015": "Зарядка",
    "016": "Продолжить уборку", "017": "Низкий заряд", "018": "Обновление",
    "019": "Обновлено", "020": "Контейнер вынут", "021": "Контейнер установлен",
    "024": "Контейнер не установлен", "042": "Низкий заряд, выключаюсь",
    "045": "Я здесь", "047": "Плановая уборка", "065": "Уборка комнаты",
    "090": "Уборка завершена", "110": "Швабры установлены", "111": "Швабры удалены",
    "114": "Режим пульта", "126": "Зона недоступна", "127": "Запретная зона",
    "241": "Детский блок вкл", "242": "Детский блок выкл", "255": "Построение карты",
    "256": "Пауза", "257": "Продолжить карту", "361": "Позиционирование",
}


def _categorize(phrase):
    p = (phrase or "").lower()
    for cat, kws in _RULES:
        if any(k in p for k in kws):
            return cat
    return "system"


def _title(eid, phrase):
    if eid in _TITLES:
        return _TITLES[eid]
    words = re.sub(r"[^\w\s]", "", phrase or "").split()
    return " ".join(words[:4]) if words else f"Событие {eid}"


def load_model_map(model):
    path = os.path.join(DATA, f"{model.split('.')[-1]}_events.json")
    if not os.path.exists(path):
        # fall back to r2567r catalogue
        path = os.path.join(DATA, "r2567r_events.json")
    return json.load(open(path, encoding="utf-8"))


def load_maxim_ids():
    p = os.path.join(DATA, "maxim_map.json")
    if os.path.exists(p):
        return set(json.load(open(p)).keys())
    return set()


# events worth surfacing first (skip factory-test / music ids)
_HIDDEN = set(["Q001", "022"]) | {f"{n:03d}" for n in range(204, 241)}


def build_events(model):
    raw = load_model_map(model)
    out = []
    for eid in sorted(raw, key=lambda x: int(re.sub(r"[^0-9]", "", x) or 9999)):
        if eid in _HIDDEN:
            continue
        phrase = raw[eid].strip()
        if not phrase:
            continue
        out.append({
            "id": eid,
            "phrase": phrase,
            "category": _categorize(phrase),
            "title": _title(eid, phrase),
        })
    return out
