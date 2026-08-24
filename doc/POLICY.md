# Implementation Policies

sizu-writer is a single Python application, so this policy is stated directly
for Python rather than separating a shared section from per-language ones.

This document stands on its own. It is the whole implementation policy of this
repository, and no rule here is completed by a document kept somewhere else. A
subject it does not cover is a gap in this document, to be filled here rather
than looked up in another repository.

[`REQUIREMENTS.md`](REQUIREMENTS.md) and [`BASIC_DESIGN.md`](BASIC_DESIGN.md)
are the higher specification of this repository, and this document is
subordinate to both. Where it contradicts either of them, this document is what
is corrected, and behaviour they do not allow is introduced by changing them
first. [`PROMPTS.md`](PROMPTS.md) governs what the prompts say and what their
output must satisfy,
[`DETAILED_DESIGN_GENERATION_API.md`](DETAILED_DESIGN_GENERATION_API.md) how
the generation API is called, and [`DEPLOYMENT.md`](DEPLOYMENT.md) how the
system is installed and run. This document governs the code that sits between
them, and where it is silent, the invariants of the basic design and the order
of priorities in the requirements decide.

The Invariants below decide over the rest of it. Some of what they forbid is
what a general policy would otherwise ask for: this system does not fall back
to a second endpoint when the first one fails, and does not infer what a
compatible endpoint supports from a model name or a URL. Those are deliberate,
and are not to be relaxed to match a more general rule.

---

## 1. General Policy

### 1.1 Design Philosophy
- Prioritize clarity, portability, and explicit control over convenience.
- Favor predictable behavior and long-term maintainability.
- Avoid implicit behavior; make control flow, errors, and side effects explicit.
- Keep the generation core (`sizu_writer/`) independent from Flask, so that
  `cli.py` and `app.py` exercise exactly the same code.

Where there are several ways to do something and the rest of this document does
not settle which, these come in order:

1. Keep the line at which the person reads the post and publishes it.
2. Do not hold or forward what the person wrote beyond what generating the post
   takes.
3. Carry the memo to the model correctly.
4. Keep it always possible to say which generation API is being talked to.
5. Do not mix the responsibilities of the web layer, the generation core and
   the provider layer.
6. Do not put into Python what belongs to a prompt.
7. Introduce no persistence and no state management that is not needed.
8. Depend on no posting path, official or otherwise.
9. Add no feature that is not needed.

A decision this list does not settle is settled by the requirements, and
recorded here once it has been.

### 1.2 Invariants
These lines are not crossed by a setting or by an extension.

- Do not send anything to the posting site. The only host this system contacts
  is the generation endpoint the configuration names.
- Do not accept credentials of the posting site, neither as a setting nor as a
  form field.
- Do not depend on browser automation. `playwright` and `selenium` do not
  belong in `requirements.txt`.
- Do not store the memo, the prompts or the generated text. No database, no
  session store, no temporary file, no cache of what a person entered: they
  live for the request that carries them and no longer.
- Do not let the API token leave the server process: not into a template, not
  into JavaScript, not into an error page.
- Do not mix an instruction to the model, an editing note, or a review result
  into the generated body. The screen separates the body from every other
  piece of information, structurally and not only visually.
- Do not render model output with `|safe`.

### 1.3 The generation endpoint
The settings decide where a memo is sent, so they are read strictly.

- Do not choose an endpoint implicitly. The backend, the token, the base URL
  and the model are required, and a missing one stops the process instead of
  being filled in with a default.
- Do not accept an unknown backend. A value the code has no provider for is
  refused before a request, never coerced to a supported backend.
- Do not switch to a second endpoint when the first one fails. One generation
  uses one route, whatever went wrong on it.
- Do not rewrite the base URL the operator named. The code does not change its
  scheme or host and does not substitute a different base URL. The configured
  provider may use the resource path defined by its wire protocol; for the
  OpenAI-compatible provider, the SDK appends `/chat/completions` to
  `GENERATION_BASE_URL`.
- Do not infer what a compatible endpoint supports from its model name or its
  URL. A difference in behavior is expressed as a named setting.
- Do not read a legacy setting as its successor. A renamed variable is refused
  by name, so that a stale value cannot decide where a memo goes.
- Do not vary the number of API requests silently. Retries are the SDK's, and
  the count is a setting an operator can see.
