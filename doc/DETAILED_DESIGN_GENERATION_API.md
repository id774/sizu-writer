# Detailed design: the generation API

- Repository: `id774/sizu-writer`
- Version: v1.0
- Written: 2026-08-05
- First endpoint supported: Sakura AI Engine, free plan for foundational models
- Protocol: OpenAI-compatible Chat Completions

This document takes [`BASIC_DESIGN.md`](BASIC_DESIGN.md) down to the level the
generation path is actually implemented at. It covers the settings, the
provider layer, the response modes, the error mapping and the tests. Everything
outside the generation path — the screens, the formatter, the prompt policy —
is unchanged and stays in the basic design.

---

## 1. Purpose

sizu-writer must not assume that the endpoint it talks to belongs to OpenAI.
Any service speaking the OpenAI-compatible Chat Completions API is a candidate,
and which one answers is a decision of the deployment, stated explicitly.

The first service supported this way is Sakura AI Engine, on its free plan for
foundational models.

The design holds these conditions:

1. sizu-writer runs without an OpenAI API key.
2. A Sakura AI Engine account token authenticates against that service's
   OpenAI-compatible Chat Completions API.
3. An unnamed endpoint is never filled in with OpenAI's.
4. One generation uses one API route, and never falls back to another.
5. Differences between compatible endpoints are configured, not guessed.
6. A limited request allowance is not spent on retries nobody asked for.
7. The existing body generation, title generation, JSON validation, error
   screens, CLI and web UI keep their responsibilities.

## 2. Background

Before this design, sizu-writer read `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
`OPENAI_MODEL`, `OPENAI_TIMEOUT`, `OPENAI_MAX_RETRIES` and
`OPENAI_TEMPERATURE`. Setting a base URL was already enough to reach a
compatible endpoint, so the transport was close to what was needed. Six things
were not:

1. The names read as OpenAI's, blurring the difference between the company's
   service and the protocol its SDK speaks.
2. A blank `OPENAI_BASE_URL` meant OpenAI, so a deployment could address an
   endpoint without ever naming it.
3. `response_format={"type": "json_object"}` was always sent, which rules out a
   compatible endpoint or a model that refuses the parameter.
4. The SDK default of two retries turned one screen action into up to three
   requests.
5. The transport and the validation of a draft shared `generator.py`, so adding
   a second protocol would have touched both.
6. Even for a deployment never calling OpenAI, the settings, the log and the
   documents read as though OpenAI were the default.

Sakura AI Engine offers an OpenAI-compatible Chat Completions API and
authenticates with an account token used as a Bearer token. Its free plan for
foundational models allows 3,000 chat completion requests per month, and rate
limits beyond that.

## 3. Design decisions

### 3.1 The SDK is not the endpoint

The `openai` package stays as the client. Using it and talking to OpenAI the
company are separate facts, and only the first is true by default. Setting
names, module names and log lines therefore say `GENERATION_*` and
`openai-compatible`, never "OpenAI" as a synonym for "the endpoint".

The service that answers is decided by `GENERATION_BASE_URL` alone.

### 3.2 The endpoint is required

`GENERATION_BASE_URL` has no default. An empty value is a configuration error,
refused when the web process starts and before a CLI subcommand runs. It is
never completed into OpenAI's URL.

A deployment that does want OpenAI writes `https://api.openai.com/v1`, like any
other endpoint.

### 3.3 The backend is named

`GENERATION_BACKEND` is required, and one value is accepted.

| Value | Meaning |
| --- | --- |
| `openai-compatible` | Speak the OpenAI-compatible Chat Completions API |

A future Anthropic-compatible Messages API would be a new value and a new
provider module. An unknown value is refused; it is never read as the default
one.

### 3.4 No automatic fallback

An authentication failure, a rate limit, a timeout or an unusable answer from
the configured endpoint does not cause a request to a different one.

One generation corresponds to one API route, which keeps five questions
answerable after the fact:

