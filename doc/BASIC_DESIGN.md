# Basic design: a writing system for Shizuka na Internet

Requirements: [`REQUIREMENTS.md`](REQUIREMENTS.md) (2026-08-04).

This document takes the requirements down to units that can be implemented. Detailed design — the body of each function, the fine points of the CSS, the final wording of the prompts — follows the decisions made here. The system is developed in a new repository, and its design philosophy, coding rules and document layout are the ones stated in [`POLICY.md`](POLICY.md).

---

## 1. Repository name

| Candidate | Intent | Note |
| --- | --- | --- |
| **`sizu-writer`** (recommended) | A tool that writes for Shizuka na Internet | Matches the file name of the requirements document, so the name never drifts. Lowercase and hyphenated, like `ai-digest` |
| `sizu-draft` | Says in the name that the output is a draft, not a post | Puts the line this system draws into its name. Second choice |
| `quiet-writer` | The English reading of the medium | Does not age if the system later serves another medium, but loses what it is for |
| `sizuka-compose` | Names the medium and stresses assembling | Slightly long |
| `shizuka-writer` | Hepburn spelling | Overlaps `sizu-writer`; pick one |

**`sizu-writer`** is recommended, for three reasons.

- It carries over the name used in the requirements document (`20260804_sizu_writer_requirements.md`).
- The Python package `sizu_writer`, the systemd unit `sizu-writer.service` and the Apache location `/sizu/` all follow mechanically.
- Like `ai-digest`, it is "purpose plus action" in two words, so it does not stand out among the id774 repositories.

The rest of this document assumes the repository `sizu-writer` and the Python package `sizu_writer`. Changing the name means replacing those two and the file names under `deploy/`.

---

## 2. Design policy

### 2.1 The lines this system draws

From requirements 2, 13 and 14, the invariants come first. Neither a setting nor an extension crosses them.

1. Send nothing to the posting site. The only host an HTTP client here talks to is the generation endpoint the configuration names.
2. Accept no credential of the posting site. It exists neither as a setting nor as a form field.
3. Bring in no browser automation. `playwright` and `selenium` do not belong in `requirements.txt`.
4. Keep the API token inside the server process. It appears in no template, no JavaScript, no response header and no error page.
5. Let no instruction, editing note, internal remark or review result into the generated body. On the screen, the body area and the supporting area are separated structurally, not only visually.
6. Choose no endpoint implicitly. The base URL, the backend, the token and the model are all required, and a process missing one of them does not start. An endpoint reached because a setting was left blank is an endpoint nobody chose. (Added in the redesign.)
7. Fall back to no second endpoint. One generation uses one route, so which service received the memo and whose failure ended the run stay answerable. (Added in the redesign.)

### 2.2 What is inherited from ai-digest

The new repository also carries a `doc/POLICY.md`, and inherits the following. The one difference follows.

- The header block at the top of each module: Description, Routes (the web application only), the Author / Source Code / License / Contact block, Usage, Options, Exit Codes, Requirements, Environment Variables (`config.py` only), Version History.
- Comments in English, imperative, short.
- Settings collected in the `Config` dataclass of `config.py`, read from the environment (optionally from `.env`). `config.py` touches neither the network nor any file but `.env`.
- `logging` rather than `print`. Logging is configured once, at the entry point, and `INFO`, `WARNING` and `ERROR` keep their usual meanings.
- The CLI conventions: `-h`/`--help` and `-v`/`--version` through `argparse`, both exiting `0`, and exit codes documented in the module header.
- The shape of an executable: `#!/usr/bin/env python`, the UTF-8 encoding header, `main() -> int` and `sys.exit(main())`.
- Runtime dependencies pinned to a compatible range in `requirements.txt`.
- Tests in `tests/test_*.py`, `unittest` and `unittest.mock` only, with no network and no API call.
- Module versions as `major.minor`, `minor` carried over before it reaches 10, bumped for a change in behaviour and not for a documentation edit. Repository release versions are independent of them: they are recorded in `doc/VERSIONS`, may be three-level, are what a Git tag carries, and start at v1.0 with v1.0.1 after it. Work that is not released yet takes no version of its own.
- Python 3.9 or later, `str.format()` preferred over an f-string, type hints.
- Dual licensed under GPLv3 and LGPLv3.

