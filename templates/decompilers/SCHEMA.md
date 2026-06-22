# Decompilers Schema

Extends `_shared/base-schema.md`.

## Domain-Specific Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| format_spec | wiki/formats/ | Binary file format specification (PE, ELF, Mach-O) |
| opcode | wiki/opcodes/ | Single instruction: mnemonic, encoding, operands, stack effect |
| tool | wiki/tools/ | Decompiler or analysis tool |
| finding | wiki/findings/ | Research discovery or observation |

## Domain-Specific Frontmatter

### format_spec
```yaml
type: format_spec
architecture: x86 | x64 | arm | mips | wasm | other
format_type: executable | object | archive | firmware | debug
magic: ""             # file magic bytes (hex)
endianness: little | big
spec_version: ""      # e.g., "ELF 1.2"
```

### opcode
```yaml
type: opcode
mnemonic: ""          # e.g., "MOV", "JMP", "CALL"
architecture: x86 | x64 | arm | mips | wasm | other
encoding: ""          # byte encoding pattern (hex)
operands: []          # list of operand descriptions
stack_effect: ""      # effect on stack (e.g., "pop 2, push 1")
class: data_movement | arithmetic | control_flow | stack | floating_point | system
```

### tool
```yaml
type: tool
vendor: ""            # author or organization
license: proprietary | open_source | freeware
language: ""          # implementation language
platforms: []         # Windows, Linux, macOS
supports: []          # architectures/formats
```

### finding
```yaml
type: finding
severity: info | warning | critical
tool: ""              # slug of related tool page (optional)
related_opcodes: []   # slugs of related opcode pages
confidence: high | medium | low
```

## Extra Directories

See `extra-dirs.json`.
