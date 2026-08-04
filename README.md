# sizu-writer

## Overview

**sizu-writer** turns a short memo — a passing thought, a small observation, a discomfort, a question, a short reflection — into a full post body and a set of title candidates for [Shizuka na Internet](https://sizu.me), a Japanese site for quiet, unhurried writing.

It does not post. The work of this system ends on the screen: a person copies the body and the title they chose, pastes them into the posting form, reads them once more and publishes. There is no code path to the posting site and no place to hand it a credential. That is a line drawn in the design, not a feature left for later; see [doc/POLICY](doc/POLICY).

The generation core is independent from Flask, so `app.py` and `cli.py` run exactly the same code. The quality of the output is settled with `cli.py`, before any screen is involved: prompts are what this kind of system iterates on, and iterating on them through a browser is slower for no gain.

The repository is written in English — the code, the comments, the screens, the documents and the prompts. Only the generated post is Japanese, because the medium is. The few Japanese strings that remain in the source are load bearing; see [The Japanese that stays](#the-japanese-that-stays).

- Requirements: [doc/REQUIREMENTS.md](doc/REQUIREMENTS.md)
- Basic design: [doc/BASIC_DESIGN.md](doc/BASIC_DESIGN.md)
- The prompts: [doc/PROMPTS.md](doc/PROMPTS.md)
- Debian and Apache deployment: [doc/DEPLOYMENT.md](doc/DEPLOYMENT.md)
- Implementation policy: [doc/POLICY](doc/POLICY)

## Features

- **One memo in, a postable draft out**: the whole body and the title candidates from a single generation
- **Structured answer**: the endpoint is asked for a JSON object, so the body and the titles arrive as separate fields rather than being cut out of prose by heuristic
- **The writing policy is not code**: `prompts/*.md` lives outside the Python package, so adjusting how the system writes needs neither a code change nor a reinstall
- **Copy without picking**: the body and each title have their own copy button, and the copied text never carries a label or an explanation from the screen
- **Regenerate at two scales**: the whole draft, or the titles alone against a body already settled
- **Mechanical cleanup only**: an outer code fence, a `#` heading and runs of blank lines are rewritten; anything that would touch the meaning of a sentence is reported as a notice instead
- **No state on the server**: the memo and the body travel with the form, so any worker answers any request and a restart loses nothing
- **The key stays in the process**: it reaches neither a template, nor JavaScript, nor an error page
- **Deployable as is**: `systemd` and Apache examples in [deploy/](deploy), a `Procfile` for a platform that wants one

## Requirements

- Python 3.9 or later
- An API key for OpenAI, or for any endpoint speaking its Chat Completions API
- Outbound HTTPS access to that endpoint, and nothing else

Python dependencies are listed in `requirements.txt`:

| Package | Purpose |
|---|---|
| Flask | Web screens and Jinja2 templates |
| openai | Client of the OpenAI compatible endpoint |
| python-dotenv | Loading of the local `.env` file |
| gunicorn | Application server used in production |

Versions are pinned to a compatible range, so a future major release of any of them cannot break a running service.

## Installation

The following steps assume Debian or Ubuntu. Adjust the package manager commands for other systems.

### 1. Install the system packages

```sh
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

Nothing else is needed. This system draws no images and runs no browser, so there is no font package and no headless Chromium to install.

### 2. Clone the repository

```sh
git clone https://github.com/id774/sizu-writer.git
cd sizu-writer
```

### 3. Create a virtual environment and install the dependencies

```sh
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

### 4. Configure the environment

```sh
cp .env.example .env
chmod 600 .env
$EDITOR .env
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL`. Neither has a default: the key because there can be none, the model because a sensible one differs per endpoint. Every setting is documented in [.env.example](.env.example) and under [Configuration](#configuration).

`chmod 600` is part of the step rather than an afterthought. The file holds a credential and is read by one service user. `.env` is ignored by Git and must never be committed.

### 5. Verify the installation

```sh
.venv/bin/python cli.py --version
.venv/bin/python -m unittest discover -s tests
```

The first command prints the version. The second runs the whole suite, which needs no network access, no API key and no `.env`; see [Tests](#tests). Neither command calls the API, so both pass before a key is configured — which is the point of running them first.

To confirm the key and the model as well, generate something small:

```sh
.venv/bin/python cli.py generate --text "A test memo."
```

## Configuration

All settings are read from environment variables, optionally through `.env`, and collected in `config.py`. An exported variable takes precedence over `.env`. A blank value is treated as unset and falls back to the default, so commenting a line out and emptying it mean the same thing.

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | none | API key of the endpoint. Required at generation time. A missing key is reported to the log, never to the screen. |
| `OPENAI_BASE_URL` | none | Base URL of an OpenAI compatible endpoint, including the version path. Empty means OpenAI itself. |
| `OPENAI_MODEL` | none | Model used for generation. Required; no default is shipped. |
| `OPENAI_TIMEOUT` | `60` | Seconds allowed for one request. Raising it means revisiting the two outer timeouts; see [Timeouts that agree with each other](#timeouts-that-agree-with-each-other). |
| `OPENAI_MAX_RETRIES` | `2` | Retries the SDK may spend on one request. `0` spends exactly one, which is what comparing two endpoints needs. |
| `OPENAI_TEMPERATURE` | not sent | Sent only when set, so that a model refusing the parameter still runs. |
| `MAX_OUTPUT_TOKENS` | `6000` | Upper bound of one answer. Enough for a few thousand Japanese characters and the titles. |
| `MAX_INPUT_CHARS` | `4000` | Upper bound of the input field, enforced on the server as well as in the browser. |
| `MAX_ALT_TITLES` | `4` | Number of alternative titles kept, beyond the leading one. |
| `PROMPT_DIR` | `prompts` | Directory holding the prompt files. Pointing it elsewhere replaces the writing policy as a whole. |
| `LOG_LEVEL` | `INFO` | Level of the application log. |
| `PORT` | `8090` | Port of the development server and of gunicorn. |

A non numeric value given to a numeric setting raises `ValueError` at startup naming the variable and the value, rather than falling back to the default. A setting that is silently ignored is worse than one that fails.

`OPENAI_API_KEY` deliberately has no command line option: a command line is readable by every user of the host, through `ps`. The key stays in the environment or in `.env`.

### OpenAI compatible endpoints

Set `OPENAI_BASE_URL` to use any endpoint speaking the Chat Completions API:

```env
OPENAI_API_KEY=<key>
OPENAI_BASE_URL=https://api.example.net/v1
OPENAI_MODEL=some-model
```

The base URL includes the version path. The endpoint must accept `response_format={"type": "json_object"}` and produce a JSON object in the answer; see [The response format](#the-response-format).

Speaking the same API does not mean behaving the same way. When a compatible endpoint refuses `temperature`, leave `OPENAI_TEMPERATURE` empty and nothing is sent. When it answers slowly, raise `OPENAI_TIMEOUT` and the two timeouts outside it. Change one setting per run, so that the run which succeeds says which setting did it.

### The response format

Every request carries `response_format={"type": "json_object"}`, and the prompt asks for the same object again in words. The two do different work: the response format is what makes the answer parse, and the prompt is what keeps an editing note out of the body field. A model told only to return JSON will return valid JSON whose body opens with a remark about the instructions it was given.

The body and the titles arrive as separate fields for the same reason. Splitting one block of prose by heuristic — first line is the title, the rest is the body — is exactly what lets an instruction leak into a post. Separate fields leave the leak nowhere to go.

The design allows for stepping this down to a `json_schema` or to nothing at all, for endpoints that support more or less. `json_object` is fixed in this version; see [Not in this first version](#not-in-this-first-version).

### Timeouts that agree with each other

Three timeouts sit one inside the other, and they widen outwards:

| Timeout | Default | Set in |
|---|---|---|
| `OPENAI_TIMEOUT` | 60s | `.env` |
| gunicorn `--timeout` | 120s | the systemd unit, or the `Procfile` |
| Apache `ProxyTimeout` | 180s | the virtual host |

Raising `OPENAI_TIMEOUT` means raising the other two. A request cut off by Apache never reaches the error handling of Flask: the person sees a bare 504 from the proxy instead of the message the application would have shown, and the log carries no reference id to look up. Keep the order intact and the innermost timeout is always the one that fires.

## Usage

### From the command line

`cli.py` calls the same generation core as the web application, without starting Flask. It is where the prompts are adjusted and an endpoint verified.

```sh
.venv/bin/python cli.py generate --text "MEMO"
.venv/bin/python cli.py generate --input memo.txt
.venv/bin/python cli.py generate --input memo.txt --json
.venv/bin/python cli.py titles --input memo.txt --body draft.md
```

`generate` produces a body and its title candidates. `titles` produces candidates for a body that is already settled, and leaves that body untouched.

The memo comes from `--text` or from `--input`, one or the other. Human readable output prints the leading title as a `#` heading, the other candidates as a list, then the body; notices go to standard error, so redirecting standard output gives a clean draft:

```sh
.venv/bin/python cli.py generate --input memo.txt > draft.md
```

`--json` prints the whole `Draft` instead — body, titles, model, timestamp and notices — which is what to look at when the question is whether the model filled the right field rather than whether the writing is good.

The exit status is 0 on success, 1 when generation failed, and 2 when the command line itself was wrong.

### Overriding a setting for one run

| Option | Replaces |
|---|---|
| `--model NAME` | `OPENAI_MODEL` |
| `--prompt-dir DIR` | `PROMPT_DIR` |
| `--timeout SECONDS` | `OPENAI_TIMEOUT` |

Each wins over the environment and `.env` for that invocation only:

```sh
.venv/bin/python cli.py generate --input memo.txt --model gpt-4o
.venv/bin/python cli.py generate --input memo.txt --prompt-dir prompts-plain
```

`--prompt-dir` replaces the whole set of four prompts, not one file. Comparing two writing policies is a matter of copying the directory, editing the copy and pointing the option at it; see [doc/PROMPTS.md](doc/PROMPTS.md).

### The web screens

```sh
.venv/bin/python app.py     # http://127.0.0.1:8090
```

Enter a memo and generate. The result screen shows the leading title, the other candidates and the whole post body, each with its own copy button.

| Route | Method | Content |
|---|---|---|
| `/` | GET | Input screen |
| `/generate` | POST | Generate a draft, or the titles alone, and render the result |
| `/healthz` | GET | Liveness response; it calls no API |
| `/static/<file>` | GET | Stylesheet and the copy script |

Generation and regeneration share one endpoint, so the form always posts to the same place. Which one runs is decided by the submit button that was pressed.

The copy buttons use the clipboard API when the page is served over HTTPS, and fall back to selecting the text so that it can be copied by hand when it is not. A failure to copy leaves the text selected rather than silently doing nothing.

### The workflow end to end

1. Enter the memo and generate.
2. Read the body. Regenerate the whole draft if it went somewhere wrong.
3. Settle on the body, then regenerate the titles alone until one fits.
4. Copy the body, copy the title.
5. Paste both into the posting form of Shizuka na Internet.
6. Read it once more and publish.

Steps 5 and 6 are the person's. Nothing in this system reaches the posting site.

## The writing policy

What the system writes is decided by `prompts/*.md`, not by the Python around it. Four files: a system and a user prompt for `generate`, and the same pair for `titles`.

```
prompts/
├── system.md          the policy for the body and the titles
├── body_user.md       the user message carrying the memo
├── titles_system.md   the policy for regenerating the titles only
└── titles_user.md     the message carrying the body and asking for titles
```

They are read on every generation, so a prompt edited while the server runs takes effect on the next request with no restart.

The policy they encode comes from the requirements: keep the concrete scene and the writer's own wording, invent no experience or causal link to tidy the text, do not present a familiar theme as freshly discovered, add nothing to reach a length, and do not manufacture a conclusion where the thinking has not reached one.

[doc/PROMPTS.md](doc/PROMPTS.md) describes each file, the two placeholders, the JSON contract they must keep with `generator.py`, and how to iterate on a prompt without guessing which change did what.

## Notices

Some things about a draft can be noticed but must not be fixed automatically. `sizu_writer/formatter.py` rewrites only what is mechanical — an outer code fence, a `#` heading demoted to `##`, three or more blank lines collapsed to two — and reports the rest:

| Notice | Raised when |
|---|---|
| The heading level of the body was adjusted. | A `#` heading was demoted to `##`, outside a code fence |
| The body may contain a formulaic opening or closing. | A phrase the writing policy rules out is present |
| The body may contain a remark about the work itself. | A phrase that reads as an instruction or an editing note is present |

Notices appear outside the body area on the screen, and on standard error from `cli.py`, so they can never be copied along with the post. Deciding that a sentence is formulaic is not something that can be settled without touching its meaning, so the last two report and leave the text alone. A false positive costs a glance; a false rewrite costs a sentence.

## When something fails

The screen shows a message meant for the person and a short reference id. The cause, the endpoint, the model and the traceback stay in the log next to that same id, so an error page cannot leak internal information and a report of "it failed" is still traceable.

| What is shown | Status | Usually means |
|---|---|---|
| Enter a memo first. | 400 | The input was empty or blank |
| The memo is too long. | 400 | Over `MAX_INPUT_CHARS` |
| The generation service could not be reached. | 502 | DNS, network or a wrong `OPENAI_BASE_URL` |
| The generation service answered with an error. | 502 | A 4xx or 5xx answer: a bad key, no quota, a rate limit, an unknown model |
| Generation took too long and was stopped. | 504 | Over `OPENAI_TIMEOUT` |
| The result could not be read. | 502 | The answer was not the expected JSON object, or was cut off |
| The server failed to handle the request. | 500 | Anything unexpected, including a missing key or prompt file |

Two cases are worth knowing by their log line rather than their screen:

**`The output was cut off; raise MAX_OUTPUT_TOKENS or shorten the input`** — the answer stopped partway, so the body is incomplete. A truncated post is not offered as a draft. Raise `MAX_OUTPUT_TOKENS`, or shorten a memo that was long enough to push the answer past it.

**`api key missing` / `model missing`** — reported as an internal error, because from the reader's side that is what it is. The screen says only that the server failed; the log names which of the two is unset.

Both `cli.py` and `app.py` log in the same format, so a failure reproduced from the command line reads the same as the one from the screen:

```
2026-08-04 09:42:01,727 ERROR sizu_writer.generator: The output was cut off; raise MAX_OUTPUT_TOKENS or shorten the input
```

Neither the memo nor the generated text is logged at the default level.

## Tests

The suite lives in `tests/` and uses `unittest` from the standard library. Every test stubs the OpenAI client: no outbound access, no API key and no `.env` are needed.

Run everything at once, from the repository root:

```sh
.venv/bin/python -m unittest discover -s tests
```

It exits with status 0 only when all tests pass, which is what a CI step should check.

The repository root must be the working directory, because the tests import the top level modules (`config`, `app`, `sizu_writer`) from there. Running a file directly as `python tests/test_config.py` fails with `ModuleNotFoundError`, since then only `tests/` lands on the import path; always go through `python -m unittest`.

Narrower selections use the same runner:

```sh
.venv/bin/python -m unittest discover -s tests -v      # name every test as it runs
.venv/bin/python -m unittest tests.test_generator      # one module
.venv/bin/python -m unittest tests.test_config.LoadConfigTest
```

| Module | Subject |
|---|---|
| `test_config.py` | environment driven settings, blank values, refusal of a non numeric value, the key kept out of `repr` |
| `test_generator.py` | the API call, validation of the answer, the title limit, refusal of a truncated or malformed response |
| `test_formatter.py` | fence removal, heading demotion, blank line collapsing, and detection that rewrites nothing |
| `test_web.py` | the screens, input limits, regeneration of the titles alone, and that a failure does not expose its cause |

A passing suite says nothing about the endpoint being reachable or the writing being good. The first is exercised by an actual `cli.py generate`; the second cannot be decided by a test at all. The acceptance conditions about the quality of the writing — that no instruction leaks into the body, that it is not inflated into an explainer, and that a familiar theme is not presented as freshly discovered (requirements 14.7 to 14.9) — are settled by running a real memo through `cli.py generate` and reading the result.

## Deployment

gunicorn listens on `127.0.0.1` only. Apache provides HTTPS and access control.

[doc/DEPLOYMENT.md](doc/DEPLOYMENT.md) gives the complete Debian and Apache procedure.
[deploy/](deploy) holds the matching systemd unit and Apache virtual host examples.

The guide covers installation, TLS, reader restrictions, API compatibility and operations.

## Repository Structure

```
.
├── app.py                          Flask application (web entry point)
├── cli.py                          generation from the command line
├── config.py                       settings driven by the environment
├── requirements.txt
├── Procfile                        gunicorn invocation
├── .python-version
├── .env.example
├── sizu_writer/
│   ├── __init__.py                 the Draft dataclass and the version
│   ├── errors.py                   the exception hierarchy and the messages shown
│   ├── prompts.py                  reading prompts/ and assembling the messages
│   ├── generator.py                the API call and the validation of its answer
│   ├── formatter.py                post processing and inspection of the body
│   └── web/
│       ├── __init__.py             resolution of TEMPLATE_DIR and STATIC_DIR
│       ├── templates/
│       │   ├── base.html
│       │   ├── index.html          input screen
│       │   ├── result.html         result screen
│       │   └── error.html          error screen
│       └── static/
│           ├── style.css
│           └── copy.js             clipboard copying and nothing else
├── prompts/
│   ├── system.md                   the policy for the body and the titles
│   ├── body_user.md                the user message carrying the memo
│   ├── titles_system.md            the policy for regenerating the titles only
│   └── titles_user.md              the message carrying the body and asking for titles
├── deploy/
│   ├── sizu-writer.service         example systemd unit
│   └── sizu-writer.conf            example Apache reverse proxy configuration
├── tests/                          unittest suite, standard library only
└── doc/
    ├── REQUIREMENTS.md             requirements
    ├── BASIC_DESIGN.md             basic design
    ├── PROMPTS.md                  the prompt files and how to work on them
    ├── DEPLOYMENT.md               Debian, Apache and API integration
    ├── POLICY                      implementation policy
    ├── VERSIONS                    repository version history
    ├── LICENSE
    ├── COPYING
    └── COPYING.LESSER
```

`prompts/` sits outside the package on purpose: editing a prompt needs no reinstall, and `PROMPT_DIR` can point the system at an entirely different set.

`sizu_writer/` imports no Flask. That is what lets `cli.py` exercise the same code the screens do, and what keeps the test suite free of a web context.

## The Japanese that stays

The repository is written in English. Four places keep Japanese because the strings themselves are the data:

| Where | Why |
|---|---|
| `sizu_writer/formatter.py` | `BOILERPLATE` and `INSTRUCTION_LEAKS` are matched against a Japanese post body. An English translation would match nothing. |
| `tests/test_formatter.py` | Its fixtures are Japanese bodies, because that is what the formatter is given. |
| `prompts/system.md` | The forbidden openings and closings are quoted as the literal strings the model must not produce. |
| `doc/REQUIREMENTS.md`, `doc/BASIC_DESIGN.md` | The same phrases, quoted as specification. |

Everything else — comments, log messages, screen text, error messages, prompt instructions, documents — is English. The generated post is Japanese, and so is the memo the person writes; the elements carrying either are marked `lang="ja"` while the page itself is `lang="en"`.

## Not in this first version

Parts of the basic design deliberately left for a later change:

- the space inserted between full width characters and ASCII (`BODY_ASCII_SPACING`)
- the `json_schema` and `none` response format modes; `json_object` is fixed for now
- the `Origin` check on POST (`REQUIRE_SAME_ORIGIN`)
- `LOG_PAYLOAD`, which would record the memo and the answer at DEBUG for prompt work
- persistence of the generated drafts (requirement 11, a future extension)

`PROMPT_RELOAD` appears in the basic design and is absent here for a different reason: it was to switch off a cache, and no cache was built. The prompts are read on every generation already, so the setting has nothing to control.

## Contribution

Contributions are welcome. You can help by:

- Improving the prompts, which is where the quality of the output actually lives
- Adding the parts listed under [Not in this first version](#not-in-this-first-version)
- Reporting bugs or feature requests

Please follow the style used in this repository: module level header comments describing purpose, requirements and version history, English comments, and documentation updated together with the code. [doc/POLICY](doc/POLICY) states the rules, including the invariants a change must not cross — above all, that nothing in this system posts to the site or holds a credential for it.

## License

This repository is dual licensed under the [GPL version 3](https://www.gnu.org/licenses/gpl-3.0.html) or the [LGPL version 3](https://www.gnu.org/licenses/lgpl-3.0.html), at your option.
For full details, please refer to the [LICENSE](doc/LICENSE) file. See also [COPYING](doc/COPYING) and [COPYING.LESSER](doc/COPYING.LESSER) for the complete license texts.