The difference from ai-digest is this. ai-digest keeps the batch (`cli.py`) and the read only viewer (`app.py`) independent, so that a failed batch never takes the site down. Here the API is called inside a web request, so that separation does not hold. Instead, **the generation core (`sizu_writer/`) is independent from Flask, and both `app.py` and `cli.py` call it**. Adjusting a prompt and checking the output can then be done with `cli.py`, without a web server.

### 2.3 No state

Requirement 11 does not ask for persistence. This design uses that: **the server holds neither a session nor a temporary file**.

- The memo and the current body, both needed for a regeneration, ride on the result form as a `textarea` and a `hidden` field, and travel with each request.
- So Flask's `SECRET_KEY`, a session cookie and a store shared between workers are all unnecessary. Adding gunicorn workers or restarting the process changes nothing.
- Persistence is not implemented. Section 10.3 records only the boundary that a future persistence design must preserve.

---

## 3. System composition

```
[browser]
    |  HTTPS
    v
[Apache HTTP Server]
    |  - HTTPS termination, Basic auth / IP restriction (operational choice)
    |  - ProxyPass /  ->  127.0.0.1:8090
    |  - access and error logs stay on the Apache side
    v
[gunicorn]  managed by systemd, Restart=always, enabled at boot
    |  WSGI
    v
[Flask app.py]  ---- sizu_writer/ (generation core) ----> [GENERATION_BASE_URL]
                          ^
                          |
                     prompts/*.md
                          ^
                          |
                     [cli.py]  <- maintenance and prompt work
```

The generation core is itself in two layers, so that the transport can change without touching what a draft has to look like:

```
[sizu_writer/generator.py]        messages, and the object it expects back
        |
        v
[sizu_writer/providers/]          chosen by GENERATION_BACKEND
        |
        v
[GENERATION_BASE_URL]             Sakura AI Engine, OpenAI, or another
                                  OpenAI compatible service
```

- Apache and Flask are connected by **a reverse proxy in front of gunicorn**. Requirement 5.1 also allows `mod_wsgi`, but `mod_wsgi` ties the Apache build to a Python version and cannot replace the application without restarting Apache. Behind a reverse proxy, `systemctl restart sizu-writer` is enough, which matches the operation of ai-digest.
- gunicorn listens on `127.0.0.1` only, so nothing reaches it directly from outside.
- The Flask development server is for development. The `__main__` block of `app.py` binds `127.0.0.1` as well.

### 3.1 Timeouts that agree with each other

One generation can take tens of seconds, so the timeouts widen from the inside out.

| Layer | Setting | Default | Why |
| --- | --- | --- | --- |
| Generation client | `GENERATION_TIMEOUT` | 120s | The limit of one generation. The answer is not streamed, so this is the writing itself, not the network. Beyond it, the user is told it timed out |
| gunicorn | `--timeout` | 240s | The default client timeout plus headroom for request handling. Raising retries requires increasing this outer timeout |
| Apache | `ProxyTimeout` | 300s | The outermost layer. A request cut here never reaches the Flask error handling and returns a bare 504 |

Raising `GENERATION_MAX_RETRIES` means revisiting the gunicorn and Apache values, because the request budget is `GENERATION_TIMEOUT × (GENERATION_MAX_RETRIES + 1)` before SDK and application overhead. The default is 0 retries, so 120 seconds remains below gunicorn's 240. A retry does not fit inside 240 without increasing the outer timeout. The README states this dependency in its deployment section.

---

## 4. Repository layout

