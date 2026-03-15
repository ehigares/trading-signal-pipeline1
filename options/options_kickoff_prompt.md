# Options Pipeline — Session 1 Kickoff Prompt
# Copy and paste this entire prompt into Claude Code to start the build.

---

You are building a new automated options signal pipeline.
This is a separate system from the existing stocks pipeline but shares the same infrastructure.

## Your First Actions (Before Writing Any Code)

Read these files in this exact order:

1. Read `stocks/CLAUDE.md` — understand the shared Droplet, GitHub repo, .env file, and deployment process
2. Read `options/CLAUDE.md` — understand the options-specific rules, filters, and logic
3. Read `options/dev_journal.md` — check the setup checklist and understand current status
4. Read `options/build_spec.md` — this is your blueprint for every script you will build

Do not write a single line of code until you have read all four files.

---

## What You Are Building

A new pipeline inside the `options/` folder of the existing GitHub repo.
It runs independently from the stocks pipeline.
It delivers options trading signals to a separate Slack channel (#options-signals).
It logs to a separate tab (Options Signal Log) in the existing Google Sheet.

---

## Session 1 Goals

1. Confirm the `options/` folder exists and all 4 documents are present
2. Check that the existing stocks pipeline is still intact (verify stocks/ folder untouched)
3. Add the following new keys to the existing `.env` file:
   - `OPTIONS_SLACK_WEBHOOK_URL` (user will provide this)
   - `OPTIONS_N8N_WEBHOOK_URL` (you will generate this after building the n8n workflow)
4. Create `options/requirements.txt` with initial required packages
5. Build the n8n Options Signal Logger workflow via MCP
6. Confirm n8n webhook URL and add to .env as OPTIONS_N8N_WEBHOOK_URL
7. Verify Options Signal Log tab exists in Google Sheet (create if missing)
8. Begin Phase 1: Build fetch_options_news.py and options_universe.py

---

## Before Starting Phase 1, Ask the User

"Please provide your OPTIONS_SLACK_WEBHOOK_URL. You can get this from api.slack.com/apps by creating a new incoming webhook pointed at your #options-signals channel."

Wait for the user to provide this before proceeding.

---

## Rules to Follow

- Never modify any file in the stocks/ folder
- Never modify the existing n8n Droplet
- Add new .env keys without removing existing ones
- Verify every script before moving to the next phase
- Update options/dev_journal.md at the end of this session
- Push all new files to GitHub before ending the session

---

## Success Criteria for Session 1

- [ ] All 4 options documents confirmed present
- [ ] stocks/ folder confirmed untouched
- [ ] OPTIONS_SLACK_WEBHOOK_URL in .env
- [ ] OPTIONS_N8N_WEBHOOK_URL in .env
- [ ] options/requirements.txt created
- [ ] n8n Options Signal Logger workflow active and tested
- [ ] Options Signal Log tab exists in Google Sheet
- [ ] fetch_options_news.py built, tested, produces valid options_news.json
- [ ] options_universe.py built, tested, produces valid options_candidates.json
- [ ] Both scripts pushed to GitHub and verified on Droplet
- [ ] dev_journal.md updated with session notes