- which endpoint received the memo
- which model answered
- how many requests were made
- whose allowance they counted against
- whose failure ended the run

### 3.5 Compatibility differences are settings

Nothing is inferred from a model name or a URL. How a structured answer is
asked for is stated by `GENERATION_RESPONSE_MODE`.

| Value | Sent to the API | Answer accepted when |
| --- | --- | --- |
| `json-object` | `response_format={"type":"json_object"}` | the whole answer parses as a JSON object |
| `prompt-json` | nothing extra | the whole answer, or the inside of one outer code fence, parses as a JSON object |

There is no `auto`. Sending `json-object`, having it refused and retrying with
`prompt-json` would make one generation cost two requests, which is exactly
what a plan counting requests punishes.

### 3.6 Retries are budgeted

`GENERATION_MAX_RETRIES` defaults to `0`, so one screen action or one CLI run
is normally one SDK request. An operator who wants resilience against a
transient network failure raises it deliberately, and revisits the outer
timeouts at the same time (section 12).

---

## 4. Scope

**In scope.** Switching the OpenAI-compatible endpoint; Sakura AI Engine
account token authentication; the models the free plan for foundational models
covers; the structured response mode; configuration validation; separation of
the transport; response normalization; error classification; logging; unit
tests; and the README, `.env.example`, design documents and version history.

**Out of scope.** The Anthropic-compatible Messages API; the Responses API; the
RAG API; embeddings; speech to text; text to speech; sending to several
endpoints at once; automatic fallback; automatic comparison of models; storing
a monthly request count locally; computing a charge; managing a Sakura AI
Engine subscription; posting to the publishing site; and entering a token in
the browser.

---

## 5. External facts

### 5.1 Sakura AI Engine

The OpenAI-compatible Chat Completions resource is:

```text
https://api.ai.sakura.ad.jp/v1/chat/completions
```

The value handed to the SDK as `base_url` stops before the resource name:

```text
https://api.ai.sakura.ad.jp/v1
```

The account token issued in the control panel is shaped:

```text
<UUID>:<secret>
```

The whole string, colon included, becomes the `api_key` of the client, and the
SDK sends it as:

```text
Authorization: Bearer <UUID>:<secret>
```

### 5.2 The free allowance

The free plan for foundational models covers 3,000 chat completion requests per
month. In sizu-writer:

| Action | Requests |
| --- | ---: |
| Generating a body and its titles | 1 |
| Regenerating the titles of a settled body | 1 |
| One SDK retry | 1 more |
| A resubmission in the browser | 1 each |

Even at `GENERATION_MAX_RETRIES=0`, a connection dropped at the wrong moment
leaves it unknowable locally whether the service accepted the request. Local
success counts are an estimate; the control panel is the record.

### 5.3 Model names

No default model is shipped, and no preview name is written into this
repository. Models are added, renamed and withdrawn, and a name frozen into a
document is wrong soon afterwards.

Read the name off the endpoint's own list of available models and put it in
`GENERATION_MODEL`. On the Sakura AI Engine free plan, pick a foundational
model the free allowance covers; the closed models are outside it.

---

## 6. Composition

```text
[browser]
    |
    v
[Apache] -> [gunicorn] -> [Flask app.py]
                              |
                              v
                    [sizu_writer/generator.py]
                              |  messages, and the object it expects back
                              v
                 [sizu_writer/providers/__init__.py]
                              |  chosen by GENERATION_BACKEND
                              v
              [sizu_writer/providers/openai_compatible.py]
                              |  HTTPS
                              v
                     [GENERATION_BASE_URL]
                              |
                              +-- Sakura AI Engine
                              +-- OpenAI
                              +-- any other OpenAI-compatible API
```

One process addresses one endpoint, fixed at startup. Neither the endpoint, the
model nor the token can be changed from a screen.

---

## 7. Layout