```
.
├── app.py                          Flask application (web entry point)
├── cli.py                          Generation from the command line (maintenance, prompt work)
├── config.py                       Settings driven by the environment
├── requirements.txt
├── Procfile                        gunicorn invocation
├── .python-version
├── .env.example
├── .gitignore
├── sizu_writer/
│   ├── __init__.py                 The Draft dataclass, __version__, shared helpers
│   ├── errors.py                   The exception hierarchy and the messages shown to the user
│   ├── prompts.py                  Reading prompts/ and assembling the messages
│   ├── generator.py                The messages, the answer and the validation of a draft
│   ├── formatter.py                Post processing and inspection of the body
│   ├── providers/                  How an endpoint is spoken to
│   │   ├── __init__.py             The backend registry and CompletionResult
│   │   └── openai_compatible.py    The Chat Completions call and its failures
│   └── web/
│       ├── __init__.py             Resolution of TEMPLATE_DIR and STATIC_DIR
│       ├── templates/
│       │   ├── base.html
│       │   ├── index.html          Input screen
│       │   ├── result.html         Result screen
│       │   └── error.html          Error screen
│       └── static/
│           ├── style.css
│           └── copy.js             Clipboard copying and nothing else
├── prompts/
│   ├── system.md                   The policy for the body and the titles
│   ├── body_user.md                The user message carrying the memo
│   ├── titles_system.md            The policy for regenerating the titles only
│   └── titles_user.md              The message carrying the body and asking for titles
├── tests/                          unittest, standard library only
├── deploy/
│   ├── sizu-writer.service         Example systemd unit
│   └── sizu-writer.conf            Example Apache reverse proxy configuration
└── doc/
    ├── REQUIREMENTS.md             Requirements
    ├── BASIC_DESIGN.md             This document
    ├── DETAILED_DESIGN_GENERATION_API.md   The generation path in detail
    ├── PROMPTS.md                  The prompt files and how to work on them
    ├── DEPLOYMENT.md               Debian, Apache and API integration
    ├── POLICY.md                   Implementation policy
    ├── VERSIONS                    Repository version history
    ├── LICENSE.md
    ├── COPYING
    └── COPYING.LESSER
```

`prompts/` sits outside the package so that requirement 10.3, keeping the prompt out of the application code, holds in operation too. Editing a prompt needs no reinstall, and pointing `PROMPT_DIR` elsewhere runs the system on a different set of prompts.

---

## 5. Module design

### 5.1 `sizu_writer/__init__.py`

Holds the dataclass of one result, and the version.

```python
@dataclass
class Draft:
    body: str                       # the whole post body (Markdown, post processed)
    primary_title: str              # the leading title
    alternative_titles: List[str]   # other candidates, at most MAX_ALT_TITLES
    model: str                      # the model that actually answered
    generated_at: str               # ISO 8601 time, shown only as supporting information
    notices: List[str]              # what the inspection found; never mixed into the body
```

`notices` carries findings such as "a `#` heading was demoted to `##`" or "a formulaic closing was detected". **They are shown outside the body area and are not part of what is copied** (requirement 6.3).

### 5.2 `sizu_writer/errors.py`

Each error of requirement 6.6 becomes a type. The message, the HTTP status and the log level live here.

```python
class SizuWriterError(Exception):
    """ Base of every error the user is allowed to see. """
    user_message: str
    status_code: int
```

| Exception | Condition | Message | HTTP | Log |
| --- | --- | --- | --- | --- |
| `EmptyInputError` | Empty or blank input | Enter a memo first. | 400 | INFO |
| `InputTooLongError` | Input beyond `MAX_INPUT_CHARS` | The memo is too long. Keep it within N characters. | 400 | INFO |
| `UpstreamConnectionError` | Connection, DNS or TLS failure | The generation service could not be reached. Try again in a while. | 502 | ERROR |
| `UpstreamTimeoutError` | Beyond `GENERATION_TIMEOUT` | Generation took too long and was stopped. Generate it once more, or try again in a while. | 504 | ERROR |
| `UpstreamStatusError` | 4xx / 5xx, auth failure, rate limit | The generation service answered with an error. Try again in a while. | 502 | ERROR |
| `InvalidResponseError` | Bad JSON, missing field, empty body, truncated output | The result could not be read. Generate it once more. | 502 | ERROR |
| `InternalError` | Any other unexpected failure | The server failed to handle the request. | 500 | ERROR |

These properties matter.

- **Only `user_message` reaches the screen.** The `str()` of the exception, the traceback, the URL, the model name and any fragment of the key stay in the server log.
- Each error answer carries an eight digit **reference id** (random per request), which also goes to the log. The user only has to quote "error id: 3f9c1a72" for the operator to find the entry.
- An authentication failure (401 / 403) and a rate limit (429) are not distinguished for the user. Writing a misconfiguration onto the screen is leaking internal information. The log does distinguish them.
- The provider logs an upstream status where it is known; `UpstreamStatusError` itself does not carry the status code.

