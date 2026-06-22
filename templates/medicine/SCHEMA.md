# Medicine Schema

Extends `_shared/base-schema.md`.

## Domain-Specific Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| condition | wiki/conditions/ | Medical condition: etiology, diagnostics, management |
| treatment | wiki/treatments/ | Therapeutic intervention |
| study | wiki/studies/ | Structured clinical research record |
| term | wiki/terminology/ | Precise medical term definition |

## Domain-Specific Frontmatter

### condition
```yaml
type: condition
icd_code: ""           # ICD-10 code if applicable
category: infectious | cardiovascular | neurological | oncological | endocrine | respiratory | gastrointestinal | musculoskeletal | psychiatric | other
chronic: true | false
contagious: true | false
prevalence: ""         # e.g., "~1 in 10,000"
mortality_rate: ""     # optional
```

### treatment
```yaml
type: treatment
modality: pharmacological | surgical | behavioral | radiation | alternative | supportive
condition: ""          # slug of primary condition it treats
mechanism: ""          # mechanism of action
effectiveness: established | investigational | experimental | controversial
side_effects: []       # list of common side effects
```

### study
```yaml
type: study
design: RCT | cohort | case_control | meta_analysis | systematic_review | case_series | cross_sectional
sample_size: 0
population: ""         # study population description
intervention: ""       # what was tested
control: ""            # control/comparator
outcome: ""            # primary outcome measure
significance: ""       # p-value, CI, or other significance metric
effect_size: ""        # optional: odds ratio, hazard ratio, etc.
follow_up: ""          # optional: follow-up duration
registry: ""           # optional: ClinicalTrials.gov ID
```

### term
```yaml
type: term
field: anatomy | pharmacology | pathology | diagnostics | physiology | classification
abbreviation: ""       # if applicable
synonyms: []           # alternative names
see_also: []           # slugs of related pages
```

## Extra Directories

See `extra-dirs.json`.
