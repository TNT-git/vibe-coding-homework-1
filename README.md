# Vibe Coding — Lekce 1: Python skript pro LLM API

Domácí úkol z kurzu **Vibe Coding** (Robot Dreams, lektor Lukáš Kellerstein).

Skript zavolá **Anthropic Claude API**, poskytne modelu jeden nástroj
(bezpečnou kalkulačku) a vrátí výsledek zpět do LLM, aby model mohl složit
finální odpověď uživateli. Jde o tzv. **tool use / function calling** pattern.

## Jak to funguje

```
1. Uživatel položí dotaz (např. "Kolik je 17 × 23 + √144 − 3²?")
2. Skript pošle dotaz Claudovi spolu s definicí toolu `calculator`.
3. Claude usoudí, že potřebuje spočítat výraz → vrátí tool_use blok.
4. Skript výraz vyhodnotí přes bezpečný AST-parser (žádné eval!).
5. Výsledek pošle zpět Claudovi jako tool_result.
6. Claude zformuluje finální česky psanou odpověď.
```

Tool podporuje `+ − × ÷ **`, závorky a funkce `sqrt, abs, round, floor, ceil,
log, log10, exp, sin, cos, tan` a konstanty `pi, e`. Všechno ostatní (importy,
přístup k filesystému, `eval`, …) je na úrovni parseru zakázané.

## Požadavky

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) (doporučený package manager kurzu)
- Anthropic API klíč z <https://console.anthropic.com/>

## Spuštění

1. Naklonuj repo a přejdi do složky:

   ```bash
   git clone <adresa-repa>
   cd vibe-coding-homework-1
   ```

2. Nastav API klíč:

   ```bash
   cp .env.example .env
   # otevři .env a doplň ANTHROPIC_API_KEY=sk-ant-...
   ```

3. Spusť (uv si sám stáhne závislosti):

   ```bash
   uv run main.py
   ```

   Nebo s vlastním dotazem:

   ```bash
   uv run main.py "Kolik je 25 procent ze 480?"
   ```

### Alternativa bez `uv run`

```bash
uv venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
uv sync
python main.py
```

### Dry-run (bez API klíče)

Otestuje samotnou kalkulačku — užitečné, když si chceš ověřit, že AST-parser
funguje a odmítá nebezpečné vstupy:

```bash
uv run main.py --dry-run
```

## Ukázka výstupu

```
=== Prompt: Kolik je (17 * 23) + odmocnina ze 144 - 3 na druhou? ===

--- Krok 1: stop_reason=tool_use ---
[TextBlock(text='Spočítám ten výraz.'), ToolUseBlock(name='calculator', input={'expression': '17 * 23 + sqrt(144) - 3**2'}, ...)]
  -> volam calculator({'expression': '17 * 23 + sqrt(144) - 3**2'})
  <- {'expression': '17 * 23 + sqrt(144) - 3**2', 'result': 394.0}

--- Krok 2: stop_reason=end_turn ---
[TextBlock(text='Výsledek je 394.')]

=== Finalni odpoved ===
Výsledek je 394.
```

## Struktura projektu

```
vibe-coding-homework-1/
├── main.py              # hlavní skript (tool-use smyčka + kalkulačka)
├── pyproject.toml       # závislosti pro uv
├── .python-version      # Python 3.12
├── .env.example         # šablona pro API klíč
├── .gitignore           # ignoruje .env, .venv, __pycache__
└── README.md            # tento soubor
```

## Poznámky

- **Model**: `claude-haiku-4-5-20251001` — levný a rychlý, pro jednoduchý tool
  use víc než dostatečný. Pro složitější úlohy lze v `main.py` změnit na
  `claude-sonnet-4-6`.
- **Bezpečnost kalkulačky**: vstup je parsován přes `ast.parse()` a validován —
  `eval` pracuje nad pre-kompilovaným stromem s prázdným `__builtins__` a jen
  whitelistem funkcí. Útoky typu `__import__('os').system(...)` nebo
  čtení proměnných selžou při validaci.
- **Limit iterací**: 5 kroků tool-use smyčky, aby skript nikdy neběhal
  donekonečna, kdyby model začal halucinovat v cyklu.

## Zdroje

- [Anthropic Tool use docs](https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview)
- Kurzový repo: `Global-Classes-CZE/Vibe-Coding-1`, složka
  `1_LLM/2_anthropic/4_tools/` (referenční příklad lektora).