### 5.3 `sizu_writer/prompts.py`

Its only job is reading the prompt files and assembling the messages. It performs no API call.

```python
def load_prompt(name: str, prompt_dir: str) -> str
def build_body_messages(input_text: str, prompt_dir: str) -> List[Dict[str, str]]
def build_titles_messages(input_text: str, body: str, prompt_dir: str) -> List[Dict[str, str]]
```

- The placeholders are `{{input}}` and `{{body}}` only, substituted with `str.replace()`. `str.format()` is avoided so that a brace appearing in a prompt does not have to be escaped. (The POLICY preference for `str.format()` concerns string building in code, not substitution into external text.)
- `load_prompt()` reads each prompt file on every generation, so prompt edits take effect without a restart.
- An unreadable prompt file is logged by path and raises `InternalError` when generation attempts to load it.

#### The shape of the prompt

`prompts/system.md` writes requirements 3, 7 and 8 out as instructions to the model, in these sections.

| Section | Requirement | Content |
| --- | --- | --- |
| Role and medium | 2, 7.1 | A piece of a few paragraphs for Shizuka na Internet; neither a stretched microblog post nor a shrunk article |
| What this is not | 3 | Not a primary source, a draft, material, a systematic essay, a survey, a how-to or an explainer. No point, evidence or generalization added for a future article |
| The grain of the material | 3 | What one line would exhaust stays short; what an article would argue is written as the memo carries it. Unfinished, inconclusive and personal are not faults |
| Stance | 7.2 | A familiar theme is not a discovery. Sort the thinking out, check where the interest lies, separate the points, state what can and cannot be said |
| Keeping the material | 7.3 | Keep the scene, the subject, the wording, the hesitation, the discomfort, the question, the unsettled. Invent no experience, emotion, fact or causal link |
| What you do not look up | 7.10 | No research, no references. What has not been checked is not stated as established |
| How much to explain | 7.4 | Background only as far as the text requires. No generalities, systems, glossary, history, case lists, bibliography or systematic argument. No move to a wide subject beyond what the observation supports |
| Shape | 7.9 | Three to six paragraphs, fewer when the material is short. The usual order given, to follow the material rather than be applied mechanically |
| Register | 7.5 | Desu/masu throughout, never the plain form, whichever form the memo uses; the memo's voice followed in every other respect. Not academic, advertising or social media. Avoid what is typical of generated text. No bait, no conclusion first, no keyword repetition, no call to act |
| Opening | 7.6 | Start from a concrete scene, subject, word or sensation. The forbidden openings are listed |
| Ending | 7.7 | No manufactured lesson, recommendation or conclusion. The undecided stays undecided, without reading as abandoned. The forbidden closings are listed |
| Markdown | 7.8 | No heading in a short text; `##` and `###` only when needed, never `#`. Lists, quotes and emphasis only where needed. A link only where the reader needs it, no bibliography. A space between full width characters and ASCII |
| Titles | 8 | Stay close to the scene, the subject, the words, the question, the point of attention, where the thinking started. No word for search, spread or clicks. Not settled looking, not symbolic, literary or sensational; a date when nothing else is natural |
| What matters most | 7.11 | The five points in order, the first three never given up for readability or notation |
| Output format | 5.3 | Follow the given JSON schema, keeping the body and the titles apart. No instruction or annotation inside the body |
| Before you answer | 3, 7 | A short recap of the checks that decide whether the answer is usable at all |

Length is written as an instruction that **sets no lower bound**: "a few paragraphs to a few thousand characters as a guide; do not add background, generalities, examples or a conclusion to reach a length; what holds in a short text stays short" (requirement 7.1).

`prompts/titles_system.md` takes only the title section and the position of the medium from the table above, and says nothing about writing the body, because the body is already settled when the titles alone are regenerated.

### 5.4 `sizu_writer/generator.py`

Validates the answer and returns a `Draft`.

```python
def generate_draft(input_text: str, config: Config) -> Draft
def regenerate_titles(input_text: str, body: str, config: Config) -> Draft
```

