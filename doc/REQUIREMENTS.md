# Requirements: a writing system for Shizuka na Internet

## 1. Purpose

Take a short text a person wrote — a passing thought, an observation, a discomfort, a question, a short reflection — and use the OpenAI API to produce a post for Shizuka na Internet (sizu.me).

The system does not post. It shows the whole post body and the title candidates on the screen; the person reads them, copies them, pastes them into the posting form of Shizuka na Internet and publishes.

## 2. Principles

- Run on a server as a Flask application, continuously.
- Publish it through the Apache HTTP Server.
- Let the person enter a short text through a web page.
- Use the OpenAI API to produce the whole post body and the title candidates.
- Show the post body so that it can be copied whole.
- Show each title candidate so that it can be copied on its own.
- Leave the posting to the person.
- Never post to Shizuka na Internet from this system.
- Depend neither on browser automation nor on any unofficial posting path.

## 3. What kind of text

The system produces text that is too long for the timeline of a microblog, yet does not need the construction and argument of a blog, Qiita, Zenn or note article.

It covers:

- a thought of the moment
- a small observation
- a discomfort
- an association
- a question
- a short reflection
- a thought on a familiar theme, sorted out again

It does not extend to:

- a primary source for id774.net
- a draft for Qiita, Zenn or note
- material for a future article
- a systematic essay
- a survey article
- a how-to
- an explainer

The same idea may later feed an article; that is not prevented. But no point, explanation, evidence or generalization is added in anticipation of it.

The grain of the material decides the length. What one line on a microblog would exhaust stays short here rather than being inflated to fill the medium, and what has research, a systematic argument or a reproducible procedure at its centre is written as the memo carries it, without the argument such an article would need. Being unfinished, reaching no conclusion and concerning the writer alone are none of them reasons to treat a text as unsuited to this medium.

## 4. Expected flow

1. The person opens the system in a browser.
2. They enter a short text, a memo, an event, a fragment of a conversation.
3. They press the generate button.
4. The Flask application calls the OpenAI API.
5. The API produces a text and title candidates suited to Shizuka na Internet.
6. The system shows the result.
7. The person copies the whole body.
8. The person copies the title they choose.
9. The person pastes both into the posting form of Shizuka na Internet.
10. The person reads it once more and publishes.

## 5. System composition

### 5.1 Web server

- Use the Apache HTTP Server.
- Forward requests from Apache to the Flask application.
- Either WSGI or a reverse proxy is acceptable.
- HTTPS, access control and authentication are managed by Apache, according to the deployment.

### 5.2 Application

- Use Python and Flask.
- Keep the Flask application running on the server.
- Do not expose the Flask development server in production.
- Use a WSGI server or an application server that works with Apache.

### 5.3 External API

- Use the OpenAI API.
- Do not write the API key into the source or onto a screen.
- Read the API key from an environment variable or from a configuration file with restricted access.
- Receive the answer in a structured form, so that the body and the titles are separate.

## 6. Functional requirements

### 6.1 Input

The input screen carries:

- a field for the memo
- a generate button
- a button that clears the field

The field is a textarea that accepts several paragraphs.

The input may be:

- a single thought
- a list
- a fragment of a conversation
- an existing short text
- a memo of several paragraphs

### 6.2 Generation

From the input, the system produces:

- the whole post body
- the leading title
- other title candidates

The body and the titles belong to the same result and must agree with each other.

### 6.3 Showing the body

- Show the post body alone, in its own area.
- It must be copyable as it stands, straight into the posting form.
- Never mix an instruction to the AI, an editing note, an internal remark or a review result into the body.
- Produce the body as Markdown.
- Provide a button that copies the whole body.
- Do not let a label or an explanatory sentence on the screen fall inside what is copied.

### 6.4 Showing the titles

- Mark the leading title.
- Allow several candidates of differing character.
- Provide a copy button for each title.
- A rationale per title is not required in the initial specification.
- Do not add a word only for search, spread or clicks.

### 6.5 Regeneration

The result may miss the intent, so it must be possible to generate again. At a minimum:

- regenerate the whole text from the same input
- regenerate the titles alone

Letting the AI revise a part of the body is not required in the initial implementation.

### 6.6 Errors

Report these in a form the person understands:

