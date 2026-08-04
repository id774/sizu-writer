# Debian and Apache Deployment

This guide deploys sizu-writer on Debian behind Apache and HTTPS.
Run the commands from an account with `sudo` access.

## Before you begin

Prepare these values first:

- A DNS name whose `A` or `AAAA` record points to the server
- An API key and model name for an OpenAI-compatible endpoint
- A TLS certificate for the DNS name
- A reader restriction: Basic authentication, an IP range, or a VPN

Allow inbound TCP ports 80 and 443 and outbound HTTPS to the API endpoint.
Do not expose gunicorn's port to another host.

## Install the service

Install the required packages:

```sh
sudo apt update
sudo apt install apache2 git python3 python3-venv
sudo a2enmod proxy proxy_http ssl
```

Create an unprivileged account and install the repository:

```sh
sudo adduser --system --group --home /opt/sizu-writer sizu
sudo -u sizu git clone https://github.com/id774/sizu-writer.git /opt/sizu-writer
cd /opt/sizu-writer
sudo -u sizu python3 -m venv .venv
sudo -u sizu .venv/bin/pip install --upgrade pip
sudo -u sizu .venv/bin/pip install -r requirements.txt
```

Create the environment file and edit the two required values:

```sh
sudo -u sizu cp .env.example .env
sudo chmod 600 .env
sudo -u sizu sensible-editor .env
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL`.
Set `OPENAI_BASE_URL` only for a compatible service other than OpenAI.
Keep `PORT=8090` unless both deployment examples are changed to the same port.

Run the offline checks, then make one real API request:

```sh
sudo -u sizu .venv/bin/python cli.py --version
sudo -u sizu .venv/bin/python -m unittest discover -s tests
sudo -u sizu .venv/bin/python cli.py generate --text "A deployment test memo."
```

The last command spends API quota and confirms the key, model and endpoint.

## Start the application

Review `deploy/sizu-writer.service` before copying it.
Its user, paths, port and timeouts must match the installation and `.env`.

```sh
sudo cp deploy/sizu-writer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sizu-writer
sudo systemctl status sizu-writer
curl --fail --silent http://127.0.0.1:8090/healthz
```

The expected health response is `{"status":"ok"}`.
This check does not call the generation API.

Read startup and request errors with:

```sh
sudo journalctl -u sizu-writer --since today
```

## Configure Apache and TLS

Edit a copy of `deploy/sizu-writer.conf` before enabling it.
Replace the server name and certificate paths with real values.

```sh
sudo cp deploy/sizu-writer.conf /etc/apache2/sites-available/
sudo sensible-editor /etc/apache2/sites-available/sizu-writer.conf
sudo apache2ctl configtest
sudo a2ensite sizu-writer
sudo systemctl reload apache2
```

The sample assumes that a certificate already exists.
Debian's Certbot packages can obtain and renew one when that is preferred.
Follow the certificate provider's current instructions rather than copying an old command.

Add an HTTP virtual host if port 80 should redirect to HTTPS:

```apache
<VirtualHost *:80>
    ServerName sizu.example.net
    Redirect permanent / https://sizu.example.net/
</VirtualHost>
```

Enable `mod_alias` if the redirect directive is unavailable.
Run `apache2ctl configtest` before every Apache reload.

## Restrict access

Do not publish an unrestricted instance.
Each generation request sends memo text to an external service and may incur a charge.

The Apache example contains disabled Basic authentication and IP restriction blocks.
Enable one block, or put the site behind a VPN.
Create a Basic authentication file with:

```sh
sudo htpasswd -c /etc/apache2/sizu.htpasswd USERNAME
sudo chown root:www-data /etc/apache2/sizu.htpasswd
sudo chmod 640 /etc/apache2/sizu.htpasswd
```

Install `apache2-utils` if `htpasswd` is unavailable.
Use `htpasswd` without `-c` when adding another user.

Application-level rate limiting is not implemented.
Authentication, a VPN, `mod_qos`, or another shared limiter must enforce it.

## Verify the complete path

Check each layer separately:

```sh
curl --fail --silent http://127.0.0.1:8090/healthz
curl --fail --silent https://sizu.example.net/healthz
sudo -u sizu .venv/bin/python cli.py generate --text "An API test memo."
```

Supply the configured authentication option to the external `curl` command.
The first two checks test liveness only; the third makes a real API request.
Finally, generate a draft in the browser to test Apache, gunicorn and the API together.

## API integration

### Generation endpoint contract

sizu-writer uses the OpenAI SDK's Chat Completions client.
The configured endpoint must accept these request fields:

- `model`
- `messages`
- `max_tokens`
- `response_format={"type":"json_object"}`
- `temperature`, only when `OPENAI_TEMPERATURE` is set

The assistant message must contain a JSON object like this:

```json
{
  "body_markdown": "Generated post body.",
  "primary_title": "Primary title",
  "alternative_titles": ["Another title"]
}
```

The response must expose that content through `choices[0].message.content`.
It must also report `finish_reason`, because a response cut off for length is rejected.
An endpoint that only resembles Chat Completions may not satisfy this contract.

Change one compatibility setting at a time and test it with `cli.py generate`.
Leave `OPENAI_TEMPERATURE` empty when the selected model rejects that parameter.
Keep the timeout order `OPENAI_TIMEOUT` < gunicorn < Apache `ProxyTimeout`.

### Calling sizu-writer from another system

sizu-writer does not expose a public JSON API.
`POST /generate` accepts a browser form and returns HTML; it is not a REST contract.

For a local process, use the CLI's stable JSON output:

```sh
sudo -u sizu .venv/bin/python cli.py generate --input memo.txt --json
```

A network API needs a separate design for authentication, request and error schemas,
rate limiting, cross-origin policy and contract tests.
Do not treat the current form endpoint as that API.

## Routine operations

After changing Python code or `.env`, restart the service:

```sh
sudo systemctl restart sizu-writer
```

After changing dependencies, install them before restarting:

```sh
cd /opt/sizu-writer
sudo -u sizu .venv/bin/pip install -r requirements.txt
sudo systemctl restart sizu-writer
```

Prompt files are read for every generation, so prompt-only changes need no restart.
Changing the unit requires `systemctl daemon-reload` and a restart.
Changing the Apache virtual host requires a config test and reload.

Rotate an API key by replacing it in `.env` and restarting the service.
Never put the key in a command line, a repository, a template or an Apache log.

Generated drafts are not persisted on the server.
Back up `.env` securely and back up any custom prompt directory.
Keep the previous application revision available for rollback.
