# The prompts

The writing policy of sizu-writer lives in `prompts/*.md`, outside the Python
package. Adjusting how the system writes is editing a Markdown file, not
changing code, and `PROMPT_DIR` points the whole set somewhere else. This
document describes what each file is for, the contract they have to keep with
`sizu_writer/generator.py`, and how to work on them.

It matters more here than it would elsewhere. Everything this system is judged
on — whether the post reads like the person who wrote the memo, whether it
stays the length the material deserves, whether a familiar theme is presented
as freshly discovered — is decided by these four files. The Python around them
only carries text to an endpoint and validates what comes back.

## The four files

| File | Sent as | Used by |
|---|---|---|
| `system.md` | system message | `generate` |
| `body_user.md` | user message | `generate` |
| `titles_system.md` | system message | `titles` |
| `titles_user.md` | user message | `titles` |

Two pairs, one per command. `sizu_writer/prompts.py` reads them and assembles
the message list; it performs no API call, so a prompt can be exercised without
spending a request.

`titles_system.md` deliberately repeats the title policy of `system.md` rather
than referring to it. When only the titles are regenerated the body is already
settled, and a prompt that also described how to write a body would invite the
model to rewrite one it was told to leave alone. The cost is that a change to
the title policy belongs in both files.

## Placeholders

Two, substituted by `sizu_writer/prompts.py`:

| Placeholder | Replaced with | Appears in |
|---|---|---|
| `{{input}}` | the memo the person entered | `body_user.md`, `titles_user.md` |
| `{{body}}` | the body already settled | `titles_user.md` |

Substitution is `str.replace()`, not `str.format()`, so a brace written in a
prompt needs no escaping — which matters, because the output format section of
`system.md` shows a JSON object full of braces.

An unknown placeholder is not an error. `{{tone}}` written into a prompt stays
in the text literally and reaches the model as those eight characters, so a
typo in a placeholder name fails quietly rather than loudly. Check a new
placeholder against the table above.

## The JSON contract

`system.md` ends by asking for one JSON object and nothing else:

```json
{
  "body_markdown": "the whole post body",
  "primary_title": "the leading title",
  "alternative_titles": ["another candidate", "..."]
}
```

`titles_system.md` asks for the same object without `body_markdown`.

The prompt carries the whole contract, so that it holds whether or not the API
is also asked. That is what `GENERATION_RESPONSE_MODE` selects:

| Mode | The request | The prompt |
|---|---|---|
| `prompt-json` (default) | sends nothing extra | is the only statement of the contract |
| `json-object` | sends `response_format={"type":"json_object"}` | states it again in words |

The instruction stays in the prompt even under `json-object`, because the two
do different work. `response_format` makes the answer parse; the prompt is what
keeps an editing note out of `body_markdown`. A model told only to return JSON
will happily return valid JSON whose body field opens with a remark about the
instructions it was given.

The same four prompts serve both modes. There is no `prompts-json-object/`
alongside `prompts/`: a policy that differs by transport would have to be
edited twice and would drift.

`sizu_writer/generator.py` validates what comes back and refuses the answer,
raising `InvalidResponseError`, when:

- there is no choice in the response
- `finish_reason` says the output limit was reached, meaning the body was cut
  off partway
- the content does not parse as JSON, or parses as something other than an object
- `body_markdown` is missing, not a string, or blank (checked on `generate` only)
- `primary_title` is missing, not a string, or blank
- `alternative_titles` is not a list, or holds a value that is not a string

An empty `alternative_titles` is accepted; the requirement sets a maximum, not
a minimum. Blank entries, duplicates and repeats of `primary_title` are dropped,
and `MAX_ALT_TITLES` of the rest are kept. Renaming a field in a prompt without
renaming it in `generator.py` produces `InvalidResponseError` on every run.

## What surrounds the object

Under `prompt-json` one concession is made: an answer that is a single code
fence with the object inside it is unwrapped, because a model asked in words
for JSON wraps it routinely. Accepted:

````text
```json
{"body_markdown": "...", "primary_title": "...", "alternative_titles": []}
```
````

Refused, in both modes:

````text
Here is the draft you asked for.

```json
{...}
```
````