`generator.py` owns message assembly, JSON parsing, draft validation and `Draft`
construction. It delegates the request itself to `sizu_writer/providers/`
through `build_provider(config).complete(messages, config)`, and therefore knows
nothing about HTTP, authentication, the base URL or SDK exceptions.

#### 5.4.1 Calling the provider

`_complete()` calls `build_provider(config).complete(messages, config)`.
`GENERATION_BACKEND` selects the provider; the current accepted value is
`openai-compatible`.

The OpenAI-compatible provider sends `model`, `messages` and `max_tokens` on
every request. It sends `temperature` only when `GENERATION_TEMPERATURE` is set.
Under `GENERATION_RESPONSE_MODE=json-object` it also sends
`response_format={"type":"json_object"}`. Under
`GENERATION_RESPONSE_MODE=prompt-json` it sends no `response_format` parameter.
There is no automatic retry with another response mode and no fallback to a
second endpoint.

The provider maps SDK timeout, connection and status failures to the repository's
upstream exception types. It also refuses an answer with no choice, no usable
content, or a truncation finish reason before returning `CompletionResult` to
`generator.py`.

#### 5.4.2 The JSON object contract

For body generation the accepted object has this shape:

```json
{
  "body_markdown": "the generated Markdown body",
  "primary_title": "the leading title",
  "alternative_titles": ["another title"]
}
```

Title-only regeneration uses the same title fields and does not require
`body_markdown`.

`MAX_ALT_TITLES` is enforced by the application after parsing. Empty alternatives,
duplicates of `primary_title` and duplicates already kept are removed, and only
the first configured number of remaining alternatives is retained.

#### 5.4.3 Validating the answer

The provider first rejects a response with no choice, a truncation finish reason,
or no usable text. `generator.py` then applies the response-mode parsing rule:
`prompt-json` may unwrap one outer code fence, while `json-object` parses the
whole answer directly. In either mode the parsed value must be a JSON object.

For body generation, `body_markdown` must be a non-empty string. In both
generation modes, `primary_title` must be a non-empty string and
`alternative_titles` must be a list containing strings only. A violation raises
`InvalidResponseError` and is not turned into a partial draft.

#### 5.4.4 Retries

Retries belong to the SDK through `GENERATION_MAX_RETRIES`; there is no retry
loop in `generator.py` or in the provider. The default is zero retries, so a
normal screen action or CLI generation spends one request. A retry repeats the
same configured request and never changes the endpoint or response mode. The
outer timeout relationship is defined in section 3.1.

### 5.5 `sizu_writer/formatter.py`

Turns the model output into something postable. It rewrites only what can be
decided mechanically and never changes the meaning.

```python
def normalize_body(text: str) -> Tuple[str, List[str]]
```

The rewrites are:

1. Remove one outer code fence only when it wraps the whole body and there is no
   separate inner fence.
2. Demote a level-one Markdown heading to level two outside fenced code blocks,
   adding a notice when that happens.
3. Collapse three or more consecutive line breaks to a normal paragraph gap and
   strip surrounding whitespace.

After those rewrites the formatter only inspects. It adds a notice when the body
contains a configured boilerplate phrase or a phrase that looks like an
instruction leak, and it does not rewrite that sentence. Spacing between Japanese
text and ASCII belongs to the prompt policy described in section 5.3, not to the
formatter.

### 5.6 `app.py`

The Flask application. Four routes.

| Method | Path | Role |
| --- | --- | --- |
| GET | `/` | Input screen |
| POST | `/generate` | Generate and render the result; `mode` selects a whole draft or the titles only |
| GET | `/healthz` | Liveness; no API call |
| GET | `/static/<file>` | CSS and JS |

- Generation and regeneration share one endpoint, so the form always posts to the same place and the branching stays in the template. `mode` comes from the `name`/`value` of the submit button (`mode=full` / `mode=titles`).
- The POST renders the result directly, without PRG. The server holds no state, so there is nothing to carry to a redirect target. Reloading the result asks for a resubmission, and a resubmission is "regenerate from the same input", which destroys nothing.
- `SizuWriterError` is caught by an `errorhandler` and drawn on `error.html` (or in the error area of the result screen) as `user_message` plus the reference id. An unexpected exception is wrapped in `InternalError` and takes the same path. `DEBUG` is off in production and `app.config["PROPAGATE_EXCEPTIONS"]` is left alone, so no traceback reaches the screen.
- `MAX_CONTENT_LENGTH` is set in `app.py` to 1 MiB and keeps an oversized POST from reaching the application logic.
- An address the application does not serve answers 404, and a method an address does not accept answers 405, each on `error.html` with wording of its own. Flask looks a handler up along the class hierarchy, so without one for `HTTPException` a routing failure reached the handler for `Exception`: a browser asking for `/favicon.ico` was logged as a traceback and answered 500. A page that is not there is not a failure of the server.

