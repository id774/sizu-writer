# sizu-writer

## Overview

**sizu-writer** turns a short memo, a passing thought, a small observation, a doubt or a question into a full post body and a set of title candidates for [Shizuka na Internet](https://sizu.me), a Japanese site for quiet, unhurried writing.

It does not post. The work of this system ends on the screen: a human copies the body and the chosen title, pastes them into the posting form, reads them once more and publishes. There is no code path to the posting site and no place to hand it a credential.

The repository is written in English: the code, the comments, the screens, the documents and the prompts. Only the generated post itself is Japanese, because the medium is.

- Requirements: [doc/REQUIREMENTS.md](doc/REQUIREMENTS.md)
- Basic design: [doc/BASIC_DESIGN.md](doc/BASIC_DESIGN.md)
- Implementation policy: [doc/POLICY](doc/POLICY)

## Structure

```
[browser] -> [Apache: HTTPS, access control] -> [gunicorn on 127.0.0.1] -> [Flask app.py]
                                                                                |
                                                        sizu_writer/ (core) -> [OpenAI compatible API]
                                                              ^
                                                     prompts/*.md, cli.py
```

The generation core is independent from Flask, so `app.py` and `cli.py` run the same code. The quality of the output is settled with `cli.py`, before any screen is involved: prompts are what this kind of system iterates on, and iterating on them through a browser is slower for no gain.

## Setup

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`. The model has no default, because a sensible one differs per endpoint. Every setting is documented in [.env.example](.env.example).

## Usage

From the command line:

```sh
.venv/bin/python cli.py generate --text "MEMO"
.venv/bin/python cli.py generate --input memo.txt --json
.venv/bin/python cli.py titles --input memo.txt --body draft.md
```

Development server:

```sh
.venv/bin/python app.py     # http://127.0.0.1:8090
```

Enter a memo and generate: the screen shows the leading title, the other candidates and the whole post body. The body and each title have their own copy button, and the whole draft or the titles alone can be regenerated.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests
```

No network access; the OpenAI client is stubbed. The acceptance conditions about the quality of the writing (requirements 14, items 7 to 9) cannot be decided by a test: run a real memo through `cli.py generate` and read the result.

## Deployment

[deploy/](deploy) holds an example systemd unit and an example Apache configuration.

```sh
sudo cp deploy/sizu-writer.service /etc/systemd/system/
sudo systemctl enable --now sizu-writer
sudo cp deploy/sizu-writer.conf /etc/apache2/sites-available/
sudo a2ensite sizu-writer && sudo systemctl reload apache2
```

gunicorn listens on `127.0.0.1` only, so the application is reachable through Apache and nowhere else. HTTPS, Basic authentication and IP restriction belong to Apache.

The timeouts widen from the inside out: `OPENAI_TIMEOUT` (60s), the gunicorn `--timeout` (120s), the Apache `ProxyTimeout` (180s). Raising `OPENAI_TIMEOUT` or `OPENAI_MAX_RETRIES` means revisiting the two outer values, because a request cut off by Apache never reaches the error handling of Flask and returns a bare 504.

Rate limiting is not implemented in the application: it cannot count across gunicorn workers, so it would not hold. Restrict the readers with Apache (`mod_ratelimit`, `mod_qos`) or with authentication instead.

## Not in this first version

Parts of the basic design deliberately left for a later change:

- the space inserted between full width characters and ASCII (`BODY_ASCII_SPACING`)
- the `json_schema` and `none` response format modes; `json_object` is fixed for now
- the `PROMPT_RELOAD` reload of the prompts
- the `Origin` check on POST (`REQUIRE_SAME_ORIGIN`)
- persistence of the generated drafts (requirement 11, a future extension)

## License

Dual licensed under the GPL version 3 or the LGPL version 3. See [doc/LICENSE](doc/LICENSE).