- Do not log the API token, the memo, the prompts or the generated text. What
  a log line carries is the shape of the exchange: the backend, the endpoint
  host, the model, the request id, the finish reason and the token counts.
- Do not accept part of an answer. A structured answer is the whole response,
  or the whole inside of one code fence; an object cut out of surrounding
  prose is refused, because that is the heuristic which lets a remark become
  the first line of a post.

### 1.4 Logging and Output
- Use the standard `logging` module. Obtain a module logger with
  `logging.getLogger(__name__)`; do not print status from library modules.
- Configure logging once, at the entry point, with `logging.basicConfig`
  writing to standard error, in the format
  `%(asctime)s %(levelname)s %(name)s: %(message)s`.
- Map severity to levels: `INFO` for normal progress, `WARNING` for a degraded
  but recoverable condition, and `ERROR` for a failure that ends the current
  command or request.
- Keep the log low-noise. One generation must not leave a trail of per-step
  lines at the default level.
- When a third-party logger, such as the HTTP client the SDK carries, adds
  nothing to a run, lower that logger rather than raising the global level.
- The screen shows `user_message` only. The cause, the endpoint, the model and
  the traceback stay in the log, next to the reference id shown to the user.
- Do not log the memo or the generated text at the default level.

### 1.5 Control Flow Rules
- Reserve `sys.exit` for the process entry point. Commands and helpers return
  their status.
- Raise a `SizuWriterError` subclass for every failure the user is allowed to
  see, and let the entry point map it to a screen or an exit code.
- Do not swallow an error with a bare `except:`. Where a broad
  `except Exception` is genuinely required, such as around a call whose failure
  modes are open-ended, log the reason before returning a failure.

### 1.6 CLI Conventions
- A command line tool provides `-h`, `--help` for usage and `-v`, `--version`
  for the version, and both exit with code `0`: a user who asked for them got
  what they asked for.
- Build the parser with `argparse`. It provides `-h`/`--help`; `-v`/`--version`
  is declared explicitly.
- An invalid or unsupported option results in usage output.
- Exit codes are consistent and are documented in the module header.
- An option that replaces a setting names the setting it replaces, so that a
  reader of a command line sees which configured value it displaced. A
  credential never gets one, and neither does `PORT`.
- An option that is left out changes nothing, so an existing service unit or a
  recorded command keeps behaving as before.
- An option value the pipeline cannot use is refused by the parser, before a
  request is spent.
- Subcommands carry the verbs of the tool. A new mode of operation becomes a
  subcommand; it does not become a flag that changes what an existing
  subcommand means.

### 1.7 Error Handling and Exit Codes
- Detect an unmet prerequisite early. A misconfiguration is refused before a
  request is spent, not after.
- Log the reason and the affected target when an error occurs.
- Exit code semantics follow the usual UNIX/Linux conventions and stay
  consistent across the repository.

#### 1.7.1 Exit Code Conventions
- **0: Success**
  The command completed. This includes terminating after help or version
  output.
- **1: General failure**
  The default failure code: a refused setting, an unreadable input, or a
  generation that did not produce a draft.
- **2: The command line was rejected**
  What `argparse` returns for an unknown option, a missing subcommand or an
  argument it cannot convert. Do not raise it from application code.
- **126, 127, 128 and above**
  Reserved by the shell and by signal convention. Do not redefine them for
  application errors.

### 1.8 Environment Differences
- Branch on what the environment provides, not on what it is called. A
  distribution name, a release number, a platform string or a Python build
  each answer a question the code is not asking. The question is whether the
  command, the file, the service or the format it needs is there.
- Keep that detection in one place. The same question answered separately in
  several places drifts apart as environments change.
- A capability the application can work without is detected where it is used,
  not declared as a requirement. Detection asks whether the capability is
  usable, not only whether it is present: a package can import while the
  backend it needs is absent.
- Decide in advance what an absent optional capability leads to: use the
  alternative, skip the step and say so once, or refuse the run.
- This section is about the host and the packages installed on it. It does not
  reach the generation endpoint, where the Invariants forbid choosing an
  alternative: one generation uses one route, whatever went wrong on it.

### 1.9 Pull Request Scope and History
A pull request presents the change it proposes, not the sequence of corrections
that produced it. It carries one purpose, and when the direction is revised part
way through a review, the branch is rewritten so that it reads as the change
finally intended, and merges as if it had been written that way.

