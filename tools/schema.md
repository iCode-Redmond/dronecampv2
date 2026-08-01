# Problem bank schema

One JSON file per category in `data/problems/<category>.json`.
Each file is a JSON array of problem objects.

```json
{
  "id": "sleep_in",
  "category": "Warmup-1",
  "title": "Sleep In",
  "function": "sleep_in",
  "difficulty": 1,
  "concept": "Boolean logic: not + or",
  "brief": "One sentence naming what the function returns.",
  "description": "2-3 sentences. Plain language for a 10-14 year old. Original wording.",
  "starter": "def sleep_in(weekday, vacation):\n    # your code here\n    pass\n",
  "solution": "def sleep_in(weekday, vacation):\n    return not weekday or vacation\n",
  "hints": ["Nudge, no code.", "Bigger nudge, may name the operator."],
  "example": "sleep_in(False, False)  ->  True",
  "explainer": "2 sentences on why the solution works.",
  "tests": [
    {"args": [false, false], "expected": true}
  ]
}
```

## Hard rules

1. `id` unique across the whole bank, snake_case, matches `function`.
2. `starter` and `solution` must both be valid Python defining `function`.
3. `tests` >= 5 cases, covering edge cases (empty string/list, zero, negatives,
   boundaries). Every `expected` must be what `solution` actually returns —
   the validator enforces this and rejects the file otherwise.
4. `args` and `expected` must be JSON-native (no tuples, no sets). Lists are fine.
5. All prose must be ORIGINAL. Do not copy sentences from codingbat.com.
   Function names and problem semantics are fine; wording must be ours.
6. `difficulty` 1-5.
7. No problem may require imports beyond the standard builtins.
