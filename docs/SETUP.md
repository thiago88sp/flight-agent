# Setup guide

This guide takes you from zero to a working Flight Deal Agent with real prices, a smarter chat and
Telegram alerts that run on GitHub even when your computer is off. It works for **domestic
(Brazil) and international** flights. Every step says how to check
that it worked before moving on.

| Step | What you get | Needed? | Cost | Time |
|---|---|---|---|---|
| [1. Install the project](#1-install-the-project) | the web app with simulated prices | yes | free | 5 min |
| [2. Travelpayouts token](#2-travelpayouts-token-real-prices) | real prices + booking links on Aviasales | recommended | free | 5 min |
| [3. Gemini API key](#3-gemini-api-key-optional-smarter-chat) | a chat that understands free-form sentences | optional | free tier | 3 min |
| [4. Telegram bot](#4-telegram-bot-alerts-on-your-phone) | alerts on your phone | for price watches | free | 5 min |
| [5. First search](#5-run-the-app-and-make-a-first-search) | check that everything works together | yes | — | 2 min |
| [6. Price watch](#6-create-a-price-watch) | a saved search with a target price | for alerts | — | 1 min |
| [7. GitHub Actions](#7-run-the-watches-on-github-actions) | checks every 4 h with the computer off | for unattended alerts | free | 10 min |

All keys go into a local file called `.env`, which is **never committed** to git (it is listed in
`.gitignore`). On GitHub, the same keys are stored as encrypted **secrets**.

---

## 1. Install the project

**You need:** Python 3.10 or newer and git. On Windows, use WSL (Ubuntu).

1. Clone the repository and enter the folder:
   ```bash
   git clone https://github.com/thiago88sp/flight-agent.git
   cd flight-agent
   ```
2. Create a virtual environment and install the dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   > **WSL tip:** if the project lives under `/mnt/c` (for example inside OneDrive), installing
   > there is very slow. Create the venv on the Linux disk instead:
   > ```bash
   > python3 -m venv ~/.venvs/flight-agent
   > source ~/.venvs/flight-agent/bin/activate
   > pip install -r requirements.txt
   > ```
3. Create your `.env` from the template:
   ```bash
   cp .env.example .env
   ```
4. Start the web app:
   ```bash
   streamlit run app.py
   ```
   Open <http://localhost:8501> in your browser.

**✅ Check:** the sidebar footer says **⚠️ Demo mode: prices are examples, not real fares.** Click
one of the example buttons; you should see a result card with a **Book on Google Flights** button.
Everything works at this point, just with fake prices.

> **Consumer view vs. developer mode.** The web app is designed for travelers, so it hides
> technical details. While you are setting things up, you can turn them on by adding
> `DEV_MODE=true` to `.env` and restarting the app: the sidebar gets a **🛠️ Developer info** panel
> (price source, chat parser, limits), each chat answer shows which parser handled it, errors show
> their technical cause, and the price-watch panel shows the JSON for GitHub (step 7). Set it back
> to `false` before sharing the app with others.

---

## 2. Travelpayouts token (real prices)

Travelpayouts is the affiliate platform of Aviasales, a flight metasearch site (like Skyscanner or
Kayak). Its Data API is free and returns prices that other travelers recently found on Aviasales.

1. Go to <https://www.travelpayouts.com> and click **Sign up**. Register with your email or Google.
2. After registering, the site asks **"What would you like to monetize?"** and wants a link to your
   "main channel". This is an affiliate program, so it expects a website or social profile.
   For a personal or lab project, paste a link you own, for example
   `https://github.com/<your-user>` or your LinkedIn profile, then click **Continue** and answer the
   remaining questions with simple answers.
   - You do **not** need to install their "Drive" script or any affiliate tool.
3. You land on the dashboard, which says **"Create a Project to get started"**. You can ignore it:
   the Data API works without a project.
4. Open the token page directly: <https://app.travelpayouts.com/profile/api-token>
   (or click your profile at the bottom left → **API token**).
5. Copy the token (a 32-character string of letters and numbers).
6. Paste it into `.env`:
   ```env
   TRAVELPAYOUTS_TOKEN=your_32_character_token
   ```
7. Save the file and **restart** the web app (Ctrl+C in the terminal, then `streamlit run app.py`).

**✅ Check:** the **Demo mode** note disappears from the sidebar. Search for
`São Paulo to Lisbon next month, 10 days`; the offers now show real airlines (TAP, LATAM,
Royal Air Maroc...) and the button says **Book on Aviasales**. With `DEV_MODE=true`,
**🛠️ Developer info** shows **Prices: Travelpayouts (Aviasales cache)**.

From the command line:
```bash
python -m flight_agent "GRU to Lisbon in November, 10 days"
```
The output should list real airlines and a `Book: https://www.aviasales.com/...` link.

> **The Travelpayouts dashboard stays empty.** It only shows affiliate earnings (clicks, bookings,
> commissions). Data API calls never appear there; use the checks above instead.

> **Why not Amadeus?** Amadeus' free Self-Service portal was shut down; it now requires a company
> contract.

---

## 3. Gemini API key (optional, smarter chat)

Without this key the chat uses local rules, which understand sentences like
`GRU to Lisbon on Dec 10, 10 days, up to R$ 4000`. With Gemini, much freer sentences work too
("I'd like to see Rome sometime in spring, about two weeks, not too many connections").

1. Go to <https://aistudio.google.com> and sign in with a Google account.
2. Click **Get API key** (left menu, or the key icon at the bottom left).
3. Click **Create API key**. If asked, pick an existing Google Cloud project or let it create one
   (the default is "Default Gemini Project").
4. Copy the key.
5. Paste it into `.env`:
   ```env
   GEMINI_API_KEY=your_key
   ```
6. Save and restart the web app.

**✅ Check:** from the terminal,
```bash
python -m flight_agent "I'd like to see Rome sometime in March, about two weeks"
```
prints `[parsed by: gemini]` on the first line. If Gemini is slow or down it prints
`[parsed by: rules (fallback: gemini failed)]`: the app kept working with the local rules.
In the web app the same note appears under each chat answer when `DEV_MODE=true`.

Good to know:
- The Gemini **consumer subscription does not include an API key**. The key from AI Studio is
  separate and has a free tier with rate limits.
- The **Usage** page in AI Studio can take hours to show new requests, and you must select the
  same project the key belongs to (see **API keys** to know which one).
- On the free tier, Google may use the content you send to improve its products. This app only
  sends the search sentence.

---

## 4. Telegram bot (alerts on your phone)

The bot is what sends you the price alerts. It is created inside Telegram by talking to
**@BotFather**, Telegram's official bot for creating bots. This works the same on phone and desktop.

### 4.1 Create the bot and get the token

1. In Telegram, tap the **search** icon and type `BotFather`.
2. Open the one with the **blue verified badge** and the username exactly **@BotFather**
   (there are fake look-alikes).
3. Tap **Start**.
4. Send:
   ```
   /newbot
   ```
5. BotFather asks for the bot's **display name**. Anything works, e.g.:
   ```
   Flight Deal Agent
   ```
6. Then it asks for a **username**. It must be unique on Telegram and **end in `bot`**, e.g.:
   ```
   yourname_flights_bot
   ```
   If it answers "Sorry, this username is already taken", try another one.
7. On success, BotFather replies with something like:
   ```
   Done! Congratulations on your new bot. You will find it at t.me/yourname_flights_bot.
   ...
   Use this token to access the HTTP API:
   7123456789:AAH4x9Kq2ZyXwVuTsRqPoNmLkJiHgFeDcBa
   ```
8. Copy the **whole token**, including the digits and the colon, and put it into `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=7123456789:AAH4x9Kq2ZyXwVuTsRqPoNmLkJiHgFeDcBa
   ```

> ⚠️ **Most common mistake:** double-clicking the token selects only the part after the colon
> (`AAH4x9...`). The token must start with the digits: `7123456789:AAH...`. If the part before the
> colon is missing, the commands below say "TELEGRAM_BOT_TOKEN is incomplete".

### 4.2 Find your chat id

A bot can only message people who talked to it first.

1. Open your bot's link (`t.me/yourname_flights_bot`), tap **Start** and send **hi**.
2. In the terminal, inside the project folder:
   ```bash
   python -m flight_agent.watch --telegram-chat-id
   ```
   It prints something like:
   ```
   TELEGRAM_CHAT_ID=123456789   (Your Name)
   ```
   If it says "No messages found", send another message to the bot and run it again.
3. Copy that line into `.env`:
   ```env
   TELEGRAM_CHAT_ID=123456789
   ```

### 4.3 Test it

```bash
python -m flight_agent.watch --test
```

**✅ Check:** your phone receives *"✅ Flight Deal Agent connected. Your alerts will arrive here."*
You can also use **Send me a test alert** under **🔔 Price watches** in the web app sidebar.

### 4.4 Keep the token safe

- **Never share the token** or paste it in chats, issues or screenshots. Whoever has it controls
  the bot.
- If it leaks, send `/revoke` to @BotFather and pick your bot. You get a new token and the old one
  stops working immediately. Update `.env` (and the GitHub secret, step 7).

---

## 5. Run the app and make a first search

1. Start the app: `streamlit run app.py` and open <http://localhost:8501>.
2. Check that the sidebar no longer shows the **Demo mode** note (that means real prices are on).
3. Try a search in the chat, for example:
   ```
   São Paulo to Lisbon next month, 10 days
   ```
4. You should see:
   - a sentence confirming what was understood;
   - a **🏆 CHEAPEST** card with the price and a **Book on Aviasales** button;
   - **Other options** with their own **Book** buttons;
   - **📋 See all offers** with the full table.

If nothing is found, the app explains why, shows the **closest dates with a price** and offers a
button to check the exact dates on Google Flights. This is normal for dates more than 2–3 months
ahead: the free cache only knows what other travelers searched recently.

---

## 6. Create a price watch

1. Run a search (step 5).
2. Under the result, open **🔔 Watch this search and alert me when it drops**.
3. Set **Alert me at or below (R$)** (it suggests 10% below today's best price) and
   **Watch for (days)** (default 30).
4. Click **Create watch**.

**✅ Check:** a green message confirms the watch, and the sidebar shows **🔔 Price watches (1)**.

Check it right away from the terminal (this also sends a Telegram alert if the target is already met):
```bash
python -m flight_agent.watch           # checks every watch now
python -m flight_agent.watch --list    # shows target, end date and lowest price seen
```

Watches are saved in `watches.json`, which is local only (not committed). To run them while your
computer is off, continue with step 7.

---

## 7. Run the watches on GitHub Actions

The repository includes a workflow, [.github/workflows/watch.yml](../.github/workflows/watch.yml),
that checks your watches **every 4 hours** on GitHub's servers, for free.

### 7.1 Have the code in your own GitHub repository

If you cloned someone else's repository, create your own copy first: click **Fork** at the top of
the repository page (or create a new empty repository and push the code to it).

> On a fork, GitHub disables workflows by default. Open the **Actions** tab and click
> **I understand my workflows, go ahead and enable them**.

### 7.2 Add the secrets

Secrets are encrypted values that only the workflow can read. Nobody browsing the repository can
see them, not even on a public repository.

1. In your repository, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Fill **Name** and **Secret**, then click **Add secret**.
4. Repeat for each row:

| Name | Secret (value) |
|---|---|
| `TRAVELPAYOUTS_TOKEN` | the same value as in your `.env` |
| `TELEGRAM_BOT_TOKEN` | the same value as in your `.env` (the whole `digits:secret` line) |
| `TELEGRAM_CHAT_ID` | the same value as in your `.env` |
| `WATCHES` | the JSON of your watches (see below) |

**Getting the `WATCHES` JSON:** with `DEV_MODE=true` in `.env`, open **🔔 Price watches** in the web
app sidebar; under **Enable on GitHub** there is a code box with the JSON and a copy button. Or run:
```bash
python -m flight_agent.watch --export
```
Paste the whole line (it starts with `[` and ends with `]`).

> Why a secret and not a file? The repository is public and your watches reveal your travel plans
> (routes, dates, budget). The workflow's state (lowest price seen, last alert) is kept in the
> **Actions cache**, also outside the repository.

### 7.3 Run it once by hand

1. Open the **Actions** tab.
2. In the left list, click **price watches**.
3. Click **Run workflow** → keep branch **main** → **Run workflow**.
4. Wait about a minute and click the run that appears. Open the **check** job and the
   **Check prices** step.

**✅ Check:** the log shows one line per watch, for example:
```
GRU → LIS: lowest now R$ 4,035 (target R$ 3,600)
```
or, when the target is met, `ALERT sent (...)` and the message arrives on Telegram.

From now on it runs by itself every 4 hours (GitHub may start it a few minutes late).

### 7.4 Keep it up to date

- **Created or deleted a watch in the web app?** Copy the new JSON and update the `WATCHES` secret
  (Settings → Secrets → Actions → `WATCHES` → **Update**).
- **Revoked the Telegram token?** Update `TELEGRAM_BOT_TOKEN` too.
- GitHub **pauses scheduled workflows** on public repositories with no commits for 60 days. If you
  get an email about it, open **Actions → price watches** and click **Enable workflow**.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Sidebar still shows **Demo mode** after adding the token | `.env` not saved, or app not restarted | Save `.env` (Ctrl+S) and restart `streamlit run app.py` |
| **Prices are temporarily unavailable** | Travelpayouts is down, or the token is wrong (with `DEV_MODE=true` you see e.g. `HTTP 401`) | Wait a few minutes; if it persists, copy the token again from the API token page |
| **"I couldn't find flights"** with real prices | the free cache has no prices for those dates | Use the closest dates shown, widen flexibility, try a nearer month, or use the Google Flights button |
| **I don't know the place '...'** | a name that is not a known city, Brazilian state or airport code | Type a city (Florianópolis), a state (Santa Catarina) or the code (FLN); see the README glossary |
| **TELEGRAM_BOT_TOKEN is incomplete** | only the part after the colon was copied | Copy the whole line, starting with the digits |
| **Telegram rejected the token** | token revoked or mistyped | `/revoke` in @BotFather and use the new token |
| **No messages found** when getting the chat id | the bot never received a message from you | Send "hi" to the bot and run the command again |
| `[parsed by: rules (fallback: gemini failed)]` | Gemini timeout or quota | Nothing to do; it works with the rules. Check the key if it happens every time |
| Workflow log: **no offers right now** | same as the cache case above | Normal for far-away dates; the watch keeps checking |
| Workflow fails reading `WATCHES` | the secret is not valid JSON | Paste the export again, the whole line from `[` to `]` |
| No scheduled runs anymore | GitHub paused the schedule after 60 days without commits | Actions → price watches → **Enable workflow** |

## Security checklist

- [ ] `.env` is not committed (`git status` never lists it).
- [ ] Keys exist only in `.env` and in GitHub secrets, never in code, issues or chats.
- [ ] Watches are in the `WATCHES` secret, not in a committed file.
- [ ] If a key leaked: revoke it (Telegram `/revoke`, a new Travelpayouts token, delete the Gemini
      key in AI Studio) and update `.env` and the secrets.
