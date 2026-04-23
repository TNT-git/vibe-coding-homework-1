"""
Vibe Coding - Lekce 1: Python skript pro LLM API s nastrojem (tool use).

Skript zavola Anthropic Claude API, da modelu k dispozici jeden nastroj
(bezpecnou kalkulacku), a vrati vysledek vypoctu zpet do LLM, aby model
zformuloval finalni odpoved pro uzivatele.

Spusteni:
    uv run main.py
    uv run main.py "Kolik je 25 procent ze 480?"
    uv run main.py --dry-run    # bez API klice, otestuje jen tool

Env promenne (.env):
    ANTHROPIC_API_KEY   -  klic z https://console.anthropic.com/
"""

import ast
import json
import math
import os
import sys
from pprint import pprint

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
SYSTEM_PROMPT = (
    "Jsi uzitecny asistent pro matematiku. Kdyz potrebujes spocitat "
    "matematicky vyraz, vzdy pouzij tool 'calculator' misto toho, abys "
    "odpoved odhadoval. Vyslednou odpoved podej cesky, strucne."
)
DEFAULT_PROMPT = "Kolik je (17 * 23) + odmocnina ze 144 - 3 na druhou?"


# ---------------------------------------------------------------------------
# Tool: bezpecna kalkulacka (AST-based, zadny eval())
# ---------------------------------------------------------------------------

# povolene AST uzly - cokoliv jineho vyhodi SyntaxError
_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Num,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Call, ast.Name, ast.Load,
)

# dostupne funkce a konstanty
_SAFE_NAMES = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
}


def _validate(node: ast.AST) -> None:
    """Projde cely AST strom a overi, ze obsahuje jen povolene prvky."""
    for child in ast.walk(node):
        if not isinstance(child, _ALLOWED_NODES):
            raise ValueError(f"Zakazana konstrukce: {type(child).__name__}")
        if isinstance(child, ast.Name) and child.id not in _SAFE_NAMES:
            raise ValueError(f"Zakazany identifikator: {child.id}")


def calculator(expression: str) -> dict:
    """Spocita matematicky vyraz. Vraci dict s 'expression' a 'result' (nebo 'error')."""
    try:
        tree = ast.parse(expression, mode="eval")
        _validate(tree)
        result = eval(  # noqa: S307  (vstup zvalidovany, zadne arbitrarni volani)
            compile(tree, "<calc>", "eval"),
            {"__builtins__": {}},
            _SAFE_NAMES,
        )
        return {"expression": expression, "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"expression": expression, "error": str(exc)}


# ---------------------------------------------------------------------------
# Definice nastroje pro Claude
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "calculator",
        "description": (
            "Spocita zadany matematicky vyraz a vrati cislo. Podporuje +, -, *, /, "
            "**, zavorky a funkce sqrt, abs, round, floor, ceil, log, log10, exp, "
            "sin, cos, tan a konstanty pi, e. Vstup musi byt ciste matematicky."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Matematicky vyraz v Python syntaxi, napr. '17 * 23 + sqrt(144)'.",
                },
            },
            "required": ["expression"],
        },
    },
]

AVAILABLE_TOOLS = {"calculator": calculator}


# ---------------------------------------------------------------------------
# Hlavni logika: tool-use smycka
# ---------------------------------------------------------------------------

def run(prompt: str) -> str:
    """Posle prompt Claudovi, obslouzi pripadne tool_use volani a vrati text odpovedi."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Chybi ANTHROPIC_API_KEY. Zkopiruj .env.example do .env a doplni klic."
        )

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": prompt}]

    # limit iteraci jako pojistka proti nekonecne smycce
    for step in range(5):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS,
            tool_choice={"type": "auto"},
        )

        print(f"\n--- Krok {step + 1}: stop_reason={response.stop_reason} ---")
        pprint(response.content)

        # pokud model nechce volat tool, jsme hotovi
        if response.stop_reason != "tool_use":
            return _extract_text(response)

        # jinak najdi tool_use bloky, spust je a posli vysledky zpet
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn = AVAILABLE_TOOLS.get(block.name)
            if fn is None:
                result = {"error": f"Nezname volani nastroje: {block.name}"}
            else:
                print(f"  -> volam {block.name}({block.input})")
                result = fn(**block.input)
                print(f"  <- {result}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        messages.append({"role": "user", "content": tool_results})

    return "(dosazen limit iteraci - model nedokoncil odpoved)"


def _extract_text(response) -> str:
    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts) if parts else "(prazdna odpoved)"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    # dry-run: otestuje jen kalkulacku, bez volani API
    if args and args[0] == "--dry-run":
        print("=== Dry-run: test kalkulacky bez volani LLM ===")
        cases = [
            "17 * 23 + sqrt(144) - 3**2",
            "25 / 100 * 480",
            "sin(pi / 2)",
            "round(log(e**5), 4)",
            "__import__('os').system('ls')",  # musi byt odmitnuto
        ]
        for expr in cases:
            print(f"  {expr!r:55} -> {calculator(expr)}")
        return

    prompt = " ".join(args) if args else DEFAULT_PROMPT
    print(f"=== Prompt: {prompt} ===")
    answer = run(prompt)
    print("\n=== Finalni odpoved ===")
    print(answer)


if __name__ == "__main__":
    main()
