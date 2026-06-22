# Reading Schema

Extends `_shared/base-schema.md`.

## Domain-Specific Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| character | wiki/characters/ | A fictional character profile |
| theme | wiki/themes/ | A major idea or motif in the work |
| plot_thread | wiki/plot-threads/ | A narrative arc or subplot |
| chapter | wiki/chapters/ | Chapter-level notes and analysis |

## Domain-Specific Frontmatter

### character
```yaml
type: character
role: protagonist | antagonist | supporting | minor | narrator
arc: static | dynamic | flat | round
species: ""            # if applicable (human, elf, AI, etc.)
affiliations: []       # groups, organizations, factions
relationships: {}      # map of character-slug -> relationship-type
first_appearance: ""   # chapter slug
status: alive | deceased | unknown | ambiguous
```

### theme
```yaml
type: theme
category: social | philosophical | psychological | political | religious | existential | aesthetic
related_characters: []  # slugs of characters embodying this theme
motifs: []              # recurring symbols/images related to the theme
conflicting_themes: []  # slugs of opposing themes
```

### plot_thread
```yaml
type: plot_thread
status: introduced | developing | climax | resolved | cliffhanger
primary_characters: []  # slugs of main characters in this thread
conflict_type: person_vs_person | person_vs_self | person_vs_society | person_vs_nature | person_vs_fate
resolution: ""          # how the thread resolves (if resolved)
```

### chapter
```yaml
type: chapter
chapter_number: 0
part: ""               # optional: book part/section
pov_character: ""      # slug of POV character (if applicable)
setting: ""            # location(s) in the chapter
timeframe: ""          # when the chapter takes place
word_count: 0          # optional
key_events: []         # brief list of major events
```

## Extra Directories

See `extra-dirs.json`.