### 5.7 `cli.py`

Calls the same core without the web. Used for prompt work, for verifying a compatible endpoint and for acceptance checks. Following POLICY: `main() -> int`, `sys.exit(main())`, `-h` and `-v`.

```sh
python cli.py generate --input memo.txt          # read a file, print the result
python cli.py generate --text "a short thought"  # pass it directly
python cli.py generate --input memo.txt --json   # print the Draft as JSON (tests, pipes)
python cli.py titles --input memo.txt --body draft.md   # regenerate the titles only
```

As in ai-digest, the main settings can be overridden by options of the same name (`--model`, `--timeout`, `--prompt-dir`). **No option exists for a credential**: a command line is readable by others.

Exit codes, as POLICY prescribes: `0` success, including `-h` and `-v`; `1` failure, a refused setting or a generation that produced no draft; `2` a command line argparse rejected. The list is repeated in the header of `cli.py`.

---

## 6. Settings

`config.py` is the single implementation source for runtime setting names,
defaults and validation. The operator-facing copy is the Configuration table in
README.md; this basic design does not maintain a second table of the same current
defaults.

The endpoint identity is explicit: `GENERATION_BACKEND`,
`GENERATION_API_TOKEN`, `GENERATION_BASE_URL` and `GENERATION_MODEL` are required
before a generation request can be made and have no implicit endpoint fallback.
`GENERATION_RESPONSE_MODE`, `GENERATION_TIMEOUT`, `GENERATION_MAX_RETRIES` and
`GENERATION_TEMPERATURE` shape the request. `MAX_OUTPUT_TOKENS`,
`MAX_INPUT_CHARS`, `MAX_ALT_TITLES`, `PROMPT_DIR`, `LOG_LEVEL` and `PORT` shape
the application around it.

`load_config()` parses and validates values that are meaningful on their own.
`validate_generation_config()` refuses a configuration that cannot address the
selected endpoint. This separation lets `cli.py --version` and the offline test
suite run without a token while every path that reaches generation validates the
endpoint first.

Legacy `OPENAI_*` settings are refused by `config.py`; they are not translated
into the current names.

---

## 7. Screens

### 7.1 Shared

- `base.html` carries `index.html`, `result.html` and `error.html`, as in ai-digest.
- The CSS uses system fonts only and makes no external request. A `max-width` and a single column serve both a phone and a desktop (requirement 10.4). One breakpoint, stacking the buttons on a narrow screen, is enough.
- The page declares the light color scheme, and every foreground color it relies on is stated beside its background rather than left to a system color. A phone in dark appearance otherwise renders the form controls with its own colors, which is what put white button labels on the near-white button background.
- The only JavaScript is `copy.js`. Generation and navigation work as plain HTML forms; with JavaScript disabled, nothing degrades except the copy buttons.
- After the generate button is pressed, it is disabled and a waiting state is shown, to prevent a double submission (with JavaScript only; without it the submission still works).

### 7.2 Input screen (`/`)

| Element | Specification |
| --- | --- |
| Page title | The name of the service and a one line description |
| Memo field | `<textarea name="input_text">`, several paragraphs, about 12 rows initially, resizable, `maxlength` of `MAX_INPUT_CHARS` |
| Character count | The current count and the limit (with JavaScript only; without it the server checks) |
| Generate button | `<button name="mode" value="full">` |
| Clear button | Not `type="reset"`, which restores the initial value rather than clearing the field; it empties the field and returns the focus |

### 7.3 Result screen (the answer of `/generate`)

From top to bottom. **What is posted and what merely supports it are separated visually and in the DOM** (requirement 10.4).

