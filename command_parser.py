import re
from rapidfuzz import fuzz, process

DEVICE_VARIANTS = {
    "LED1": [
        "light 1", "ek number light", "prothom light",
        "light one", "wan number light",
        "1 number light", "light number 1", "light number one",
    ],
    "LED2": [
        "light 2", "dui number light", "ditiyo light",
        "light two", "dto number light",
        "2 number light", "light number 2", "light number two",
    ],
    "FAN1": [
        "fan 1", "ek number fan", "prothom fan",
        "fan one", "wan number fan",
        "1 number fan", "fan number 1", "fan number one",
    ],
    "FAN2": [
        "fan 2", "dui number fan", "ditiyo fan",
        "fan two", "dto number fan",
        "2 number fan", "fan number 2", "fan number two",
    ],
}

ACTION_VARIANTS = {
    "on":  ["on", "chalu", "cholo", "chalao", "charo", "chharo"],
    "off": ["off", "bondho", "bondo", "bondhu"],
}

ALL_VARIANTS = {
    "all": ["shob", "shobkichu"],
}

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _best_match(token: str, variants: dict, score_cutoff: int = 85):
    best_canonical, best_score = None, score_cutoff - 1
    for canonical, spellings in variants.items():
        match = process.extractOne(token, spellings, scorer=fuzz.ratio, score_cutoff=score_cutoff)
        if match is not None and match[1] > best_score:
            best_canonical, best_score = canonical, match[1]
    return best_canonical


def _phrase_matches(window: list[str], phrase_tokens: list[str], score_cutoff: int = 85) -> bool:
    return all(fuzz.ratio(w, p) >= score_cutoff for w, p in zip(window, phrase_tokens))


def _match_device_phrase(tokens: list[str], start: int, lengths_desc: list[int]):
    for length in lengths_desc:
        if start + length > len(tokens):
            continue
        window = tokens[start:start + length]
        matched = set()
        for device_id, phrases in DEVICE_VARIANTS.items():
            for phrase in phrases:
                phrase_tokens = phrase.split()
                if len(phrase_tokens) == length and _phrase_matches(window, phrase_tokens):
                    matched.add(device_id)
                    break
        if len(matched) == 1:
            return matched.pop(), length
        if len(matched) > 1:
            return "ambiguous", length
    return None


def parse_command(text: str):
    tokens = _tokenize(text)
    if not tokens:
        return None

    lengths_desc = sorted({len(p.split()) for phrases in DEVICE_VARIANTS.values() for p in phrases}, reverse=True)

    awaiting = []      # device_ids waiting for an action
    commands = []       # (device_id, action) tuples, in order

    i = 0
    while i < len(tokens):
        match = _match_device_phrase(tokens, i, lengths_desc)
        if match is not None:
            device_id, length = match
            if device_id == "ambiguous":
                return None
            awaiting.append(device_id)
            i += length
            continue

        token = tokens[i]

        action = _best_match(token, ACTION_VARIANTS)
        if action is not None:
            if not awaiting:
                return None  # action word with nothing waiting for it
            for device_id in awaiting:
                commands.append((device_id, action))
            awaiting = []
            i += 1
            continue

        if _best_match(token, ALL_VARIANTS) is not None:
            awaiting.extend(DEVICE_VARIANTS.keys())
            i += 1
            continue

        i += 1  # filler word ("koro", a stray "number", an unsupported number like "3", ...)

    if awaiting:
        return None  # device(s) left waiting with no action ever assigned


    seen = {}
    result = []
    for device_id, action in commands:
        if device_id in seen:
            if seen[device_id] != action:
                return None
            continue
        seen[device_id] = action
        result.append((device_id, action))

    return result or None