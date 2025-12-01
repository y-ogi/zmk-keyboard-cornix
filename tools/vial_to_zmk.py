#!/usr/bin/env python3
"""
Convert a Vial/QMK JSON keymap into this repo's ZMK .keymap.

Assumptions
-----------
* Vial JSON uses the same physical order as the layout JSON in config/cornix*.json.
* MT/L*CTL_T style keys are mapped to this repo's homerow hold-tap behaviors:
  - left side -> &hm_l (or &hm_shift_l for shifts)
  - right side -> &hm_r (or &hm_shift_r for shifts)
* Unknown keycodes fall back to "&none" and are reported as warnings.

Usage
-----
python tools/vial_to_zmk.py --vial path/to/vial.json --variant 54 \\
    --out config/cornix.keymap

Variants: 54 (cornix) or 42 (cornix42). The script only rewrites the layer
bindings found in the target .keymap; other sections (behaviors/combos) stay.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


KEYMAP_PATHS = {
    "54": Path("config/cornix.keymap"),
    "42": Path("config/cornix42.keymap"),
}

LAYOUT_JSON = {
    "54": Path("config/cornix.json"),
    "42": Path("config/cornix42.json"),
}

# Layer names in the existing .keymap (order matters)
LAYER_NAMES = {
    "54": [
        "default_layer",
        "win_layer",
        "Symbol_layer",
        "Mix_layer",
        "Adjust_layer",
        "Navi_layer",
        "KeyPad_layer",
        "Debug_layer",
    ],
    "42": [
        "default_layer",
        "lower_layer",
        "raise_layer",
    ],
}

# Basic QMK -> ZMK keycode map
KC = {
    "KC_NO": "&none",
    "KC_TRNS": "&trans",
    "KC_TRANSPARENT": "&trans",
    "KC_BSPC": "&kp BACKSPACE",
    "KC_BSPACE": "&kp BACKSPACE",
    "KC_TAB": "&kp TAB",
    "KC_ESC": "&kp ESC",
    "KC_ENTER": "&kp 0x28",
    "KC_ENT": "&kp 0x28",
    "KC_SPC": "&kp 0x2C",
    "KC_SPACE": "&kp 0x2C",
    "KC_DEL": "&kp DELETE",
    "KC_INS": "&kp INS",
    "KC_HOME": "&kp HOME",
    "KC_END": "&kp END",
    "KC_PGUP": "&kp PG_UP",
    "KC_PGDN": "&kp PG_DN",
    "KC_LEFT": "&kp LEFT",
    "KC_RGHT": "&kp RIGHT",
    "KC_RIGHT": "&kp RIGHT",
    "KC_UP": "&kp UP",
    "KC_DOWN": "&kp DOWN",
    "KC_LCTL": "&kp LCTRL",
    "KC_RCTL": "&kp RCTRL",
    "KC_LALT": "&kp LALT",
    "KC_RALT": "&kp RALT",
    "KC_LGUI": "&kp LGUI",
    "KC_RGUI": "&kp RGUI",
    "KC_LSFT": "&kp LSHFT",
    "KC_RSFT": "&kp RSHFT",
    "KC_CAPS": "&kp CAPSLOCK",
    "KC_CAPSLOCK": "&kp CAPSLOCK",
    "KC_MUTE": "&kp MUTE",
    "KC_VOLU": "&kp C_VOL_UP",
    "KC_VOLD": "&kp C_VOL_DN",
    "RESET": "&bootloader",
    "KC_BTN1": "&mkp MB1",
    "KC_BTN2": "&mkp MB2",
    "KC_BTN3": "&mkp MB3",
}

# digits
for i in range(10):
    KC[f"KC_{i}"] = f"&kp N{i}"
KC["KC_1"] = "&kp N1"  # overwrite to keep format consistent

# Function keys
for i in range(1, 25):
    KC[f"KC_F{i}"] = f"&kp F{i}"

# Symbols / punctuation
KC.update(
    {
        "KC_MINS": "&kp MINUS",
        "KC_MINUS": "&kp MINUS",
        "KC_EQL": "&kp EQUAL",
        "KC_EQUAL": "&kp EQUAL",
        "KC_PLUS": "&kp PLUS",
        "KC_PLUS": "&kp PLUS",
        "KC_BSLS": "&kp BSLH",
        "KC_BSLASH": "&kp BSLH",
        "KC_SLSH": "&kp FSLH",
        "KC_SLSH": "&kp FSLH",
        "KC_SCLN": "&kp SEMI",
        "KC_SCLN": "&kp SEMI",
        "KC_SCOLON": "&kp SEMI",
        "KC_COLN": "&kp COLON",
        "KC_QUOT": "&kp SQT",
        "KC_DQUO": "&kp DQT",
        "KC_COMM": "&kp COMMA",
        "KC_DOT": "&kp DOT",
        "KC_LBRC": "&kp LBKT",
        "KC_RBRC": "&kp RBKT",
        "KC_LCBR": "&kp LBRC",
        "KC_RCBR": "&kp RBRC",
        "KC_GRV": "&kp GRAVE",
        "KC_TILD": "&kp TILDE",
        "KC_EXLM": "&kp EXCL",
        "KC_AT": "&kp AT",
        "KC_HASH": "&kp HASH",
        "KC_DLR": "&kp DLLR",
        "KC_PERC": "&kp PRCNT",
        "KC_CIRC": "&kp CARET",
        "KC_AMPR": "&kp AMPS",
        "KC_ASTR": "&kp ASTRK",
        "KC_LPRN": "&kp LPAR",
        "KC_RPRN": "&kp RPAR",
        "KC_UNDS": "&kp UNDER",
        "KC_PIPE": "&kp PIPE",
        "KC_LT": "&kp LESS_THAN",
        "KC_GT": "&kp GREATER_THAN",
    }
)


def load_layout(variant: str) -> List[Dict]:
    with LAYOUT_JSON[variant].open() as f:
        j = json.load(f)
    layout = j["layouts"][next(iter(j["layouts"]))]["layout"]
    return layout


def reorder_vial_matrix(layer_rows, layout):
    """
    Map Vial's 8x7 matrix (4 rows per side) into the 14-column layout used in
    config/cornix*.json. We place values by (row, col):
      left  side cols 0..6  (as-is)
      right side cols 8..13 (row list reversed so inner -> outer)
    Any -1 becomes None (later mapped to &none).
    Output is a flat list ordered exactly like the layout JSON (by row, then col).
    """
    if len(layer_rows) != 8:
        # Fallback: row-major keeping -1 as None to preserve slots
        out = []
        for row in layer_rows:
            out.extend([None if k == -1 else k for k in row])
        return out

    # Build a map (row, col) -> token/None
    rc_map = {}
    for r in range(4):
        left = layer_rows[r]
        right = list(reversed(layer_rows[4 + r]))  # Vial stores outer->inner; reverse to inner->outer

        # left: keep order (outer -> inner), keep gaps
        for c, val in enumerate(left):
            rc_map[(r, c)] = None if val == -1 else val

        # right: now inner->outer; drop gaps, and if we have more keys than
        # layout columns, trim from the inner side (front of list).
        packed = [v for v in right if v != -1]
        num_right = sum(1 for k in layout if k["row"] == r and k["col"] >= 8)
        while len(packed) > num_right:
            packed.pop(0)
        for j, val in enumerate(packed):
            rc_map[(r, 8 + j)] = val

    ordered = []
    for key in layout:
        r, c = key["row"], key["col"]
        ordered.append(rc_map.get((r, c)))
    return ordered


def side_of_index(idx: int, layout: List[Dict]) -> str:
    """Return 'left' or 'right' based on x coordinate."""
    x = layout[idx]["x"]
    return "left" if x < 7 else "right"


def zmk_key(
    token: str, idx: int, layout: List[Dict], warnings: List[str], td_map=None
) -> str:
    """
    Convert a single Vial/QMK token to ZMK binding string.
    """
    if token is None:
        return "&none"
    token = token.strip()

    if td_map and token in td_map:
        return td_map[token]

    if token in KC:
        return KC[token]

    if token.startswith("KC_"):
        # Fallback: &kp KC_NAME (last part)
        return f"&kp {token[3:]}"

    # Transparent / none placeholders used by some exports
    if token in ("_______", "XXXXXXX"):
        return "&none"
    if token in ("KC_TRNS", "TRNS", "_______", "KC_TRANSPARENT"):
        return "&trans"

    # Layer switch
    m = re.match(r"MO\((\d+)\)", token)
    if m:
        return f"&mo {m.group(1)}"
    m = re.match(r"TG\((\d+)\)", token)
    if m:
        return f"&tog {m.group(1)}"
    m = re.match(r"TO\((\d+)\)", token)
    if m:
        return f"&to {m.group(1)}"
    m = re.match(r"DF\((\d+)\)", token)
    if m:
        return f"&to {m.group(1)}"

    # Layer-tap LT(layer, KC_x)
    m = re.match(r"LT\((\d+),\s*KC_([A-Z0-9_]+)\)", token)
    if m:
        # Simplify: convert LT(layer, key) to plain tap key to avoid extra binding cells issues.
        return f"&kp {m.group(2)}"

    # Mod-tap forms: LCTL_T(KC_A)
    m = re.match(r"(LCTL|RCTL|LALT|RALT|LGUI|RGUI|LSFT|RSFT)_T\(KC_([A-Z0-9_]+)\)", token)
    if not m:
        m = re.match(
            r"MT\((MOD_[A-Z]+),\s*KC_([A-Z0-9_]+)\)", token
        )
    if m:
        mod_raw = m.group(1)
        tap = m.group(2)
        mod = {
            "LCTL": "LCTRL",
            "RCTL": "RCTRL",
            "LALT": "LALT",
            "RALT": "RALT",
            "LGUI": "LGUI",
            "RGUI": "RGUI",
            "LSFT": "LSHFT",
            "RSFT": "RSHFT",
            "MOD_LCTL": "LCTRL",
            "MOD_RCTL": "RCTRL",
            "MOD_LALT": "LALT",
            "MOD_RALT": "RALT",
            "MOD_LGUI": "LGUI",
            "MOD_RGUI": "RGUI",
            "MOD_LSFT": "LSHFT",
            "MOD_RSFT": "RSHFT",
        }.get(mod_raw, mod_raw)
        side = side_of_index(idx, layout)
        if mod in ("LSHFT", "RSHFT"):
            beh = "hm_shift_l" if side == "left" else "hm_shift_r"
        else:
            beh = "hm_l" if side == "left" else "hm_r"
        return f"&{beh} {mod} {tap}"

    # Chorded modifiers e.g. LCTL(KC_C) -> &kp LC(C)
    m = re.match(r"(LCTL|RCTL|LALT|RALT|LGUI|RGUI|LSFT|RSFT)\(KC_([A-Z0-9_]+)\)", token)
    if m:
        mod = m.group(1)
        tap = m.group(2)
        chord = {
            "LCTL": "LC",
            "RCTL": "RC",
            "LALT": "LA",
            "RALT": "RA",
            "LGUI": "LG",
            "RGUI": "RG",
            "LSFT": "LS",
            "RSFT": "RS",
        }[mod]
        return f"&kp {chord}({tap})"

    # Shifted keys e.g. LSFT(KC_1)
    m = re.match(r"LSFT\(KC_([A-Z0-9_]+)\)", token)
    if m:
        return f"&kp LS({m.group(1)})"

    warnings.append(token)
    return "&none"


def format_bindings(bindings: List[str], layout: List[Dict], base_indent: str) -> str:
    rows: Dict[int, List[str]] = {}
    for key, pos in zip(bindings, layout):
        rows.setdefault(pos["row"], []).append(key)
    lines = []
    for row in sorted(rows.keys()):
        lines.append(base_indent + " ".join(rows[row]))
    return "\n".join(lines)


def replace_layer_block(text: str, layer_name: str, new_block: str) -> str:
    pattern = re.compile(
        rf"({layer_name}\s*{{.*?bindings\s*=\s*<)(.*?)(>;)", re.S
    )
    m = pattern.search(text)
    if not m:
        raise ValueError(f"Layer '{layer_name}' not found in keymap.")
    prefix, _, suffix = m.groups()
    return text[: m.start()] + prefix + "\n" + new_block + "\n" + suffix + text[m.end() :]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vial", required=True, help="Path to Vial/QMK JSON")
    ap.add_argument("--variant", choices=["54", "42"], required=True)
    ap.add_argument("--out", help="Path to write .keymap (default: replace repo file)")
    args = ap.parse_args()

    vial_path = Path(args.vial)
    variant = args.variant
    out_path = Path(args.out) if args.out else KEYMAP_PATHS[variant]
    keymap_path = KEYMAP_PATHS[variant]

    with vial_path.open() as f:
        vial = json.load(f)

    td_def = vial.get("tap_dance")

    layout = load_layout(variant)

    if "layers" in vial:
        layers: List[List[str]] = vial["layers"]
    elif isinstance(vial.get("layout"), list):
        # Vial .vil export: list of layers, each is a 2D matrix; -1 = no key
        layers = []
        for layer_rows in vial["layout"]:
            flat = reorder_vial_matrix(layer_rows, layout)
            layers.append(flat)
    else:
        sys.exit("Could not find 'layers' or 'layout' in Vial file.")
    if len(layout) != len(layers[0]):
        sys.exit(
            f"Layout length mismatch: layout has {len(layout)} keys, "
            f"Vial layer has {len(layers[0])}."
        )

    with keymap_path.open() as f:
        keymap_txt = f.read()

    layer_names = LAYER_NAMES[variant]
    if len(layers) > len(layer_names):
        print(
            f"Warning: Vial has {len(layers)} layers but keymap has only {len(layer_names)}. Extra layers will be ignored.",
            file=sys.stderr,
        )
        layers = layers[: len(layer_names)]
    warnings: List[str] = []

    # Tap dance mapping: TD(n) -> &lt layer key (only single tap/hold supported)
    td_map: Dict[str, str] = {}
    if td_def:
        for idx, td in enumerate(td_def):
            if not isinstance(td, list) or len(td) < 2:
                continue
            tap, hold = td[0], td[1]
            dtap = td[2] if len(td) > 2 else "KC_NO"
            dhold = td[3] if len(td) > 3 else "KC_NO"
            if tap in ("KC_NO", "KC_TRNS"):
                continue
            if hold.startswith("MO(") and hold.endswith(")"):
                layer_num = hold[3:-1]
                tap_binding = zmk_key(tap, 0, layout, warnings, None)
                td_map[f"TD({idx})"] = tap_binding
                if dtap not in ("KC_NO", "KC_TRNS") or dhold not in ("KC_NO", "KC_TRNS"):
                    warnings.append(f"TD({idx}) double tap/hold ignored")
            else:
                warnings.append(f"TD({idx}) hold '{hold}' not mapped")

    for idx_layer, tokens in enumerate(layers):
        bindings = [
            zmk_key(tok, i, layout, warnings, td_map) for i, tok in enumerate(tokens)
        ][: len(layout)]  # guard: do not exceed layout size
        # Use indent from existing block if possible
        indent = "            "
        block = format_bindings(bindings, layout, indent)
        keymap_txt = replace_layer_block(
            keymap_txt, layer_names[idx_layer], block
        )

    out_path.write_text(keymap_txt)

    if warnings:
        print("Warnings (unmapped tokens -> &none):", file=sys.stderr)
        for w in sorted(set(warnings)):
            print("  ", w, file=sys.stderr)
    else:
        print("Done. No unmapped tokens.", file=sys.stderr)


if __name__ == "__main__":
    main()