#### 1.9.1 One Purpose to a Pull Request
- Changes that serve different purposes are proposed separately, as a rule,
  even when they touch one file and even when one was noticed while the other
  was being made. A pull request is accepted or rejected whole, and a mixed one
  leaves no way to take the part that is wanted.
- A change noticed in passing is proposed on a branch of its own. It is not
  carried along because the working tree happened to be open at it, and it does
  not enlarge the request already under review.
- Tidying, renaming and reformatting that the change does not require are a
  change of their own. Attached to something else, they bury the change the
  reviewer came to read.
- Work that cannot stand without the change is not a second purpose. Its
  `doc/VERSIONS` entry, the `Version History` entry in the header of the module
  it changes, the test that fails without it, and the README or `.env.example`
  line a change of behavior requires, belong to the change that requires them.
- Where the separation is genuinely artificial, because neither part is correct
  or reviewable without the other, they are proposed together and the request
  says why.

#### 1.9.2 Keeping a Branch to Its Change
- A branch that carries one coherent change carries it as one commit. That
  commit is amended and force pushed with `--force-with-lease`, rather than
  gaining a further commit for each remark received.
- Commits such as "fix review comment", "address feedback" or "resolve
  conflict" describe the review rather than the change, and do not belong in
  the history that is merged.
- A branch is split into several commits only when it genuinely carries several
  independent changes. The reasoning is the one that decides a `doc/VERSIONS`
  bullet: coherence, not chronology.

#### 1.9.3 Leaving No Trace of the Correction
- Each revision is read against the base branch, not against the revision
  before it, so that a correction leaves no residue in the diff that is merged.
- A correction withdraws what it replaces. Code, comments and wording
  introduced by an earlier revision and since abandoned are removed, not left
  standing beside their replacement.
- Conflicts with the base branch are resolved by rebasing onto it, so that no
  merge commit enters the branch.
- A rewritten branch invalidates the copies others have fetched. Force pushing
  is confined to the branch under review, and the rewrite is stated whenever
  the branch is shared.

### 1.10 Prompts
- The prompts are files under `prompts/`, outside the Python package, and the
  directory is named by a setting.
- A change to how a post reads is an edit to a prompt. Adding a rule about
  register, length, formulae or repetition to Python is the wrong place for it
  unless the rule is mechanical and cannot be expressed as an instruction.
- The prompt keeps the memo plainly apart from the instructions given by the
  system, and says which is which.
- Substitution into a prompt is textual and literal. A prompt is not treated as
  a format string, so a brace or a percent sign written in it needs no
  escaping.
- A prompt file that is missing, unreadable or empty is a configuration error,
  refused before a request is spent. The code ships no built-in text to fall
  back to, because a post written by a fallback prompt would be
  indistinguishable from one written by the intended prompt.
- Post processing is mechanical and changes no meaning: an outer code fence, a
  heading level, an excess of blank lines, the spacing between full width
  characters and ASCII. A problem with how the post reads is solved in the
  prompts.
- An inspection that finds a forbidden formula, or a phrase that reads as a
  remark about the work, reports it and rewrites nothing. Handing the finding
  to the person is closer to what this system is for than breaking a sentence
  on a false positive.
- What each prompt is for, and the contract its output has to keep, are
  documented in [`PROMPTS.md`](PROMPTS.md), and the file and the document are
  changed together.

### 1.11 Judging a Change
Before a change is proposed, it answers these:

- Does it cross an Invariant? Then it is not made.
- Does it need the requirements or the basic design to say something they do
  not? Then those documents change first.
- Does it move a decision about how a post reads out of the prompts and into
  Python, or let post processing change a meaning?
- Does it widen what leaves the process, or what is kept after the request
  ends?
- Can the API token reach a template, a page, a URL or an error through it?
- Does it change an existing option, setting, output or exit code that a
  service unit or a recorded command depends on?
- Does it add a dependency, and does that dependency earn its place?
- Is it the smallest change that serves its purpose?
- Does a test fail without it?
- Which documents change with it: the module header, `.env.example`, the
  README, the prompt specification, `doc/VERSIONS`?

---

## 2. Python Policy

### 2.1 Structure
- Python 3.9 or later. Every module states `Python Version: 3.9 or later` under
  `Requirements`, and no module states a minimum higher than the code needs.
