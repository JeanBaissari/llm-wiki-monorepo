// LLM Wiki Clipper — Chrome Extension Popup
// Uses Readability.js + Turndown.js to extract clean markdown from web pages
// Saves to the wiki's raw/ directory via the MCP server or local filesystem

const statusEl = document.getElementById('status');
const clipBtn = document.getElementById('clipBtn');

function status(msg, cls = '') {
  statusEl.textContent = msg;
  statusEl.className = cls;
}

// Load saved settings
chrome.storage.local.get(['wikiPath', 'saveFolder', 'autoIngest', 'mcpUrl'], (data) => {
  if (data.wikiPath) document.getElementById('wikiPath').value = data.wikiPath;
  if (data.saveFolder) document.getElementById('folder').value = data.saveFolder;
  if (data.autoIngest !== undefined) document.getElementById('autoIngest').checked = data.autoIngest;
  if (data.mcpUrl) document.getElementById('mcpUrl').value = data.mcpUrl;
});

clipBtn.addEventListener('click', async () => {
  const wikiPath = document.getElementById('wikiPath').value.trim();
  const folder = document.getElementById('folder').value;
  const autoIngest = document.getElementById('autoIngest').checked;
  const mcpUrl = document.getElementById('mcpUrl').value.trim();

  if (!wikiPath) {
    status('Please enter a wiki path', 'error');
    return;
  }

  // Save settings
  chrome.storage.local.set({ wikiPath, saveFolder: folder, autoIngest, mcpUrl });

  status('Clipping...');

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Inject Readability + Turndown into the page
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['Readability.js', 'Turndown.js'],
    });

    // Extract readable content
    const extractResult = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractContent,
      args: [tab.title, tab.url],
    });

    const { markdown, title } = extractResult[0].result;
    const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
    const filename = `${slug}.md`;
    const filePath = `${folder}/${filename}`;

    // Try MCP server first
    let saved = false;
    try {
      const resp = await fetch(`http://127.0.0.1:19828/api/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectPath: wikiPath,
          path: filePath,
          content: markdown,
        }),
      });
      if (resp.ok) saved = true;
    } catch {
      // MCP server not running — fall back to download
    }

    if (saved) {
      status(`✓ Saved to ${filePath}`, 'success');
    } else {
      // Fallback: download the markdown file
      const blob = new Blob([markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      await chrome.downloads.download({
        url,
        filename: `wiki-imports/${filePath}`,
        saveAs: false,
      });
      status(`⬇ Downloaded ${filename} — move to ${folder}/`, 'success');
    }

    // Auto-ingest
    if (autoIngest && saved) {
      status('Ingesting...', '');
      try {
        const ingestResp = await fetch(`${mcpUrl.replace(/\/+$/, '')}/api/ingest`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            wiki_root: wikiPath,
            source_path: filePath,
          }),
        });
        if (ingestResp.ok) {
          status(`✓ Saved + ingested`, 'success');
        } else {
          const errText = await ingestResp.text().catch(() => 'unknown error');
          status(`✓ Saved, ingest failed: ${errText}`, 'error');
        }
      } catch (err) {
        status(`✓ Saved, ingest unavailable (${err.message})`, 'error');
      }
    }
  } catch (err) {
    status(`Error: ${err.message}`, 'error');
  }
});

// Injected into the page to extract content
function extractContent(pageTitle, pageUrl) {
  try {
    const documentClone = document.cloneNode(true);
    const reader = new Readability(documentClone);
    const article = reader.parse();

    const turndownService = new TurndownService({
      headingStyle: 'atx',
      codeBlockStyle: 'fenced',
    });
    const markdown = turndownService.turndown(article.content);

    // Add frontmatter
    const frontmatter = [
      '---',
      `source_url: "${pageUrl}"`,
      `ingested: ${new Date().toISOString().slice(0, 10)}`,
      `source_type: article`,
      '---',
      '',
    ].join('\n');

    return {
      title: article.title || pageTitle || 'Untitled',
      markdown: frontmatter + `# ${article.title || pageTitle}\n\n**Source:** [${pageTitle}](${pageUrl})\n\n` + markdown,
    };
  } catch (err) {
    return { title: 'Error', markdown: `Error extracting content: ${err.message}` };
  }
}