```text
.
├── app.py
├── cli.py
├── config.py
├── .env.example
├── sizu_writer/
│   ├── __init__.py
│   ├── errors.py
│   ├── generator.py
│   ├── formatter.py
│   ├── prompts.py
│   └── providers/
│       ├── __init__.py            the choice, CompletionResult, the log line
│       └── openai_compatible.py   the SDK call and its failures
├── tests/
│   ├── test_config.py
│   ├── test_generator.py
│   └── test_openai_compatible_provider.py
└── doc/
    ├── REQUIREMENTS.md
    ├── BASIC_DESIGN.md
    ├── DETAILED_DESIGN_GENERATION_API.md   this document
    ├── PROMPTS.md
    ├── DEPLOYMENT.md
    ├── POLICY
    └── VERSIONS
```

---

## 8. Settings

### 8.1 The variables

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `GENERATION_BACKEND` | yes | none | `openai-compatible` only |
| `GENERATION_API_TOKEN` | yes | none | API key or Bearer token of the endpoint |
| `GENERATION_BASE_URL` | yes | none | Base URL. Required so that no endpoint is implied |
| `GENERATION_MODEL` | yes | none | Model name as the endpoint spells it |
| `GENERATION_RESPONSE_MODE` | no | `prompt-json` | `json-object` or `prompt-json` |
| `GENERATION_TIMEOUT` | no | `120` | Seconds for one request, which is the whole generation |
| `GENERATION_MAX_RETRIES` | no | `0` | Retries left to the SDK |
| `GENERATION_TEMPERATURE` | no | not sent | Sent only when set |
| `MAX_OUTPUT_TOKENS` | no | `6000` | Upper bound of one answer |
| `MAX_INPUT_CHARS` | no | `4000` | Upper bound of the input field |
| `MAX_ALT_TITLES` | no | `4` | Alternative titles kept |
| `PROMPT_DIR` | no | `prompts` | Where the prompts live |
| `LOG_LEVEL` | no | `INFO` | Level of the application log |
| `PORT` | no | `8090` | Port of the development server and of gunicorn |

### 8.2 Sakura AI Engine

```env
GENERATION_BACKEND=openai-compatible
GENERATION_API_TOKEN=<UUID>:<secret>
GENERATION_BASE_URL=https://api.ai.sakura.ad.jp/v1
GENERATION_MODEL=
GENERATION_RESPONSE_MODE=prompt-json
GENERATION_TIMEOUT=120
GENERATION_MAX_RETRIES=0
GENERATION_TEMPERATURE=
```

### 8.3 OpenAI

```env
GENERATION_BACKEND=openai-compatible
GENERATION_API_TOKEN=<OpenAI API key>
GENERATION_BASE_URL=https://api.openai.com/v1
GENERATION_MODEL=<model>
GENERATION_RESPONSE_MODE=json-object
GENERATION_MAX_RETRIES=0
```

OpenAI is one explicit endpoint among several, not a privileged default.

### 8.4 The legacy settings

`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_TIMEOUT`,
`OPENAI_MAX_RETRIES` and `OPENAI_TEMPERATURE` are refused. A process finding
one of them present — even exported and empty — stops and names its
replacement:

```text
OPENAI_API_KEY is no longer supported; use GENERATION_API_TOKEN.
```

The value is not quoted in the message. There is no translation, no aliasing
and no precedence rule, for four reasons:

1. A mixture of old and new settings would leave the endpoint to be guessed.
2. A stale `OPENAI_API_KEY` in a shell must not be picked up silently.
3. The path back to OpenAI's default URL has to be closed completely.
4. The break belongs in the open, and refusing the old settings by name is
   what puts it there — not the version number.

---

## 9. `config.py`

### 9.1 `Config`

```python
@dataclass
class Config:
    generation_backend: str = ""
    generation_api_token: str = field(repr=False, default="")
    generation_base_url: str = ""
    generation_model: str = ""
    generation_response_mode: str = "prompt-json"
    generation_timeout: float = 120.0
    generation_max_retries: int = 0
    generation_temperature: Optional[float] = None
    max_output_tokens: int = 6000
    max_input_chars: int = 4000
    max_alt_titles: int = 4
    prompt_dir: str = "prompts"
    log_level: str = "INFO"
    port: int = 8090
```