- the input is empty
- the OpenAI API could not be reached
- the OpenAI API returned an error
- the answer had an unexpected shape
- a timeout occurred
- the server failed internally

Never show the API key, an internal path or a traceback on the screen.

## 7. Requirements on the writing

### 7.1 Position within the medium

The text is neither a stretched out microblog post nor a shrunk blog article. It is a piece of a few paragraphs that stands on its own.

A few paragraphs to a few thousand Japanese characters is the guide. Background, generalities, examples or a conclusion are not added to reach a length. What holds in a short text stays short.

### 7.2 Stance

A theme the writer already knows is not presented as a discovery.

The basic stances are:

- revisiting a familiar theme and sorting the thinking out again
- checking where the interest actually lies
- separating points that had been conflated
- stating what can and cannot be said at this moment
- closing naturally on an unsettled matter, when that is where things stand

### 7.3 Keeping the material

Keep, in preference to anything else:

- the concrete scene
- the subject
- the writer's own wording
- the hesitation in judgment
- the discomfort
- the question
- what is not settled

Never invent an experience, an emotion, a fact or a causal link in order to make the text tidier.

### 7.4 How much to explain

Explain the background only as far as the observations and thoughts in the text require.

Do not widen into:

- generalities
- an account of a whole system
- a glossary
- historical background
- a list of related cases
- a bibliography
- a systematic argument

No causal link and no generalization is added that the material does not carry. Before the text moves to a wide subject — 「社会では」, 「人間は」, 「私たちは」 — that move has to be needed, and it says no more than the particular observation supports.

### 7.5 Register

- The whole body is written in the Japanese desu/masu form, never in the plain form, whichever of the two the memo uses.
- Follow the voice of the memo in every other respect, and do not smooth it away while putting it into the desu/masu form.
- Do not shift into an academic, advertising or social media register.
- Avoid what is typical of generated text: a generic opening, a syllogism that is too neat, a safe summary, formulaic connectives.
- Do not bait the reader, put the conclusion first, repeat a keyword for the sake of search or call the reader to act.

### 7.6 Opening

Prefer to start from a concrete scene, subject, word or sensation.

Do not use an article style opening such as:

- 「今回は〜について書きます」
- 「この記事では〜を考えます」
- 「近年、〜が注目されています」
- 「皆さんは〜をご存じでしょうか」

When a familiar theme is being sorted out, a stance of "known for a while" or "thinking it over again" may of course be shown.

### 7.7 Ending

- Do not manufacture a lesson, a recommendation or a conclusion.
- What is undecided may be written as undecided.
- Do not read as abandoned halfway.
- Close where the thinking currently stands, so that the position is visible.
- Do not use formulas such as 「いかがだったでしょうか」 or 「ぜひ考えてみてください」.

### 7.8 Markdown

- Produce the body as Markdown.
- A short text normally carries no heading.
- When a heading is needed, use `##` or `###` only.
- Never use a `#` heading inside the body.
- Use lists, quotes and emphasis only where they are needed.
- Do not break a short text apart with small headings.
- Use a link only where the reader needs it to check the subject.
- Do not add a bibliography by default.
- Put a space between a full width character and an adjacent ASCII alphanumeric.

### 7.9 The shape of the text

- Three to six paragraphs is the usual shape, and fewer when the material is short.
- A paragraph is not added to fill the medium.
- One usual order: the scene, word or event that set it off; the discomfort, association or question it raised; what became visible after a little thought; the point where the text stops.
- That order follows the material rather than being applied mechanically, and a text with nothing settled may end on the question.

### 7.10 What is not looked up

- Research and the gathering of references are no part of the work. The text is written from the input alone.
- What has not been checked is not stated as established. Where a particular fact would have to be verified, the text writes around it or leaves the uncertainty visible.

### 7.11 What the text is judged on

In this order:

1. the observation or the thought of the input has not been altered
2. the concrete scene and the subject are still in the text
3. where the writer hesitated, and how far the thinking went, can be seen
4. it reads naturally as a piece of a few paragraphs
5. the notation and the grammar are correct

The first three are never given up for the sake of the last two.

## 8. Requirements on the titles

A title stays close to what the body actually contains:

- the scene
- the subject
- the words
- the question
- what caught the writer's attention
- where the thinking started
- the point that was sorted out again

The policy is:

- prefer a plain, direct title
- add no word for the sake of search, spread or clicks
- avoid a title that makes the content look settled
- avoid a question form suggesting a resolution the body does not reach
- when the matter is unsettled, an observed fact or the point where the thinking started makes a fine title
- do not force a symbolic, literary or sensational title
- when the content carries no natural title, a title made from the date is a candidate

The number of candidates:

- leading title: 1
- other candidates: at most 4

## 9. Screens

### 9.1 Input screen

At a minimum:

- the page title
- the memo field
- the generate button
- the button that clears the field

### 9.2 Result screen

At a minimum:

- the leading title
- the other title candidates
- a copy button per title
- the whole post body
- a copy button for the whole body
- a button that regenerates the whole text
- a button that regenerates the titles only
- a way back to the input screen

### 9.3 Copying

- A copy button copies the target string and nothing else.
- On success, show a short confirmation.
- On failure, leave the text selectable by hand.
- Preserve the line breaks and the Markdown of the body.

## 10. Non functional requirements

### 10.1 Security

- Never send the OpenAI API key to the client.
- Never put the key into the HTML, the JavaScript or the Git repository.
- Call the OpenAI API from the server only.
- When published, terminate HTTPS at Apache.
- Restrict the users with Basic authentication, IP restriction or a VPN as needed.
- If the input and the answers are logged, state the purpose and the retention period.
- Do not expose internal information on an error page.

### 10.2 Availability

- Run the Flask application as a service.
- Restart it automatically when the process ends.
- Start it automatically after a reboot.
- On an API failure, return an error to the person and run no subsequent step; there is none to run.

### 10.3 Maintainability

- Keep the writing prompt out of the application code.
- Manage the prompt as a standalone Markdown or text file.
- Allow the model name, the timeout and the output limit to be changed through a configuration file or environment variables.
- Keep the HTML templates, the CSS, the Python code and the prompt separate.
- Keep the application log separate from the Apache log.

### 10.4 Usability

- One input and one generation yield the body and the titles needed to post.
- From result to post, copying and pasting the body and a title is all that is needed.
- Separate the strings meant for posting from the supporting information.
- Assume both a phone and a desktop.

## 11. Persistence

Persisting the results is not required in the initial specification.

A later extension may store:

- the input
- the generated body
- the title candidates
- the time of generation
- the model used
- the history of regenerations
- the title the person chose
- whether it was posted

Even with persistence, nothing is sent to the posting site.

## 12. Scope of the initial implementation

1. Apache and Flask working together
2. the input screen
3. generation through the OpenAI API
4. showing the whole body
5. showing the title candidates
6. copying the whole body at once
7. copying each title
8. regenerating the whole text
9. regenerating the titles only
10. basic error handling
11. keeping the API key on the server

## 13. Out of scope for the initial implementation

- posting to Shizuka na Internet
- browser automation with Playwright, Selenium or the like
- storing credentials of the posting site
- scheduled posting
- posting to several media at once
- sharing to social networks
- image generation
- collecting references automatically
- external web search
- SEO for articles
- editing a published post
- retrieving the result of a post

## 14. Acceptance conditions

The initial specification is met when:

1. the person can enter a short text on a web page
2. pressing generate calls the OpenAI API
3. the whole body, suited to Shizuka na Internet, is shown
4. the body can be copied and pasted into the posting form as it stands
5. the leading title and several candidates are shown
6. the body and each title can be copied individually
7. no internal instruction or editing note of the AI leaks into the body
8. the body is not inflated into an explainer or a systematic essay
9. a familiar theme is not presented as a discovery
10. the person can post by copying, pasting and reading it once more
11. the system posts nothing by itself
12. the OpenAI API key never reaches the browser

## 15. Summary

The system runs on a server as a Flask application behind Apache.

A person enters a short text, and the OpenAI API produces the whole post body and several title candidates for Shizuka na Internet. The result is shown as a screen where the body and each title can be copied individually.

The person copies the title they choose and the whole body, pastes them into the posting form of Shizuka na Internet, reads them once more and publishes.

The system does not post, does not automate a browser and holds no credential of the posting site.
