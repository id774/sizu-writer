# sizu-writer

## Overview

**sizu-writer** turns a short memo — a passing thought, a small observation, a discomfort, a question, a short reflection — into a full post body and a set of title candidates for [Shizuka na Internet](https://sizu.me), a Japanese site for quiet, unhurried writing.

It does not post. The work of this system ends on the screen: a person copies the body and the title they chose, pastes them into the posting form, reads them once more and publishes. There is no code path to the posting site and no place to hand it a credential. That is a line drawn in the design, not a feature left for later; see [doc/POLICY](doc/POLICY).

The generation core is independent from Flask, so `app.py` and `cli.py` run exactly the same code. The quality of the output is settled with `cli.py`, before any screen is involved: prompts are what this kind of system iterates on, and iterating on them through a browser is slower for no gain.

The repository is written in English — the code, the comments, the screens, the documents and the prompts. Only the generated post is Japanese, because the medium is. The few Japanese strings that remain in the source are load bearing; see [The Japanese that stays](#the-japanese-that-stays).

- Requirements: [doc/REQUIREMENTS.md](doc/REQUIREMENTS.md)
- Basic design: [doc/BASIC_DESIGN.md](doc/BASIC_DESIGN.md)
- The generation API in detail: [doc/DETAILED_DESIGN_GENERATION_API.md](doc/DETAILED_DESIGN_GENERATION_API.md)
- The prompts: [doc/PROMPTS.md](doc/PROMPTS.md)
- Debian and Apache deployment: [doc/DEPLOYMENT.md](doc/DEPLOYMENT.md)
- Implementation policy: [doc/POLICY](doc/POLICY)

> **The `OPENAI_*` variables are refused.** Provider neutral `GENERATION_*` ones replaced them, and a process that still finds an `OPENAI_*` variable refuses to start. See [Coming from an earlier checkout](#coming-from-an-earlier-checkout).

## Features

- **One memo in, a postable draft out**: the whole body and the title candidates from a single generation
- **Any OpenAI compatible endpoint, named out loud**: Sakura AI Engine, OpenAI or another service, chosen by setting `GENERATION_BASE_URL`; there is no default endpoint and no fallback to one
- **Structured answer**: the endpoint is asked for a JSON object, so the body and the titles arrive as separate fields rather than being cut out of prose by heuristic
- **One action, one request**: retries default to zero, so a screen click or a CLI run costs exactly one request on a plan that counts them
- **The writing policy is not code**: `prompts/*.md` lives outside the Python package, so adjusting how the system writes needs neither a code change nor a reinstall
- **Copy without picking**: the body and each title have their own copy button, and the copied text never carries a label or an explanation from the screen
- **Regenerate at two scales**: the whole draft, or the titles alone against a body already settled
- **Mechanical cleanup only**: an outer code fence, a `#` heading and runs of blank lines are rewritten; anything that would touch the meaning of a sentence is reported as a notice instead
- **No state on the server**: the memo and the body travel with the form, so any worker answers any request and a restart loses nothing
- **The token stays in the process**: it reaches neither a template, nor JavaScript, nor an error page
- **Deployable as is**: `systemd` and Apache examples in [deploy/](deploy), a `Procfile` for a platform that wants one

## Requirements

- Python 3.9 or later
- A token for an endpoint speaking the OpenAI compatible Chat Completions API — Sakura AI Engine, OpenAI, or another service
- Outbound HTTPS access to that endpoint, and nothing else

No OpenAI account is needed. The `openai` package is used as the client for the protocol; which service answers is decided by `GENERATION_BASE_URL` and by nothing else.

Python dependencies are listed in `requirements.txt`:

| Package | Purpose |
|---|---|
| Flask | Web screens and Jinja2 templates |
| openai | Client of the OpenAI compatible Chat Completions protocol |
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

Four settings are required and none of them has a default: `GENERATION_BACKEND`, `GENERATION_API_TOKEN`, `GENERATION_BASE_URL` and `GENERATION_MODEL`. The shipped example is already filled in for Sakura AI Engine except for the token and the model; see [Choosing an endpoint](#choosing-an-endpoint). Every setting is documented in [.env.example](.env.example) and under [Configuration](#configuration).

The base URL is required rather than defaulted on purpose. A request that leaves for a service nobody named is worse than one that never leaves, so an unset endpoint stops the process instead of quietly becoming OpenAI's.

`chmod 600` is part of the step rather than an afterthought. The file holds a credential and is read by one service user. `.env` is ignored by Git and must never be committed.

### 5. Verify the installation

```sh
.venv/bin/python cli.py --version
.venv/bin/python -m unittest discover -s tests
```

The first command prints the version. The second runs the whole suite, which needs no network access, no API token and no `.env`; see [Tests](#tests). Neither command calls the API, so both pass before a token is configured — which is the point of running them first.

To confirm the token and the model as well, generate something small:

```sh
.venv/bin/python cli.py generate --text "A test memo."
```

## Configuration

All settings are read from environment variables, optionally through `.env`, and collected in `config.py`. An exported variable takes precedence over `.env`. A blank value is treated as unset and falls back to the default, so commenting a line out and emptying it mean the same thing.

| Variable | Default | Description |
|---|---|---|
| `GENERATION_BACKEND` | **required** | Wire protocol of the endpoint. `openai-compatible` is the only value this version accepts; an unknown one is refused rather than read as the default. |
| `GENERATION_API_TOKEN` | **required** | API key or Bearer token of the endpoint. A missing token is reported to the log and to the operator, never to the screen. |
| `GENERATION_BASE_URL` | **required** | Base URL of the endpoint, including the version path and stopping before the resource name. `https` only. |
| `GENERATION_MODEL` | **required** | Model used for generation. No default is shipped: the available models differ per endpoint and change over time. |
| `GENERATION_RESPONSE_MODE` | `prompt-json` | How a structured answer is asked for: `json-object` or `prompt-json`. See [Asking for JSON](#asking-for-json). |
| `GENERATION_TIMEOUT` | `120` | Seconds allowed for one request, which is the whole generation: nothing is streamed. Raising it means revisiting the two outer timeouts; see [Timeouts that agree with each other](#timeouts-that-agree-with-each-other). |
| `GENERATION_MAX_RETRIES` | `0` | Retries the SDK may spend on one request. `0` spends exactly one; see [One action, one request](#one-action-one-request). |
| `GENERATION_TEMPERATURE` | not sent | Sent only when set, so that a model refusing the parameter still runs. |
| `MAX_OUTPUT_TOKENS` | `6000` | Upper bound of one answer. Enough for a few thousand Japanese characters and the titles. |
| `MAX_INPUT_CHARS` | `4000` | Upper bound of the input field, enforced on the server as well as in the browser. |
| `MAX_ALT_TITLES` | `4` | Number of alternative titles kept, beyond the leading one. Lowering it takes effect on its own; raising it above 4 also needs `prompts/system.md` and `prompts/titles_system.md`, which ask the model for at most 4. |
| `PROMPT_DIR` | `prompts` | Directory holding the prompt files. Pointing it elsewhere replaces the writing policy as a whole. |
| `LOG_LEVEL` | `INFO` | Level of the application log. |
| `PORT` | `8090` | Port of the development server and of gunicorn. |

A malformed value raises `ConfigError` naming the variable, rather than falling back to the default. A setting that is silently ignored is worse than one that fails. The four required settings are checked before any request is made: `app.py` checks them while it is imported, so a worker that cannot address an endpoint never starts, and `cli.py` checks them before it reads the input. `cli.py --version` and the test suite need none of them.

`GENERATION_API_TOKEN` deliberately has no command line option: a command line is readable by every user of the host, through `ps`. The token stays in the environment or in `.env`. `GENERATION_BASE_URL` has none either, for a different reason — the endpoint is a decision of the deployment, not of an invocation.

### Choosing an endpoint

Any service speaking the OpenAI compatible Chat Completions API works. The base URL includes the version path and stops before `/chat/completions`, which the SDK appends itself; a URL that already carries it is refused at startup.

**Sakura AI Engine.** The token is the account token issued in the control panel, shaped `<UUID>:<secret>`; paste the whole string, colon included.

```env
GENERATION_BACKEND=openai-compatible
GENERATION_API_TOKEN=<UUID>:<secret>
GENERATION_BASE_URL=https://api.ai.sakura.ad.jp/v1
GENERATION_MODEL=<a model from the control panel>
GENERATION_RESPONSE_MODE=prompt-json
```

The free plan for foundational models covers 3,000 chat completion requests per month, and rate limits beyond that. Model names are read off the control panel's list of available models rather than copied from a document: models are added, renamed and withdrawn, and the closed models are outside the free allowance. That is why no default model is shipped and no model name appears anywhere in this repository.

**OpenAI.**

```env
GENERATION_BACKEND=openai-compatible
GENERATION_API_TOKEN=<OpenAI API key>
GENERATION_BASE_URL=https://api.openai.com/v1
GENERATION_MODEL=<model>
GENERATION_RESPONSE_MODE=json-object
```

OpenAI is one explicit endpoint among several here, not a privileged default. Nothing happens differently because that URL is the one configured.

**Anything else.** Same four settings, different values. Speaking the same API does not mean behaving the same way: when an endpoint refuses `temperature`, leave `GENERATION_TEMPERATURE` empty and nothing is sent; when it refuses `response_format`, use `prompt-json`; when it answers slowly, raise `GENERATION_TIMEOUT` and the two timeouts outside it. Change one setting per run, so that the run which succeeds says which setting did it.

**No fallback.** An authentication failure, a rate limit or a timeout never causes a request to a second endpoint. One generation uses one route, which is what keeps it answerable afterwards which service received the memo, which model replied, how many requests were spent and whose failure ended the run.

### Asking for JSON

The body and the titles arrive as separate fields of a JSON object. Splitting one block of prose by heuristic — first line is the title, the rest is the body — is exactly what lets an instruction leak into a post, and separate fields leave the leak nowhere to go. How that object is asked for is a setting, because endpoints differ:

| `GENERATION_RESPONSE_MODE` | Sent to the API | Answer accepted when |
|---|---|---|
| `prompt-json` (default) | nothing extra | the whole answer, or the inside of one outer code fence, parses as a JSON object |
| `json-object` | `response_format={"type":"json_object"}` | the whole answer parses as a JSON object |

`prompt-json` is the default because it works everywhere: an endpoint or a model that rejects `response_format` still answers. Use `json-object` where it is supported — it is the stronger of the two, and it costs nothing.

There is no `auto`. Sending `json-object`, having it refused and retrying with `prompt-json` would turn one generation into two requests, which is precisely what a plan counting requests punishes.

In both modes the prompt also states the contract in words, and both do work the other cannot. `response_format` is what makes an answer parse; the prompt is what keeps an editing note out of the body field. A model told only to return JSON will return valid JSON whose body opens with a remark about the instructions it was given.

Neither mode digs an object out of surrounding prose. An answer with a sentence before the JSON is refused rather than trimmed: reading past an explanation would hide the fact that the endpoint is answering the wrong way.

### One action, one request

`GENERATION_MAX_RETRIES` defaults to `0`, so one screen click or one CLI run is one request to the endpoint. On a plan that counts requests, that is the difference between a predictable monthly total and one that drifts.

| Action | Requests |
|---|---:|
| Generating a body and its titles | 1 |
| Regenerating the titles of a settled body | 1 |
| One SDK retry | 1 more |
| A resubmission in the browser | 1 each |

Raising the retries is a deliberate choice, and it also multiplies the worst case wait; see [Timeouts that agree with each other](#timeouts-that-agree-with-each-other).

Local counts are an estimate, not a ledger. A connection dropped at the wrong moment leaves it unknowable on this side whether the service accepted the request, and no monthly counter is written to disk, because the server holds no state. The endpoint's own control panel is the record.

### Timeouts that agree with each other

Three timeouts sit one inside the other, and they widen outwards:

| Timeout | Default | Set in |
|---|---|---|
| `GENERATION_TIMEOUT` | 120s | `.env` |
| gunicorn `--timeout` | 240s | the systemd unit, or the `Procfile` |
| Apache `ProxyTimeout` | 300s | the virtual host |

Raising `GENERATION_TIMEOUT` means raising the other two. A request cut off by Apache never reaches the error handling of Flask: the person sees a bare 504 from the proxy instead of the message the application would have shown, and the log carries no reference id to look up. Keep the order intact and the innermost timeout is always the one that fires.

Retries widen the same window, because the SDK spends the timeout again on each one:

```text
worst case wait = GENERATION_TIMEOUT × (GENERATION_MAX_RETRIES + 1)
```

At the default of zero retries that is 120 seconds, comfortably inside gunicorn's 240. Raising the retries to 2 makes it 360, which is already outside both — so the outer two move with it.

**Why the innermost one is 120 and not 60.** The request is not streamed: the client waits until the last character of the answer exists, so `GENERATION_TIMEOUT` is not a limit on the network but on the writing. What decides that wait is the length of the answer and the speed of the endpoint — a whole post of a few paragraphs plus five titles, from a model that may be sharing its hardware with everyone else on a free plan. The memo is a few dozen tokens of a prompt of a few thousand, so a one line memo and a four thousand character one ask for almost the same work. At 60 seconds that put ordinary generations on the wrong side of the limit and reported them as the person's fault. If your endpoint answers faster, lowering it again is a change to `.env` alone.

### Coming from an earlier checkout

The `OPENAI_*` settings are not read, and a process that finds one of them in its environment stops at startup naming its replacement:

```text
OPENAI_API_KEY is no longer supported; use GENERATION_API_TOKEN.
```

| Earlier checkout | Now |
|---|---|
| `OPENAI_API_KEY` | `GENERATION_API_TOKEN` |
| `OPENAI_BASE_URL` | `GENERATION_BASE_URL`, now required |
| `OPENAI_MODEL` | `GENERATION_MODEL` |
| `OPENAI_TIMEOUT` | `GENERATION_TIMEOUT` |
| `OPENAI_MAX_RETRIES` | `GENERATION_MAX_RETRIES`, now defaulting to `0` |
| `OPENAI_TEMPERATURE` | `GENERATION_TEMPERATURE` |

Two settings have no predecessor: `GENERATION_BACKEND`, which must be `openai-compatible`, and `GENERATION_RESPONSE_MODE`, which there was no choice about before — `response_format` was always sent, so `json-object` is the setting that reproduces that behaviour.

There is no automatic translation, no aliasing and no precedence rule, which is deliberate. A mixture of old and new settings would leave the endpoint to be guessed; a stale `OPENAI_API_KEY` exported in a shell must not be picked up silently; the path back to OpenAI's default URL has to be closed completely; and a break of this size belongs in the open. Presence is what is refused, whatever the value: an exported but empty `OPENAI_BASE_URL` still says the host was set up for the old settings.

Moving a host over is therefore: rewrite `.env` from [.env.example](.env.example), unset any `OPENAI_*` variable exported elsewhere (a systemd `EnvironmentFile`, a shell profile, a CI secret), and restart.

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
| `--model NAME` | `GENERATION_MODEL` |
| `--prompt-dir DIR` | `PROMPT_DIR` |
| `--timeout SECONDS` | `GENERATION_TIMEOUT` |

Each wins over the environment and `.env` for that invocation only:

```sh
.venv/bin/python cli.py generate --input memo.txt --model some-other-model
.venv/bin/python cli.py generate --input memo.txt --prompt-dir prompts-plain
```

The overrides are applied before the settings are checked, so `--model` can stand in for a `GENERATION_MODEL` that is not configured at all. `--timeout` is held to the same rule as `GENERATION_TIMEOUT` — a number greater than zero — and a value outside that ends the run with exit status 1 rather than reaching the endpoint. There is no option for the token or the base URL, for the reasons under [Configuration](#configuration).

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

Any other address answers 404, and a method an address does not accept answers 405. Both keep their own status rather than being reported as a server failure, so a browser asking for `/favicon.ico` costs a note in the log instead of a traceback.

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
| The generation service could not be reached. | 502 | DNS, network or a wrong `GENERATION_BASE_URL` |
| The generation service answered with an error. | 502 | A 4xx or 5xx answer: a bad token, no quota, a rate limit, an unknown model |
| Generation took too long and was stopped. | 504 | Over `GENERATION_TIMEOUT` |
| The result could not be read. | 502 | The answer was not the expected JSON object, or was cut off |
| That page does not exist. | 404 | An address the application does not serve |
| That address does not accept this kind of request. | 405 | The right address, the wrong method |
| The server failed to handle the request. | 500 | Anything unexpected, including a missing prompt file |

A misconfiguration never reaches this table, because the settings are checked before a request is made: the web process refuses to start and `cli.py` exits 1, each naming the setting at fault.

Every failed request also leaves one line naming the status the endpoint answered with. The screen does not distinguish them — writing "your token is invalid" onto a page is reporting the configuration of the server to whoever asked for a draft — but the log does, and the difference decides what to do next:

| Status | What to do |
|---|---|
| 401 | Replace `GENERATION_API_TOKEN`; it is not valid for this endpoint |
| 403 | The plan or the permissions do not cover this model |
| 429 | A rate limit, or the monthly allowance is used up. Wait, or check the control panel |
| 500 | The endpoint failed internally. Retry later |
| 504 | The endpoint timed out on its own side, before `GENERATION_TIMEOUT` fired |

Two cases are worth knowing by their log line rather than their screen:

**`The output was cut off (finish_reason=length); raise MAX_OUTPUT_TOKENS or shorten the input`** — the answer stopped partway, so the body is incomplete. A truncated post is not offered as a draft. Raise `MAX_OUTPUT_TOKENS`, or shorten a memo that was long enough to push the answer past it.

**`error=APITimeoutError ... elapsed=120.0 timeout=120.0`** — the endpoint was still writing when the limit fired. Every line carries the seconds the request actually took next to the limit it was given, on a successful answer as well as a failed one, and the two together say what to do. Elapsed at the limit means the endpoint is slower than the time allowed: raise `GENERATION_TIMEOUT` and the two timeouts outside it, or pick a faster model. Elapsed well short of it means the connection died on the way, and raising the limit changes nothing. Successful lines are the early warning — an answer that took 110 of 120 seconds is the same event as the timeout that follows it, one run earlier.

Shortening the memo is not the answer to this one, which is why the screen no longer suggests it. The wait is the answer being written, and a memo of one line asks for the same post as a long one.

**`The answer is not readable as JSON`** — the endpoint answered with something other than the object it was asked for. Under `json-object` that usually means the endpoint accepted `response_format` and ignored it; under `prompt-json` it usually means the model wrote a sentence around the object. Read the answer back with `cli.py generate --json` before changing a prompt.

Both `cli.py` and `app.py` log in the same format, so a failure reproduced from the command line reads the same as the one from the screen:

```
2026-08-05 09:42:01,727 INFO  sizu_writer.providers: generation response: backend=openai-compatible endpoint_host=api.ai.sakura.ad.jp request_id=... model=... finish_reason=stop prompt_tokens=... completion_tokens=... total_tokens=... elapsed=47.2 timeout=120.0
2026-08-05 09:42:44,913 ERROR sizu_writer.providers.openai_compatible: generation failure: backend=openai-compatible endpoint_host=api.ai.sakura.ad.jp model=... error=APIStatusError status=429 request_id=... elapsed=0.4 timeout=120.0: ...
```

The token, the memo, the prompts, the generated body and the titles appear at no level. What is left is the shape of the exchange, which is what matches a run against the usage the endpoint counted.

## Tests

The suite lives in `tests/` and uses `unittest` from the standard library. Every test stubs the client: no outbound access, no API token and no `.env` are needed. The provider tests go further and stub the `openai` package itself, so they exercise the request that would have been sent without importing the SDK at all.

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
| `test_config.py` | environment driven settings, blank values, refusal of a malformed value, refusal of a legacy `OPENAI_*` variable, the base URL rules, the token kept out of `repr` and out of every message |
| `test_openai_compatible_provider.py` | what reaches the SDK — token, base URL, retries, model, `max_tokens`, `response_format` per mode, `temperature` only when set — the normalization of an answer, and the mapping of a timeout, a connection failure and 401/403/429/500, and the elapsed seconds recorded next to the limit on both a success and a timeout |
| `test_generator.py` | building a `Draft` from a `CompletionResult`, both response modes, a fenced answer, refusal of prose around the object and of any fragment extraction, the title limit |
| `test_formatter.py` | fence removal, heading demotion, blank line collapsing, and detection that rewrites nothing |
| `test_web.py` | the screens, input limits, regeneration of the titles alone, that a failure does not expose its cause, and that a timeout does not blame the memo |
| `test_cli.py` | reading the memo from `--text` or `--input`, refusal of an empty one, the `--model` and `--timeout` overrides and the refusal of a timeout that is not positive, the exit codes, and the failure named in the log |

`test_web.py` sets the four required settings before importing `app`, because `app.py` validates them while it is imported. They are placeholders and no request is made; `setdefault` leaves a real `.env` alone when one is present.

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
│   ├── generator.py                the messages, the answer and the validation of a draft
│   ├── formatter.py                post processing and inspection of the body
│   ├── providers/
│   │   ├── __init__.py             the backend registry, CompletionResult, the log line
│   │   └── openai_compatible.py    the Chat Completions call and its failures
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
    ├── DETAILED_DESIGN_GENERATION_API.md   the generation path in detail
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

### Adding a backend

`providers/` holds everything that knows how an endpoint is spoken to: the SDK, the authentication, the base URL, the shape of a request and the exceptions the client raises. Above it, `generator.py` hands over a message list and receives a `CompletionResult`.

Supporting a genuinely different protocol — an Anthropic compatible Messages API, say — is three steps:

1. Write `sizu_writer/providers/<name>.py` with a class exposing `complete(messages, config) -> CompletionResult`, raising the `Upstream*` errors of `sizu_writer/errors.py`.
2. Register a loader for it in `BACKENDS` in `sizu_writer/providers/__init__.py`.
3. Add the value to `GENERATION_BACKENDS` in `config.py`, so the setting is accepted.

Nothing else changes. `generator.py` is untouched by a new backend, which is the point of `CompletionResult`: what a body and its titles have to look like is not a property of the wire protocol, so a second protocol must not be able to weaken it. A backend needing settings of its own adds new `GENERATION_*` variables rather than reinterpreting an existing one — a setting that means different things per backend cannot be validated in one place.

The registry holds loaders rather than classes, so importing `providers` does not import an SDK a deployment may not need. [doc/DETAILED_DESIGN_GENERATION_API.md](doc/DETAILED_DESIGN_GENERATION_API.md) documents the layer in full.

## The Japanese that stays

The repository is written in English. Four places keep Japanese because the strings themselves are the data:

| Where | Why |
|---|---|
| `sizu_writer/formatter.py` | `BOILERPLATE` and `INSTRUCTION_LEAKS` are matched against a Japanese post body. An English translation would match nothing. |
| `tests/test_formatter.py` | Its fixtures are Japanese bodies, because that is what the formatter is given. |
| `prompts/system.md` | The forbidden openings and closings are quoted as the literal strings the model must not produce, and the wide subjects it must not slide into are quoted the same way. |
| `doc/REQUIREMENTS.md`, `doc/BASIC_DESIGN.md` | The same phrases, quoted as specification. |

Everything else — comments, log messages, screen text, error messages, prompt instructions, documents — is English. The generated post is Japanese, and so is the memo the person writes; the elements carrying either are marked `lang="ja"` while the page itself is `lang="en"`.

## Not implemented yet

Parts of the basic design deliberately left for a later change:

- the space inserted between full width characters and ASCII (`BODY_ASCII_SPACING`)
- the `json_schema` response format mode, for endpoints supporting Structured Outputs; `json-object` and `prompt-json` are the two modes that exist
- a second backend in `providers/`; `openai-compatible` is the only one sizu-writer speaks
- the `Origin` check on POST (`REQUIRE_SAME_ORIGIN`)
- `LOG_PAYLOAD`, which would record the memo and the answer at DEBUG for prompt work
- persistence of the generated drafts (requirement 11, a future extension)

`PROMPT_RELOAD` appears in the basic design and is absent here for a different reason: it was to switch off a cache, and no cache was built. The prompts are read on every generation already, so the setting has nothing to control.

## Contribution

Contributions are welcome. You can help by:

- Improving the prompts, which is where the quality of the output actually lives
- Adding the parts listed under [Not implemented yet](#not-implemented-yet)
- Reporting bugs or feature requests

Please follow the style used in this repository: module level header comments describing purpose, requirements and version history, English comments, and documentation updated together with the code. [doc/POLICY](doc/POLICY) states the rules, including the invariants a change must not cross — above all, that nothing in this system posts to the site or holds a credential for it.

## License

This repository is dual licensed under the [GPL version 3](https://www.gnu.org/licenses/gpl-3.0.html) or the [LGPL version 3](https://www.gnu.org/licenses/lgpl-3.0.html), at your option.
For full details, please refer to the [LICENSE](doc/LICENSE) file. See also [COPYING](doc/COPYING) and [COPYING.LESSER](doc/COPYING.LESSER) for the complete license texts.
