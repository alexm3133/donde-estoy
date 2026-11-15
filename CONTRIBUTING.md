# Contributing

Thanks for wanting to help. This is a small project with a clear goal: tell
the person waiting when the runner will arrive, reliably and without fuss.

## Getting set up

Follow [Local development](README.md#local-development) in the README. You
do not need Docker or PostgreSQL to work on the code.

## Before you open a pull request

Run the same checks CI runs:

```bash
cd backend && ruff check . && ruff format --check . && pytest
```

```bash
cd frontend && npm run lint && npm test && npm run build
```

Then:

- Keep pull requests focused: one change, explained in a few sentences.
- Add or update tests for behaviour changes. Changes to the ETA engine
  (`backend/app/eta`) always need a test that shows the improvement.
- UI changes: include a screenshot (phone width, dark theme at least).

## Ground rules for the code

- **Readable first.** Comment *why*, not *what*. Someone new should be able to
  follow a module top to bottom.
- **The ETA engine stays pure.** No I/O, no clock, no database inside
  `backend/app/eta`.
- **Design tokens only.** Colours, sizes and spacing come from
  `frontend/src/theme/tokens.css`; do not hard-code them in components.
- **All user-facing text is translated.** Add every string to the three files
  in `frontend/src/i18n/locales` (a test fails if keys differ).
- **Accessibility is not optional.** WCAG AA contrast, visible focus, labels on
  controls, tap targets of at least 44 px. Many viewers are older people on a
  phone.
- **Privacy by default.** Do not add analytics, third-party requests or new
  stored data without discussing it in an issue first.

## Useful contributions

- **Translations**: copy `frontend/src/i18n/locales/en.json`, translate, and
  register the language in `frontend/src/i18n/index.ts`.
- **Real-world ETA cases**: a GPX recording of your own outing (with
  timestamps) turned into a test tells us where the model is wrong.
- **Native builds**: a Capacitor background-geolocation provider implementing
  `frontend/src/location/LocationProvider.ts`.

## Reporting bugs

Open an issue with what you did, what you expected and what happened. For ETA
problems, the route profile (distance, climb) and how far off the estimate was
are the most useful details. Never post a live share link in an issue.

## Security

If you find a vulnerability (for example, a way to read someone's location
without their link), please do not open a public issue. Use GitHub's private
vulnerability reporting on this repository instead.
