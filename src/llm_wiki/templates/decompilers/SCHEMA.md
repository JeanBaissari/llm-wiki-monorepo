# Decompilers Domain Schema

Extends the base schema with decompiler-specific page types,
directories, and frontmatter conventions.

## Inherited Base Types

All base page types from `_shared/base-schema.md` are available:

| Type | Directory | Purpose |
|------|-----------|---------|
| `entity` | `wiki/entities/` | Named things — tool authors, companies, processor vendors |
| `concept` | `wiki/concepts/` | Ideas — SSA form, control-flow graphs, type recovery, lifting |
| `source` | `wiki/sources/` | Academic papers, tool documentation, conference talks |
| `comparison` | `wiki/comparisons/` | Side-by-side analysis of decompilers or analysis techniques |
| `synthesis` | `wiki/synthesis/` | Cross-cutting summaries and conclusions |
| `overview` | `wiki/` | High-level project summary |

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/formats/` | Binary file format specifications |
| `wiki/opcodes/` | Instruction set opcode documentation |
| `wiki/tools/` | Decompiler and analysis tool records |
| `wiki/findings/` | Research discoveries and observations |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `format_spec` | `wiki/formats/` | Binary file format specification (PE, ELF, Mach-O) | `architecture: x86 \| x64 \| arm \| mips \| wasm \| other`, `format_type: executable \| object \| archive \| firmware \| debug`, `magic`, `endianness: little \| big`, `spec_version` |
| `opcode` | `wiki/opcodes/` | Single instruction: mnemonic, encoding, operands, stack effect | `mnemonic`, `architecture`, `encoding`, `operands: []`, `stack_effect`, `class: data_movement \| arithmetic \| control_flow \| stack \| floating_point \| system` |
| `tool` | `wiki/tools/` | Decompiler or analysis tool | `vendor`, `license: proprietary \| open_source \| freeware`, `language`, `platforms: []`, `supports: []` |
| `finding` | `wiki/findings/` | Research discovery or observation | `severity: info \| warning \| critical`, `tool`, `related_opcodes: []`, `confidence: high \| medium \| low` |

## Naming Conventions

- **Format specs:** `format-name.md` (e.g., `pe.md`, `elf.md`, `mach-o.md`)
- **Opcodes:** `architecture-mnemonic.md` (e.g., `x86-mov.md`, `arm-ldr.md`)
- **Tools:** `tool-name.md` (e.g., `ghidra.md`, `idapro.md`, `binary-ninja.md`)
- **Findings:** `brief-discovery-description.md` (e.g., `ghidra-arm-constant-propagation.md`)

## Frontmatter Template

```yaml
---
type: format_spec | opcode | tool | finding
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Format Spec-specific
```yaml
type: format_spec
architecture: x64
format_type: executable
magic: "7f 45 4c 46"
endianness: little
spec_version: "ELF 1.2"
```

### Opcode-specific
```yaml
type: opcode
mnemonic: "MOV"
architecture: x64
encoding: "8B /r"
operands:
  - "reg/mem"
  - "reg"
stack_effect: "none"
class: data_movement
```

### Tool-specific
```yaml
type: tool
vendor: "Hex-Rays"
license: proprietary
language: "C++"
platforms:
  - "Windows"
  - "Linux"
  - "macOS"
supports:
  - "x86"
  - "x64"
  - "ARM"
  - "MIPS"
```

### Finding-specific
```yaml
type: finding
severity: warning
tool: ghidra
related_opcodes:
  - arm-ldr
confidence: medium
```

## Conventions

1. Every format spec should document the file magic bytes, header structure, section/segment layout, and any known quirks.
2. Opcode pages should document encoding, operand types, and processor flag effects.
3. Tool pages should record the vendor, license, supported architectures, and any notable limitations.
4. Findings should link to the tool(s) and opcode(s) they relate to.
5. When a new tool version adds architecture support, update the tool page and link to the relevant format or opcode pages.