`generation_api_token` carries `repr=False`, so it appears in no log line and
no exception rendering. `Config.endpoint_host` exposes the host of the base
URL, which is what the log needs and all it needs.

### 9.2 Two stages

```python
def load_config() -> Config
def validate_generation_config(config: Config) -> None
```

`load_config()` converts the environment into typed values and refuses one that
is malformed on its own terms. `validate_generation_config()` refuses a
configuration that cannot address an endpoint. Both raise `ConfigError`, a
subclass of `ValueError`.

| Checked by `load_config()` | Condition |
| --- | --- |
| the legacy `OPENAI_*` variables | none is present |
| `GENERATION_RESPONSE_MODE` | `json-object` or `prompt-json` |
| `GENERATION_TIMEOUT` | a number greater than zero |
| `GENERATION_MAX_RETRIES` | a whole number, zero or more |
| `GENERATION_TEMPERATURE` | unset, or a number |
| `MAX_OUTPUT_TOKENS`, `MAX_INPUT_CHARS` | a whole number greater than zero |
| `MAX_ALT_TITLES` | a whole number, zero or more |
| `PORT` | a whole number from 1 to 65535 |

| Checked by `validate_generation_config()` | Condition |
| --- | --- |
| `GENERATION_BACKEND` | present, and one of the known backends |
| `GENERATION_API_TOKEN` | present, and free of whitespace |
| `GENERATION_BASE_URL` | present, and a usable base URL |
| `GENERATION_MODEL` | present |

A base URL is refused when it uses `http`, is not absolute, carries user
information, carries a query or a fragment, or ends with `/chat/completions` —
the SDK appends the resource path itself.

### 9.3 When each runs

- `app.py` calls both while it is imported, so a worker that cannot address an
  endpoint never starts and systemd shows the message.
- `cli.py` calls `load_config()`, applies `--model`, `--prompt-dir` and
  `--timeout`, then calls `validate_generation_config()` before reading the
  input. `--model` can therefore stand in for a missing `GENERATION_MODEL`.
  `--timeout` is checked where it is applied, because the override lands after
  `load_config()` has already refused a non-positive `GENERATION_TIMEOUT`.
- `cli.py --version` reaches neither: argparse answers and exits first.
- The unit tests construct `Config` directly and need no credentials.

---

## 10. The provider layer

### 10.1 `sizu_writer/providers/__init__.py`

```python
@dataclass
class CompletionResult:
    content: str
    model: str = ""
    finish_reason: str = ""
    request_id: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class GenerationProvider(Protocol):
    def complete(self, messages: List[Dict[str, str]],
                 config: Config) -> CompletionResult:
        ...


BACKENDS = {"openai-compatible": _openai_compatible}


def build_provider(config: Config) -> GenerationProvider:
    ...
```

`build_provider()` looks the backend up in `BACKENDS` and raises
`InternalError` when it is absent. Reaching that point means `BACKENDS` and
`GENERATION_BACKENDS` in `config.py` disagree, which is a fault of this
repository rather than of the operator — the operator's mistake was already
refused, by name, at startup.

The registry holds loaders rather than classes, so importing the package does
not import an SDK a deployment may not need.

`log_response()` writes the one INFO line of section 13.

### 10.2 Adding a backend

Three steps, and nothing else in the repository changes:

1. Write `sizu_writer/providers/<name>.py` with a class exposing
   `complete(messages, config) -> CompletionResult`, raising the `Upstream*`
   errors of `sizu_writer/errors.py`.
2. Register a loader for it in `BACKENDS`.
3. Add the value to `GENERATION_BACKENDS` in `config.py`.