1. **The leading title**: a label, the title, a copy button beside it.
2. **Other candidates**: a title and its own copy button per row. The section disappears when there are none.
3. **Regenerate the titles**: `<button name="mode" value="titles">`, leaving the body as it is.
4. **The post body**: a heading, then a `readonly` `<textarea>` holding the Markdown as it is.
   - `readonly` for three reasons: line breaks and Markdown are not lost to visual rendering; the text can be selected by hand when a copy button fails (requirement 9.3); and no label or explanation can slip in structurally (requirement 6.3).
   - It grows with the content, to minimize scrolling.
5. **Copy the body**: copies the value of the textarea only.
6. **Notices**: outside the body area, below it. Empty means hidden.
7. **Regenerate the whole draft**: `<button name="mode" value="full">`.
8. **The memo**: inside a `<details>`, an editable `<textarea name="input_text">` holding this run's input. Editing it and regenerating avoids a trip back to the input screen. A "start a new one" link (`GET /`) sits next to it (requirement 9.2).
9. **Supporting information**: the model name and the time of generation, in small type.

What the result form carries for a regeneration:

| Field | Kind | Use |
| --- | --- | --- |
| `input_text` | `textarea` (inside the details) | Sent by both regenerations |
| `body` | `hidden` | The current body, handed to the model when only the titles are regenerated |
| `mode` | The value of the submit button | `full` / `titles` |

### 7.4 Copying (`copy.js`)

```
click
  -> navigator.clipboard.writeText(value)      // secure context
     success -> show "Copied" beside the button for 2 seconds
     failure -> fall back
  -> fallback: select the target and document.execCommand('copy')
     success -> as above
     failure -> show "Could not copy. Select the text and copy it by hand." and keep the selection
```

- Over HTTP (not a secure context) `navigator.clipboard` is unavailable, so the fallback is required. Publication assumes HTTPS, but the system stays usable over HTTP on a LAN.
- What is copied is the `value` (a `textarea`) or the `textContent` (a title) of the element named by `data-copy-target`. A label, a button caption or a notice lies outside that element and cannot be copied.

### 7.5 Errors

- An error caused by the input (empty, too long) re-renders the input screen with the input intact and the message on top. The input is not thrown away.
- An error caused by the generation renders `error.html` while keeping the last input (and the body, for a title regeneration), so that it can be tried again.
- Only `user_message` and the reference id are shown.

---

## 8. Non functional design

### 8.1 Security

- The generation API token comes from the environment of the server process (or from `.env`, mode `600`, owned by the service user). It is not handed to a template. `Config.__repr__` hides it.
- When published, Apache terminates HTTPS. Basic authentication, IP restriction and a VPN are operational choices; `deploy/sizu-writer.conf` holds a commented template.
- gunicorn listens on `127.0.0.1` only.
- `MAX_CONTENT_LENGTH` and `MAX_INPUT_CHARS` bound the input.
- The body is shown as the value of a `textarea`, so with Jinja2 autoescaping no HTML from the model is ever executed. **Rendering model output with `|safe` is forbidden by design.**
- Rate limiting is not implemented in the application: it cannot count across gunicorn workers and would not hold. Use Apache (`mod_ratelimit`, `mod_qos`) or authentication. The README states this decision.
- No internal information on an error page (section 5.2).

### 8.2 Availability

- systemd keeps it running. The essentials of `deploy/sizu-writer.service`:

