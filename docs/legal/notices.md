# Notice

This project incorporates third-party components under various open-source licenses. Required attribution notices are provided below.

## Licenses in Use

This project as a whole is distributed under the MIT license (see [LICENSE](../../LICENSE)). Individual dependencies carry their own licenses as noted.

## Vendored Components (Browser Extension)

Two third-party libraries are vendored as standalone files under `extension/` (not consumed as npm packages):

- **Readability.js** (`extension/Readability.js`) — Mozilla Readability — **Apache-2.0**, Copyright © 2010 Arc90 Inc. The Apache-2.0 license header is retained in the vendored file. Apache-2.0 requires that any upstream `NOTICE` file be preserved with distributions of the work; this section is the attribution record for the vendored copy.
- **Turndown.js** (`extension/Turndown.js`) — Turndown — **MIT**, Copyright © Dom Christie. The MIT permission notice is retained in the vendored file.

Both are consumed unmodified as vendored bundles for the Chrome extension's article extraction and HTML→Markdown conversion.

## MIT-Licensed Dependencies

The following dependencies are licensed under the MIT License. The MIT License requires preservation of copyright and permission notices. Copyright holders are listed where known.

- **graphology** — Copyright © Graphology contributors. MIT License.
- **graphology-communities-louvain** — Copyright © Graphology contributors. MIT License.
- **@modelcontextprotocol/sdk** — Copyright © Anthropic. MIT License.
- **sql.js** — Copyright © sql.js contributors. MIT License.
- **better-sqlite3** — Copyright © Joshua Wise. MIT License.
- **express** — Copyright © OpenJS Foundation. MIT License.
- **js-yaml** — Copyright © nodeca. MIT License.
- **katex** — Copyright © Khan Academy. MIT License.
- **markdown-it** — Copyright © Vitaly Puzrin. MIT License.
- **markdown-it-attrs** — Copyright © Arve Seljebo. MIT License.
- **markdown-it-texmath** — Copyright © Stefan Gössner. MIT License.
- **mermaid** — Copyright © Knut Sveidqvist. MIT License.
- **sigma** — Copyright © Alexis Jacomy and contributors. MIT License.
- **zod** — Copyright © Colin McDonnell. MIT License.
- **openai** — Copyright © OpenAI. MIT License.
- **anthropic** — Copyright © Anthropic. MIT License.
- **litellm** — Copyright © BerriAI. MIT License.
- **instructor** — Copyright © Jason Liu. MIT License.
- **pydantic** — Copyright © Pydantic Team. MIT License.
- **tomli** — Copyright © Taneli Hukkinen. MIT License. Core dependency on Python 3.10 only (`tomllib` is stdlib on 3.11+).
- **model2vec** — Copyright © 2024 Thomas van Dongen. MIT License. Optional `[semantic]` extra.
- **graspologic** — Copyright © Microsoft Corporation. MIT License. Optional `[leiden]` extra.
- **splink** — Copyright © UK Ministry of Justice. MIT License. Optional `[entity-resolution]` extra.
- **onnxruntime** — Copyright © Microsoft Corporation. MIT License. Optional `[ner]` extra.
- **esbuild** — Copyright © Evan Wallace. MIT License.
- **pytest** — Copyright © pytest-dev. MIT License.
- **pytest-cov** — Copyright © pytest-cov contributors. MIT License.
- **vcrpy** — Copyright © Kevin McCarthy. MIT License.

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Apache-2.0-Licensed Dependencies

The following dependencies are licensed under the Apache License, Version 2.0.

- **tenacity** — Copyright © Julien Danjou. Apache-2.0.
- **typescript** — Copyright © Microsoft Corporation. Apache-2.0.
- **gliner** — Copyright © Urchade Zaratiana. Apache-2.0. Optional `[ner]` extra.
- **deepeval** — Copyright © Confident AI. Apache-2.0. Optional `[eval]` extra.

```
Apache License, Version 2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

## BSD-3-Clause-Licensed Dependencies

- **portalocker** — Copyright © 2023, Rick van Hattem. BSD-3-Clause.
- **networkx** — Copyright © NetworkX contributors. BSD-3-Clause.
- **numpy** — Copyright © 2005-2023, NumPy Developers. BSD-3-Clause. Optional `[semantic]` extra.

```
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
```

## ISC-Licensed Dependencies

- **d3-drag** — Copyright © Mike Bostock. ISC License.
- **d3-force** — Copyright © Mike Bostock. ISC License.
- **d3-selection** — Copyright © Mike Bostock. ISC License.
- **d3-zoom** — Copyright © Mike Bostock. ISC License.

```
ISC License

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

## Unlicense (Public Domain)

- **markdown-it-anchor** — Copyright © Val (valeriangalliat). Released under the Unlicense (public domain dedication).

## EPL-2.0-Licensed Dependencies

- **elkjs** — Copyright © Ulf Rüegg and contributors. Eclipse Public License 2.0 (EPL-2.0). Transitive dependency of `mermaid` (ELK graph layout); consumed unmodified as an npm package, not forked or modified. EPL-2.0 is a weak-copyleft license; the unmodified-binary distribution obligation is satisfied by this notice and the upstream source at https://www.eclipse.org/legal/epl-2.0/.

## Dual-Licensed Dependencies (License Elections)

Where a dependency offers a choice of licenses, this project elects the most permissive option:

- **dompurify** — Copyright © Dr.-Ing. Mario Heiderich, Cure53. Dual-licensed `(MPL-2.0 OR Apache-2.0)`; this project elects **Apache-2.0**. Transitive dependency of `mermaid` (HTML sanitization), consumed unmodified.
- **sqlite-vec** — Copyright © Alex Garcia. Dual-licensed `(MIT OR Apache-2.0)`; this project elects **MIT**. Optional `[semantic]` extra (SQLite vector extension with a pure-numpy KNN fallback, ADR-0016).
- **jszip** — Dual-licensed `(MIT OR GPL-3.0-or-later)`; this project elects **MIT**. jszip was a transitive dependency of the code-analysis surface removed in v0.6.4 (ADR-0035) and is not part of the current dependency closure; the election is recorded here should it be reintroduced.

## GPL-3.0 Upstream References

The following upstream projects were referenced for methodology and design. Their licenses are provided for attribution purposes only; no GPL-licensed code is incorporated into this project's distributed artifacts.

- **nashsu/llm_wiki** (https://github.com/nashsu/llm_wiki) — GPL-3.0. Referenced for graph relevance model design; the graph-engine files are independent clean-room MIT implementations (see [provenance.md](provenance.md#graph-engine--upstream-references--clean-room-reimplementations) for provenance disposition).
- **nashsu/llm_wiki_skill** (https://github.com/nashsu/llm_wiki_skill) — GPL-3.0. Referenced for API contract methodology.

---

This file was regenerated for the **v0.6.5 clean-room closure review** (provenance reimplements landed in v0.6.4; dependency rows reconciled against `pyproject.toml` and each project's official license). Licenses and attributions should be verified before each public release.