`generator.py` is untouched by this, which is the point of `CompletionResult`:
what a body and its titles have to look like is not a property of the wire
protocol, so a second protocol must not be able to weaken it.

A backend whose request shape differs enough to need settings of its own adds
them as new `GENERATION_*` variables. It does not reinterpret an existing one,
because a setting that means different things per backend cannot be validated
in `config.py`.

---

## 11. `openai_compatible.py`

### 11.1 The client

```python
OpenAI(
    api_key=config.generation_api_token,
    base_url=config.generation_base_url,
    timeout=config.generation_timeout,
    max_retries=config.generation_max_retries,
)
```

`base_url` is passed unconditionally, including when it is empty. `config.py`
has already refused an empty one; passing it anyway keeps the guarantee local,
so that the endpoint compiled into the SDK cannot be reached by any path.

### 11.2 The request

```python
request = {
    "model": config.generation_model,
    "messages": messages,
    "max_tokens": config.max_output_tokens,
}
```

`temperature` is added only when `GENERATION_TEMPERATURE` is set.
`response_format={"type": "json_object"}` is added only under `json-object`.
`stream` is never sent.

### 11.3 The call

`client.chat.completions.create(**request)` runs once per `complete()`. There
is no retry loop of our own; retries are the SDK's, bounded by
`GENERATION_MAX_RETRIES`.

### 11.4 The answer

| SDK response | `CompletionResult` |
| --- | --- |
| `choices[0].message.content` | `content` |
| `response.model` | `model`, falling back to `GENERATION_MODEL` |
| `choices[0].finish_reason` | `finish_reason` |
| `response.id` | `request_id` |
| `response.usage.prompt_tokens` | `prompt_tokens` |
| `response.usage.completion_tokens` | `completion_tokens` |
| `response.usage.total_tokens` | `total_tokens` |

A compatible endpoint may report no usage and no id. A draft is usable without
them, so a missing count is carried as `None` rather than treated as a failure.

`InvalidResponseError` is raised when there is no choice, when the content is
not a string, when it is empty, or when the finish reason says the output limit
was reached. The JSON itself is read one layer up, in `generator.py`, and fails
the same way.

### 11.5 Finish reasons

```text
length
max_tokens
```

Both mean a truncated body, which is not offered as a draft. The list is
explicit: another value from a compatible endpoint is reported as itself and
added here once a log has shown it, never assumed to mean the same thing.

---

## 12. `generator.py`

### 12.1 What it does

1. Assemble the messages for a body or for titles.
2. Call `GenerationProvider.complete()` once.
3. Read the JSON object out of the answer.
4. Validate the fields and their types.
5. Normalize the body mechanically.
6. Return a `Draft`.

It handles no HTTP client, no authentication, no base URL and no SDK exception.

### 12.2 Reading the answer

```python
def _payload(content: str, response_mode: str) -> Dict[str, Any]
```

Under `json-object`, `json.loads()` is applied to the whole answer.

Under `prompt-json`, one of two shapes is accepted:

1. the whole answer is the object, or
2. the whole answer is a single code fence whose entire inside is the object.

Accepted:

````text
```json
{
  "body_markdown": "...",
  "primary_title": "...",
  "alternative_titles": []
}
```
````

Refused:

````text
Here is the result.

```json
{...}
```
````

Refused:

```text
Some words
{...}
```

There is no code that takes the first `{` and the last `}` out of free text.
The heuristic that reads an object out of prose is the same one that lets an
opening remark become the first line of a post, and an endpoint that explains
itself before answering is misconfigured — reading past the explanation would
hide that.

### 12.3 The schema

Body generation asks for:

```json
{
  "body_markdown": "string",
  "primary_title": "string",
  "alternative_titles": ["string"]
}
```

Title regeneration asks for the same object without `body_markdown`.

The existing validation is unchanged: a non-empty body, a non-empty primary
title, a list of strings for the alternatives, duplicates and blanks dropped,
`MAX_ALT_TITLES` of the rest kept, and the body left exactly as it was when
only the titles are regenerated.