```ini
[Service]
Type=simple
User=sizu
WorkingDirectory=/opt/sizu-writer
EnvironmentFile=/opt/sizu-writer/.env
ExecStart=/opt/sizu-writer/.venv/bin/gunicorn app:app \
          --bind 127.0.0.1:8090 --workers 2 --timeout 240
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- `Restart=always` brings the process back, and `systemctl enable` starts it after a reboot (requirement 10.2).
- `/healthz` answers immediately without calling the API, so monitoring costs nothing.
- On an API failure there is no subsequent step; the error is returned and that is the end. Retrying is the user's decision (requirement 10.2).

### 8.3 Maintainability

- The prompts live outside the code (`prompts/*.md`). The model name, the timeout and the output limit are environment variables (section 6).
- The HTML templates, the CSS, the JS, the Python and the prompts are separate files (section 4).
- The application log goes to stderr and lands in the systemd journal, in a different file and a different process from the Apache log (requirement 10.3). The format is that of ai-digest: `%(asctime)s %(levelname)s %(name)s: %(message)s`.
- Persistence is not implemented. The current `Draft` carries the generated body, titles, model, generation time and notices; the memo remains on the request/form path. Neither is written to durable storage. Requirement 11 leaves persistence to a future design.

### 8.4 Usability

- One input and one click yield the whole body and the title candidates (requirement 10.4).
- Posting is "copy the body, paste, copy a title, paste, read, publish".
- A single column layout, with no horizontal scrolling on a phone.

---

## 9. Test design

The test suite uses `unittest` under `tests/` and performs no live network call.
The current test inventory and exact assertions live in the test files rather
than being duplicated here.

- `test_config.py` covers setting parsing, required generation configuration,
  legacy-name refusal and base-URL validation.
- `test_generator.py` covers JSON parsing, draft validation, title filtering and
  the two response modes independently of network transport.
- `test_openai_compatible_provider.py` covers the Chat Completions request,
  response normalization and mapping of timeout, connection and status failures.
- `test_formatter.py` covers the mechanical body rewrites and notices.
- `test_web.py` covers routes, rendering, user-visible failures and the health
  endpoint without a live generation service.
- `test_cli.py` covers command-line input, overrides and exit status behavior.

Writing-quality acceptance remains a manual check through `cli.py generate`;
the offline test suite verifies the software contract, not whether a generated
post reads well.

---

## 10. Mapping to the requirements

### 10.1 Scope of the initial implementation (requirement 12)

| Requirement | Where |
| --- | --- |
| 1. Apache and Flask | Section 3, `deploy/sizu-writer.conf`, `deploy/sizu-writer.service` |
| 2. Input screen | Section 7.2, `index.html` |
| 3. Generation through the configured OpenAI-compatible endpoint | Sections 5.4 and 6, `generator.py`, `providers/` |
| 4. Showing the whole body | Section 7.3 item 4, `result.html` |
| 5. Showing the titles | Section 7.3 items 1 to 2 |
| 6. Copying the whole body | Section 7.3 item 5, section 7.4 |
| 7. Copying each title | Section 7.3 items 1 to 2, section 7.4 |
| 8. Regenerating the whole text | Section 7.3 item 7, `mode=full` |
| 9. Regenerating the titles only | Section 7.3 item 3, `mode=titles`, `regenerate_titles()` |
| 10. Basic error handling | Sections 5.2 and 7.5 |
| 11. The generation API token on the server | Sections 6 and 8.1 |

### 10.2 Acceptance conditions (requirement 14)

| Condition | How the design holds it |
| --- | --- |
| 1. A short text can be entered | Section 7.2 |
| 2. Generate calls the configured generation endpoint | Section 5.6 `POST /generate` -> section 5.4 |
| 3. The whole body is shown | Section 7.3 item 4 |
| 4. It can be copied and pasted as it stands | The Markdown held in a `textarea`, section 7.4 |
| 5. The leading title and several candidates are shown | The schema of section 5.4.2, section 7.3 items 1 to 2 |
| 6. The body and each title can be copied individually | Section 7.4; what is copied is limited to the `data-copy-target` element |
| 7. No internal instruction leaks into the body | The separate field of section 5.4.2, the inspection of section 5.5, the separation of section 7.3 |
| 8. No inflation into an explainer or an essay | "What this is not" and "How much to explain" in section 5.3, the absence of a lower bound in 7.1 |
| 9. A familiar theme is not a discovery | "Stance" in section 5.3 |
| 10. Copy, paste and read is enough to post | Section 8.4 |
| 11. Nothing is posted automatically | Invariants 1 to 3 of section 2.1; no path to the posting site exists in the code |
| 12. The generation API token never reaches the browser | Invariant 4 of section 2.1, section 8.1 |

### 10.3 Persistence boundary (requirement 11)

Persistence is not part of the current implementation. Requirement 11 permits a
later persistence feature but does not define a current storage module, storage
path, route or file format. A future persistence design must keep the generation
core separate from storage and must not cross the invariant that this system
never posts to Shizuka na Internet.

---