- The shebang is `#!/usr/bin/env python`. Do not write `python3`.
- The encoding header `# -*- coding: utf-8 -*-` follows the shebang.
- Every module starts with the header block used across id774 repositories, in
  the order given under [Documentation and Versioning](#documentation-and-versioning).
- Comments are written in English, in the imperative, and stay short, avoiding
  a redundant lead-in such as `# Function to ...`.
- A comment says why, not what. Where a decision looks arbitrary, such as
  substituting with `str.replace()` rather than a format call, or refusing an
  answer that is only part of a response, the comment gives the reason, so that
  a later change does not quietly undo it.
- Name a thing by what it is, not by a part of it. The shell is the interpreter
  that runs a shell script, so a script is not "a shell", in the same way that
  a USB memory stick is not "a USB". The same loss happens wherever a shorthand
  reaches for the interface, the format or the container instead of the thing
  itself. This applies to the headers, the documents and the commit messages as
  much as to the comments.
- Type hints are used on the public functions of a module.
- Every public function, class and method carries a docstring stating what the
  call returns or does. A one-line docstring stays on one line, with a space
  inside each pair of quotes:
  `""" Return the body with the review notes removed. """`. A longer one opens
  on the line after the quotes, and describes the non-obvious parameters under
  `Args:` and the result under `Returns:`.
- Prefer `str.format()` over an f-string. Substitution into an external text
  such as a prompt is done with `str.replace()`, so that a brace written in
  the prompt does not need escaping.

### 2.2 Program Structure
- An executable defines `main() -> int` and terminates with `sys.exit(main())`.
- Use early returns rather than nesting the body of a function inside a
  condition.
- Group imports as standard library, third party, then local. Import a
  third-party package inside the function that needs it only when that package
  is optional, so that the module still imports without it, and name the
  package to install in the error raised when it is missing.

### 2.3 Configuration
- Every setting lives in `config.py`, in the `Config` dataclass, read from the
  environment or from `.env`. `config.py` performs no network access and
  touches no file beyond `.env`.
- A credential never gets a command line option: a command line is readable by
  every user of the host.
- Validation is in two stages. `load_config()` converts values and refuses one
  that is malformed on its own terms; `validate_generation_config()` refuses a
  configuration that cannot address an endpoint. Every path that reaches the
  API passes both; `cli.py --version` and the tests pass neither.
- No error message quotes a secret. A token is reported as present or absent.
- An empty or whitespace-only string setting reads as unset, so that a bare
  `NAME=` line in `.env` behaves exactly like the absent line.
- `.env.example` ships no placeholder credential. An empty value is honest
  about being unset; a fake token would pass a presence check and fail only
  after a generation has been spent.

### 2.4 Dependencies and I/O
- Runtime dependencies are declared in `requirements.txt` and pinned to a
  compatible range, so that a future major release cannot break a running
  service. Add a dependency only when it earns its place; prefer the standard
  library otherwise.
- Always pass `encoding="utf-8"` for a text file operation.
- Every outbound request carries an explicit timeout, which `GENERATION_TIMEOUT`
  supplies and `--timeout` replaces for one run. There is no request without
  one: a request that hangs holds a web worker until the client gives up, and
  holds an unattended run until the next one starts.
- Treat the answer as untrusted input. It is validated before it reaches a
  template or a file, and one that does not validate is refused rather than
  repaired into something that passes.

### 2.5 Testing and Operation
- `tests/test_*.py`, `unittest` and `unittest.mock` only.
- No network access and no API call. The client is replaced by a stub, and the
  provider tests stub the `openai` package itself rather than importing it.
- No test needs a token, a `.env` or a real endpoint.
- A test writes nothing outside a temporary directory.
- Run them with `python -m unittest discover -s tests`.
- The runner exits `0` only when every test passed, which is what a service
  check or a CI step reads. A passing suite says nothing about the endpoint
  being reachable; only an actual generation does.
- A fix for a defect arrives with the test that fails without it.
- Assume unattended execution as a service by default. The process reads its
  configuration from the environment or `.env`, so every required variable is
  defined explicitly there rather than inherited from a login session.
- Anything that changes state on the host, the deployment steps included, is
  safe to run twice. Check the current state before changing it, rather than
  assuming the state a previous run left behind.
- The service runs with the privileges its work needs and no more. A step that
  needs a raised privilege takes it for that step; the process does not run its
  whole body under it.

### 2.6 Documentation and Versioning
- Every module must contain a structured header, in this order:
  `Description`, `Routes` (the web application only), the standard `Author`,
  `Source Code`, `License`, `Contact` block, `Usage` and `Options`
  (executables and modules that take options only), `Exit Codes` (a module
  that can end the process with more than one status), `Requirements`,
  `Environment Variables` (`config.py` only), `Version History`.
- `Routes` sits next to `Description` because it says what the module serves,
  which is part of what it is; `Usage`, `Options` and `Exit Codes` say how it
  is driven, and follow the identifying block.
- Every setting is documented in three places that must agree: the
  `Environment Variables` block of `config.py` (the name, what it decides,
  whether it is required, and the default when it has one), `.env.example` as
  a file to copy, and the README for a reader who is not editing code.
- "Test Cases" belong in the test code under `tests/`, never in the application
  modules.
- Documentation must be updated in sync with behavior changes.

#### 2.6.1 When to Bump a Module Version
- These rules apply to the `Version History` in each module header. Repository
  release versions and Git tags follow the separate rules below.
- Do not bump the version mechanically every time a file is touched. Decide
  based on the nature of the change:
  - Documentation-only, comment-only and formatting-only changes (help text,
    README/POLICY/VERSIONS wording, whitespace and layout, with no effect on
    behavior) do not bump the version.
  - Any change that affects code behavior (bug fixes, new options, and refactors
    that change observable behavior) bumps the version.
  - Multiple updates on the same date are consolidated into a single version
    entry; do not increment the version multiple times on the same date.
  - Finalizing only the release date of an entry that already exists, such as
    changing `TBD` to the actual date, is not by itself a change. Classify that
    entry by what it contains, not by the date edit.

#### 2.6.2 Module Version Numbering
- Versions use a two-level `major.minor` scheme.
- When incrementing `minor` would reach `10`, roll over instead: increment
  `major` by 1 and reset `minor` to `0` (for example `v0.9` -> `v1.0`,
  `v1.9` -> `v2.0`).
- Do not continue `minor` past `9` as in standard semantic versioning
  (do not use `v1.10`, `v1.11`, ...).
- Raising `major` for a reason other than the rollover is a decision the
  maintainer makes, not one this document derives from the change.
- Removing or renaming an option, changing what an existing argument means,
  changing a default so that an unchanged invocation does something else, and
  changing how a path or a configuration value is resolved are all incompatible
  changes. Say so in the `Version History` entry and in `doc/VERSIONS`, so that
  the number the change is released under is chosen knowing that.

#### 2.6.3 Repository Versioning
- Repository release versions are independent of individual module versions.
- Record repository release versions in `doc/VERSIONS` and use the same versions
  for Git tags.
- Repository release versions may use a three-level `major.minor.patch` scheme.
  The first release is v1.0 and the one after it is v1.0.1.
- Work that is not released yet takes no version of its own: it belongs to the
  entry already standing at the top of `doc/VERSIONS`.
- An unreleased entry carries `(Release Date: TBD)`, and its version number
  stays provisional until it ships. An entry opened under one number may be
  released under another once what accumulated in it is known; which number it
  takes is decided then. Replacing `TBD` with the actual date is the release
  itself, not a change to record.
- A repository that has not yet made its first release is in its initial
  construction stage, and that stage takes no entry here. Typically this is the
  state while `v1.0` is the first release and the repository still stands below
  it, or `v1.0` itself is unreleased. The changes made while building up to that
  release are not accumulated in `doc/VERSIONS` one by one: the file is the
  record of released versions, not of the construction that precedes the first
  of them, and its first entry is written when that release is made.
- A documentation-only change takes no `doc/VERSIONS` entry, unless its scale
  makes it worth one line saying so.
- The package version exposed by `sizu_writer.__version__` and
  `cli.py --version` tracks the application, and is bumped when a release
  warrants it, not on every change.

#### 2.6.4 doc/VERSIONS Structure
- `doc/VERSIONS` reads as a version-level summary of overall changes, not a raw
  commit log. It is a plain text document and follows the rules for one stated
  below, with the one exception of line length described here.
- Each entry opens with a heading of the form `vX.Y.Z (YYYY-MM-DD)`, or
  `vX.Y.Z (Release Date: TBD)` while it is unreleased, underlined with `-`
  characters, followed by one `-` bullet per change.
- Write one coherent change on one physical line. This is the rule, qualified
  once below for a file that has already settled on a form of its own. The file
  is read as a list and reviewed as a diff, and both are served by an entry that
  is not wrapped: one line is one change, added, removed or reworded as a whole.
- That rule comes before the roughly 80 columns a plain text document otherwise
  aims at. Near 100 columns is the usual target, and an entry that has to name
  a file, a command, a function, an option or a setting may run to about 120
  columns or beyond.
- That is a deliberate exception in this file, not an oversight in it. Do not
  rewrap `doc/VERSIONS` to 80 columns, and do not report a long entry here as a
  violation of that width.
- These widths are a prompt to check whether an entry explains more than it
  needs to, not a limit to enforce.
- `doc/VERSIONS` carries these guidelines again at its foot, and an entry
  written into it follows the reasons recorded there.
- That qualification is this: where the file has settled on a width of its own,
  a new entry is wrapped to that width and balanced against the lines already
  standing, so that the version history stays of a piece, and that consistency
  comes before the one physical line asked for above. Holding to a form the
  file has established is how the rule is kept there, not a departure from it,
  and the entries already written are not reflowed or rebuilt to suit it.
- When an entry runs long, look first for what can be dropped or abstracted:
  the implementation detail, the example, the detailed reason, the secondary
  effect. Consider that before wrapping the line.
- Keep the changed target, the behavior visible from outside, the effect on
  compatibility, the effect on safety, and the identifiers that matter.
- An entry that is long because it names the identifiers it needs is not
  shortened for its length alone.
- Merge changes that serve one purpose. Related changes to the same file within
  one version are merged as a rule; changes to the same file that mean
  different things are left as separate entries rather than forced together.
- Place entries that touch the same feature, file or purpose near each other,
  and append an independent change to the end of that version. Reading well as
  a version comes before preserving the order the commits happened in.
- Use UTF-8.

#### 2.6.5 Document Format
- The format of a document is decided by what it is for and by the name it
  carries, not by whether part of its content happens to parse as Markdown.
- A document named with `.md` is written, displayed and maintained as Markdown.
- A document that carries no extension is a plain text document, and nothing in
  it assumes a Markdown renderer.
- Underlined headings, dashed lists, backquotes and bare URLs are readable as
  Markdown wherever they appear, and finding them in a plain text document does
  not make it one.
- The name states the format so that nobody has to infer it from the content.
  Reading a file to guess what it is gives a different answer to every reader
  and to every agent; the extension gives all of them the same answer.
- The two formats are kept apart because they are read in different places.
  Markdown is read rendered, in a browser, where the structure carries the
  meaning. Plain text is read raw, in a terminal, a pager or a diff, where the
  bytes are all there is. A rule that serves one damages the other, which is
  why the two sets of rules below are stated separately and are not merged.

#### 2.6.6 Markdown Documents
- A Markdown document may assume that it will be rendered, on GitHub or
  elsewhere.
- Use headings, lists, tables, code blocks, links and emphasis to make the
  structure of the document explicit.
- Name it with `.md`, so that the path states the format.
- `*.md diff=markdown` in `.gitattributes` gives it diff hunk headers that name
  the section, and that is there to be used.
- Both sides count: the structure after rendering, and how easy the source is
  to edit.
- Ordinary prose may be wrapped where that keeps the source readable, near the
  width the document already uses.
- The roughly 80 columns that plain text aims at is not a limit here, and is
  not applied to a Markdown document as one.
- A URL, a table row, a code block, a command, an identifier or a link
  construct may run long. Wrapping one of those costs a copyable line or a
  working table and buys nothing.
- Line length never justifies breaking the meaning of the markup or inserting a
  break the notation does not want.
- In a Markdown document the heading structure, the paragraph structure, the
  correctness of the notation and the rendered result come before the length of
  a physical line.

#### 2.6.7 Plain Text Documents
- A plain text document is read as it is, without GitHub's rendering and
  without any particular viewer.
- It stays readable on an old fixed-width terminal, under `less` or `cat`, in
  an editor and in a diff.
- Ordinary prose stays near 80 columns as far as it practically can.
- Near 80 columns is a guideline for readability on a terminal, not an absolute
  mechanical limit.
- A URL, a legal formula, a command, a required identifier, a table, or a line
  that is clearer left unbroken may exceed the usual width.
- Exceeding that width is not by itself a defect, and not by itself something
  that has to be corrected.
- Markdown-compatible headings and lists may be used to give such a document
  structure, but nothing in it assumes Markdown rendering.
- Judge it as raw text: how readable and how stable it is line by line, not
  what a renderer would make of it.

#### 2.6.8 Document File Naming
- A document written in Markdown takes a `.md` extension when it is newly
  created. sizu-writer is a recent repository, so its Markdown documents carry
  the extension from the moment they are written: `doc/POLICY.md`,
  `doc/LICENSE.md`, and the requirement, design and operation documents beside
  them.
- The licence texts keep the extensionless names by which they are recognised:
  `COPYING` and `COPYING.LESSER`.
- A document that is not Markdown takes no extension, or `.txt`.
- An existing document is not renamed to add or change an extension. A path
  here is a public URL that the README, the other repositories, and pages
  outside them link to. Renaming breaks those links, and the ones outside can
  be neither found nor repaired.
- Rename only when the current name causes a failure that outweighs the links
  it breaks, and only after examining the references to it. `doc/POLICY.md` and
  `doc/LICENSE.md` were renamed under that exception: GitHub does not render a
  Markdown document that carries no extension, nothing in `.gitattributes`
  changes that, and every reference to these two files was inside this
  repository, where it was corrected in the same change.
- `doc/VERSIONS` keeps its name. It is not Markdown, so rendering does not
  apply to it.
- An older repository may keep an extensionless `POLICY` or `GUIDELINES`
  because history, a published path, an outside reference or compatibility
  weighs more there than rendering does. A name that differs between
  repositories is not by itself a policy that differs: the rule for naming a
  new document and the rule for keeping an existing path hold at the same time.
- The naming of a recent repository is not applied backwards to an older one,
  and the historical naming of an older repository is not copied into a recent
  one. Each name is decided where it lives.

#### 2.6.9 The Extensionless Documents Here
- `doc/VERSIONS` is the version history, plain text, without an extension.
- `doc/COPYING` and `doc/COPYING.LESSER` hold the official licence texts as
  plain text.
- None of the three is a `.md` document, and none of them is meant to be
  rendered as Markdown.
- Their official names, their legal wording and their published paths come
  first. Uniformity of form is not on its own a reason to rename them.
- `doc/LICENSE.md` carries `.md` because it is the Markdown document this
  repository presents to a reader.
- `LICENSE.md` and the `COPYING` texts have different roles, so having both is
  neither a duplicate nor an inconsistency.
- Do not rename `doc/VERSIONS`, `doc/COPYING` or `doc/COPYING.LESSER` to `.md`
  because they contain a symbol a Markdown renderer would accept.

#### 2.6.10 Document File Attributes
- What `.gitattributes` says about a diff does not decide the format of a
  document. It describes documents whose format their names have already
  settled.
- `.gitattributes` gives `diff=markdown` to `*.md`, so that a diff hunk header
  names the section it falls in. A document named with `.md` is covered by that
  line and needs no entry of its own.
- `doc/VERSIONS` is excluded. It is underlined plain text, and `diff=markdown`
  empties the hunk headers that otherwise name the version; leaving it out
  agrees with treating it as a plain text version history.
- `doc/COPYING` and `doc/COPYING.LESSER` are excluded as the licence texts,
  which agrees with their role as the official legal wording.
- No file is given `linguist-language`. Nothing in `.gitattributes` makes GitHub
  render a document that carries no extension; that is what the `.md` names are
  for, and an extensionless document is not dressed up as Markdown.
- How a document appears on GitHub is not a reason on its own to change its
  format or its attributes.

#### 2.6.11 Form and Role
- Bringing every document to one extension, one line width and one way of being
  displayed is not a goal in itself.
- Choose the form from the role of the document, where it is read, the path it
  is published under, what it must stay compatible with, and how it is edited.
- What is kept uniform is not the appearance of the documents but the criterion
  by which their form is chosen.
- Markdown documents and plain text documents living side by side in one
  repository is the intended design, not an untidiness to be resolved.
- Modernizing or unifying a format must not cost an existing path, a legal
  text, readability on a terminal, or the legibility of a diff.
- Before changing a file name or a line width, find out why the current form
  was chosen.

### 2.7 License
- The repository is dual licensed under the GPL version 3 or the LGPL version
  3, at the user's option. The full texts live in `doc/LICENSE.md`,
  `doc/COPYING` and `doc/COPYING.LESSER`.
- Every module header repeats the license line of the standard identifying
  block, so that a file read on its own still states its terms.
- Add a dependency only when its license is compatible with that choice.