---

## 13. Logging

### 13.1 INFO

One line per answer:

```text
generation response: backend=openai-compatible endpoint_host=api.ai.sakura.ad.jp
request_id=... model=... finish_reason=... prompt_tokens=... completion_tokens=...
total_tokens=... elapsed=... timeout=...
```

`elapsed` is the seconds one request took, measured on this side around the
create() call and rounded to a tenth. It is recorded on a successful answer as
well, because an answer that arrived in almost the whole of `GENERATION_TIMEOUT`
is the timeout of the next run, seen one run earlier.

Never recorded, at any level: the API token, the memo, the generated body, the
titles, the prompts, the `Authorization` header and the answer itself.

### 13.2 ERROR

One line per failed request, carrying the backend, the endpoint host, the
model, the SDK exception type, the HTTP status, the endpoint's request id, the
seconds the request took and the timeout it was given. The last two decide what
to do with a timeout: elapsed at the limit is an endpoint slower than the time
allowed, elapsed well short of it is a connection lost on the way, and only the
first is answered by raising the limit. The reference id shown to the user is logged by the error handler
in `app.py`, next to the exception type.

The status is worth recording even though the screen never distinguishes it:
401 is a token to replace, 403 a plan that does not cover the model, 429 a rate
limit or an exhausted monthly allowance, and only the log can say which
happened.

### 13.3 Usage

Local success counts are an operational estimate. The authoritative remaining
allowance is the endpoint's own control panel. No monthly counter is written to
a file or a database, because the server holds no state — a property this
version keeps.

---

## 14. Errors

### 14.1 What the user sees

Unchanged from the first design. No message names the endpoint, the model or
the cause.

| Exception | Condition | HTTP |
| --- | --- | ---: |
| `UpstreamConnectionError` | DNS, TLS or connection failure | 502 |
| `UpstreamTimeoutError` | over `GENERATION_TIMEOUT` | 504 |
| `UpstreamStatusError` | a 4xx or 5xx answer | 502 |
| `InvalidResponseError` | bad JSON, a missing field, a truncated answer | 502 |
| `InternalError` | a configuration or implementation failure | 500 |

### 14.2 Statuses to expect

| Status | In the log |
| --- | --- |
| 401 | the token is not valid |
| 403 | the plan or the permissions refuse the request |
| 429 | a rate limit, or the monthly allowance is used up |
| 500 | the endpoint failed internally |
| 504 | the endpoint timed out on its own side |

### 14.3 Configuration errors

Refused before any request:

```text
GENERATION_BACKEND is 'sakura'; expected: openai-compatible.
GENERATION_BASE_URL is required.
GENERATION_BASE_URL must use https.
GENERATION_RESPONSE_MODE is 'auto'; expected one of: json-object, prompt-json.
GENERATION_MAX_RETRIES is -1; expected zero or a positive integer.
```

No message quotes a secret.

---

## 15. Timeouts

| Layer | Default |
| --- | ---: |
| `GENERATION_TIMEOUT` | 120s |
| gunicorn `--timeout` | 240s |
| Apache `ProxyTimeout` | 300s |

With `GENERATION_MAX_RETRIES=0` one API call uses the innermost 120 seconds.
Raising the retries changes the worst case:

```text
worst case wait = GENERATION_TIMEOUT × (GENERATION_MAX_RETRIES + 1)
```

The two outer timeouts have to stay outside that number, or a request is cut by
Apache before Flask can render the error.

---

## 16. Security

- `.env` holds the token, is mode `600`, and is not in Git.
- `GENERATION_API_TOKEN`, `GENERATION_BASE_URL` and `GENERATION_MODEL` appear in
  no HTML, JavaScript, hidden input, cookie, response header, error page or
  copyable area.
- The endpoint comes from the server environment only. No form field names a
  URL, so there is no path by which someone could have the server relay a
  request to a service of their choosing.
