# Instapaperss FastAPI

**Development in progress.**

A small service for Instapaper / Kobo users to:

- Push RSS feed items into Instapaper
- Keep Instapaper bookmarks tidy with tags and cleanup rules

This project is a thin wrapper around the Instapaper Full API with RSS feed integration.

## Features

- Fetch items from configured RSS feeds and save them to Instapaper
- Basic bookmark housekeeping (archive/renmove saved items)

## Roadmap / To‑do

- [ ] `POST /save` endpoint to:
  - [ ] Accept any feed URL
  - [ ] Push new items from that feed to Instapaper
  - [ ] Customize tags per feed
- [ ] API documentation
