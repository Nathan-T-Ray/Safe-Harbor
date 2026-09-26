# Anthropic `frontend-design` — distilled checklist

Source: https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md (also packaged at https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design)

Content was rephrased for compliance with licensing restrictions.

## 1. Before touching CSS: write a mini plan
- Name the subject, audience and main job of the screen. Safe Harbor: scientists/reviewers judging whether a genomic "safe harbor" candidate is supported by evidence; main job = read a conclusion and trace it to evidence.
- Token plan: 4–6 named hex colors, typeface roles, a layout sketch (ASCII is fine) with alignment rules, and 2–3 principles unique to this product.
- Review the plan: if a choice is what you'd output for any dashboard, change it and say why. Where the user/brief pins a look, follow it exactly.

## 2. Typography
- One or two families; if two, they must be clearly different (repo uses Manrope headings + DM Sans body — keep unless asked).
- Use a deliberate type scale with intentional weights; don't pile up near-equal sizes.
- Keep prose lines under ~80 characters (conclusion text, drawer paragraphs).
- Avoid generic tells: highlighting one word in a headline, all-caps labels by default, extra labels stacked above content.

## 3. Structure encodes meaning
- Borders, numbering, eyebrows, dividers must carry information. Numbered markers only for real sequences (the 5-stage pipeline qualifies; candidate cards numbered 01/02 only if rank matters).
- Don't chop everything into identical rounded cards with the same radius and same soft shadow; vary radius/elevation by hierarchy.

## 4. AI-design tells to avoid (unless the brief asks)
- Near-black background with one acid accent; cream + serif + terracotta; hairline newspaper grid; SaaS card kit with gradient washes.
- Tracked ALL-CAPS eyebrow over every heading; `A · B · C` meta strings; `WORD — fragment` labels; `→` appended to buttons; mono font for every small data label.
- For Safe Harbor: mono is justified for coordinates, hashes and sequences (real data), not for general labels.

## 5. Motion
- Ambient motion only to draw attention, once. No fade-slide on every section, no hover animation on every card.
- Motion that answers a user action (open drawer, expand, confirm) is good when it shows what changed.

## 6. Restraint + quality floor
- Put boldness in one place (e.g. the conclusion panel); keep the rest quiet. Remove one decoration before shipping.
- Non-negotiable floor: works down to mobile, visible keyboard focus, `prefers-reduced-motion` respected, accessible contrast, harmonious palette.
- Screenshot and critique your own output while building.
- CSS: watch selector specificity so class rules don't cancel each other (common with spacing between sections).

## 7. UX copy
- Name things in user terms, not system terms ("Open run" is fine; avoid exposing internal field names as labels).
- Active voice; buttons state the exact result; keep the same verb through the flow (button "Export" → toast "Exported").
- Errors say what happened and how to fix it; never vague, never apologetic. Empty states invite the next action.
- Sentence case, plain verbs, one job per string.