- Only `https` is accepted. If a local compatible endpoint is ever needed for
  development, that requirement gets its own design; this version adds no
  `ALLOW_INSECURE_GENERATION_URL` escape hatch.
- The token format is documented as `<UUID>:<secret>` but not enforced by a
  regular expression. Checking a colon count would make sizu-writer reject a
  format change the service is entitled to make. Only presence, surrounding
  whitespace and the absence of a line break are checked.

---

## 17. CLI

The commands are unchanged:

```sh
.venv/bin/python cli.py generate --text "MEMO"
.venv/bin/python cli.py generate --input memo.txt
.venv/bin/python cli.py generate --input memo.txt --json
.venv/bin/python cli.py titles --input memo.txt --body draft.md
```

`--model` overrides `GENERATION_MODEL` and `--timeout` overrides
`GENERATION_TIMEOUT`, for one invocation. There is no option for the token or
the base URL: a command line is readable through `ps` and in a shell history,
and one of those two is a secret while the other is a decision that belongs to
the deployment.

No connection-test subcommand is added. The smallest real generation already
exercises the authentication, the model, the structured answer and the
validation:

```sh
.venv/bin/python cli.py generate --text "A short connection check."
```

A `Draft` is the success condition, not an HTTP 200.

---

## 18. Web UI

Unchanged. The endpoint, the model and the remaining allowance are not shown,
because the configuration is information for the operator, the allowance is not
readable from the API, a model name must not end up in a copyable area, and the
screens offer no way to switch endpoints.

---

## 19. Tests

`tests/test_config.py` covers the defaults, the retry default of zero, the
token kept out of `repr()`, the refusal of an unknown or missing backend, a
missing token, a missing or `http` or resource-carrying base URL, a missing
model, an unknown response mode, a negative retry count, a non-positive
timeout, the legacy variables, and the absence of secrets from every message.

`tests/test_openai_compatible_provider.py` covers the token and base URL
reaching the SDK, `max_retries=0`, `response_format` under each mode,
`temperature` sent only when set, the model and `max_tokens`, normalization of
a good answer, an answer without usage, the refusal of a missing choice, an
empty content and a truncated answer, the mapping of a timeout, a connection
failure and 401, 403, 429 and 500, and the token staying out of the log.

`tests/test_generator.py` covers building a `Draft` from a `CompletionResult`,
both response modes, a fenced answer, the refusal of prose around the object,
the absence of any fragment extraction, a missing body, a missing primary
title, the deduplication of alternatives, `MAX_ALT_TITLES`, and the body
surviving a title regeneration.

`tests/test_cli.py` covers the command line side of the settings: the `--model`
and `--timeout` overrides reaching the generation, a `--timeout` that is not
positive being refused before a request is spent, an empty memo being refused
the same way, and a configuration that cannot address an endpoint ending the
run with exit code 1.

The suite uses no network and no token. Testing against the real Sakura AI
Engine is a manual acceptance step, and no live token is put into CI.

---

## 20. Manual acceptance

### 20.1 Before starting

A Sakura Internet member ID, a Sakura Cloud project, completed phone
verification, a registered payment method, the free plan for foundational
models selected, an issued account token, and a model name from the list of
available models that the free allowance covers.

### 20.2 The settings

```sh
cp .env.example .env
chmod 600 .env
$EDITOR .env
```

Confirm the settings exist without printing the secret:

```sh
.venv/bin/python - <<'PY'
from config import load_config, validate_generation_config

config = load_config()
validate_generation_config(config)

print("backend:", config.generation_backend)
print("base_url:", config.generation_base_url)
print("model:", config.generation_model)
print("token configured:", bool(config.generation_api_token))
print("response mode:", config.generation_response_mode)
print("max retries:", config.generation_max_retries)
PY
```

Expected:

```text
backend: openai-compatible
base_url: https://api.ai.sakura.ad.jp/v1
model: <configured model>
token configured: True
response mode: prompt-json
max retries: 0
```

### 20.3 The CLI