Nothing takes the first `{` and the last `}` out of free text. That heuristic is
the same one this design refuses everywhere else: an answer opening with "Here
are the title candidates you asked for" is a prompt that needs fixing, and
reading past the sentence would hide it. A prompt whose model keeps writing an
introduction is a prompt to change, not an answer to trim.

The output format sections of `system.md` and `titles_system.md` therefore say
in six ways what shape the answer takes — no prose, no code fence, nothing
before or after the object, the body and the titles in their own fields, and no
editing note inside the body field. Under `prompt-json` those sentences are all
that stands between the model and an unusable answer.

## Why a JSON object rather than prose

The body and the titles arrive as separate fields because the alternative is
splitting one block of prose by heuristic — take the first line as the title,
treat what follows as the body — and that heuristic is exactly what lets an
instruction leak into a post. A model that opens with "Here are the title
candidates you asked for" produces a post whose first line is that sentence.
Separate fields make the leak impossible to express: there is nowhere for the
remark to go except inside a field that is validated.

## Working on a prompt

Use `cli.py`, not the browser. The quality of the writing is settled from a
terminal, before any screen is involved: a browser adds a page load and a form
submission to every iteration and gives nothing back in return.

```sh
.venv/bin/python cli.py generate --input memo.txt
```

Keep a few real memos as files and run all of them after a change. A prompt
edit that improves one memo and ruins another is common, and it is invisible
when only one memo is ever tried.

To compare two policies without editing anything in place, copy the directory
and point `--prompt-dir` at the copy:

```sh
cp -r prompts prompts-plain
$EDITOR prompts-plain/system.md
.venv/bin/python cli.py generate --input memo.txt --prompt-dir prompts-plain
```

`--prompt-dir` replaces the whole set, not one file, so the copy must hold all
four. A missing file raises `InternalError` and the log names the path it could
not read.

`--json` prints the fields as the application sees them, which is what to look
at when the question is whether the model is filling the right field rather
than whether the writing is good:

```sh
.venv/bin/python cli.py generate --input memo.txt --json
```

Comparing models on the configured endpoint is the same command with `--model`:

```sh
.venv/bin/python cli.py generate --input memo.txt --model some-other-model
```

Comparing endpoints is not a command line option. `GENERATION_BASE_URL` and the
token belong to the deployment, so a second endpoint means a second `.env` —
which is the point: a run has one endpoint, and its log line says which.

Changing one thing per run is worth the discipline here. The output is prose,
so the difference between two runs is a matter of reading rather than of a
diff, and two simultaneous changes leave no way to say which one did it.

## The prompts are loaded once per request

`sizu_writer/prompts.py` reads the files on every call, so a prompt edited
while the development server runs takes effect on the next generation with no
restart. Under gunicorn the same holds, since each request reads the files
again; there is no cache to invalidate and no `PROMPT_RELOAD` setting to turn
on. The cost is four small reads per generation, next to an API call that takes
seconds.

## The Japanese in these files

`system.md` and `titles_system.md` are written in English, like the rest of the
repository, and they instruct the model to write in Japanese, because the
medium is.

Some phrases inside them are Japanese and have to be. The forbidden openings
and closings — 「今回は〜について書きます」, 「いかがだったでしょうか」 and the
rest — are quoted as the literal strings the model must not produce. Translating
them would leave the instruction describing a shape of English sentence that
never appears in a Japanese post, and the model would have nothing to match
against.

The wide subjects quoted in `system.md` — 「社会では」, 「人間は」, 「私たちは」 —
are Japanese for the same reason and are not forbidden strings. The instruction
around them asks the model to check that the text needs the move, not to avoid
the words, so they belong in the prompt only and not in the tables described
next.

The forbidden phrases appear again in `sizu_writer/formatter.py`, where they are
matched against the generated body so that a notice can be raised when one
slipped through. Adding a forbidden phrase to a prompt is therefore two edits:
the prompt tells the model not to write it, and `BOILERPLATE` or
`INSTRUCTION_LEAKS` in `formatter.py` catches it when the model does anyway.
The prompt alone changes what is asked for; the formatter alone changes what is
reported. Neither rewrites the sentence, because deciding that a sentence is
formulaic is not something that can be settled mechanically without touching
its meaning.