```sh
.venv/bin/python cli.py generate \
  --text "子どもと歩いていて、同じ道でも急いでいる日とそうでない日では見えるものが違うと思った。"
```

Check that the exit status is 0; that the primary title, the alternatives and
the body are printed; that no JSON, explanation or editing note is inside the
body; that the log names `api.ai.sakura.ad.jp` as the endpoint host; that no
token appears in the log; that the application made one API call; and that the
control panel shows the usage increase.

### 20.4 The screens

```sh
.venv/bin/python app.py
```

Check that the input screen renders; that a body and titles can be generated;
that the titles alone can be regenerated; that the body does not change when
they are; that the body and each title copy separately; that no endpoint
information or token appears in the HTML; that a 429 exposes nothing internal;
and that the reference id on the error screen finds the log entry.

### 20.5 That OpenAI is not contacted

With the Sakura settings: `GENERATION_BASE_URL` is
`https://api.ai.sakura.ad.jp/v1`; no OpenAI API key is configured; no `OPENAI_*`
variable is set — the process would refuse to start if one were; the log names
`api.ai.sakura.ad.jp`; and where traffic can be audited, no connection to
`api.openai.com` occurs.

---

## 21. Done when

1. sizu-writer runs with no OpenAI API key.
2. A Sakura account token authenticates.
3. Generation requests go to `https://api.ai.sakura.ad.jp/v1` and nowhere else.
4. A `Draft` with a body and titles is produced.
5. Regenerating the titles keeps the body.
6. `GENERATION_MAX_RETRIES=0` means one SDK call per operation.
7. An unknown backend, an empty base URL and a legacy `OPENAI_*` variable are all
   refused before a request.
8. `json-object` and `prompt-json` are both selectable.
9. No JSON is extracted out of free text.
10. The token, the memo, the body and the titles stay out of the log.
11. The unit suite passes with no network.
12. The CLI and the screens pass the manual acceptance.
13. The control panel shows the usage increase.
14. No traffic reaches `api.openai.com`.

---

## 22. Why this shape

Sakura AI Engine is not built into the code as a backend of its own. It is
reached as what it is: an explicitly configured OpenAI-compatible endpoint.

That keeps the diff against the first design small, reuses the `openai` package
as a transport, removes the need to contact OpenAI at all, lets every other
compatible service use the same settings, shares the body and title validation
across all of them, isolates the differences that remain into named settings
like `GENERATION_RESPONSE_MODE`, and leaves `providers/` as the place a
genuinely different protocol would go.

"OpenAI-compatible" is not read as "behaves identically". Which parameters are
accepted, which finish reasons come back and how reliably a structured answer
arrives all vary. Those differences are settled by settings, logs, tests and a
manual acceptance run — not hidden behind a guess or a silent retry.

---

## 23. References

1. id774, `sizu-writer` — https://github.com/id774/sizu-writer
2. id774, "ai-digest v1.1 をリリースして Anthropic 互換 API と外部入力の扱いを改善した" — https://qiita.com/ynakayama/items/beadd112dbf4788daa20
3. id774, "さくらの AI Engine の Anthropic 互換 API で ai-digest を動かす" — https://qiita.com/ynakayama/items/d486fc70c8a29f5f765c
4. Sakura Internet, Sakura AI Engine, how to use — https://manual.sakura.ad.jp/cloud/ai-engine/02-howto.html
5. Sakura Internet, Sakura AI Engine, service basics — https://manual.sakura.ad.jp/cloud/ai-engine/01-basics.html
6. Sakura Internet, Sakura AI Engine, operation guide — https://manual.sakura.ad.jp/cloud/ai-engine/03-operation-guide.html
7. Sakura Internet, Sakura AI Engine, Inference API — https://manual.sakura.ad.jp/api/cloud/ai-engine/inference.html
8. Sakura Internet, on the use of closed models — https://manual.sakura.ad.jp/cloud/ai-engine/06-closed-model.html
