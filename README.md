# Scraper MCP

Turn documentation websites and your own files into a searchable library. Scraper MCP lets you collect content, organize it by topic or project, and find relevant passages with links back to their sources.

Use the browser interface to get started, or connect an AI assistant through MCP (Model Context Protocol) so it can search the same documentation while helping you work.

You can:

- Add individual web pages or follow links across a documentation site.
- Upload documents, including PDFs, Word files, spreadsheets, and API specifications.
- Keep separate libraries for different projects using **namespaces**.
- Search in natural language instead of needing exact keywords.

Search returns passages from the content you have added, not generated answers or live web search results. You do not need an AI account or API key to use the browser interface.

## Quick start: use it in your browser

### 1. Install the prerequisites

You need:

- **Git** to download the project.
- **uv** to install and run the Python dependencies. See the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).
- **Python 3.13 or newer**. uv can download a compatible Python version if one is not available.
- **Node.js 22 or newer**, with **npm**, to build the browser interface. Get them from the [Node.js download page](https://nodejs.org/en/download).

You need an internet connection for installation and the initial search-model download, as well as to fetch web pages. The first indexing operation may take longer while the model downloads.

### 2. Download and prepare the project

Open a terminal and run:

```bash
git clone https://github.com/uzilan/scraper-mcp.git
cd scraper-mcp
uv sync --locked
cd ui
npm ci
npm run build
cd ..
```

If you already have the project, skip the clone and start from its `scraper-mcp` directory. You only need to build the interface again after updating its code.

### 3. Start the server

From the `scraper-mcp` directory, run:

```bash
uv run python server.py
```

Leave this terminal open, then visit **[http://localhost:8000/ui/](http://localhost:8000/ui/)** in your browser. If the server is quiet, that is normal; open the browser to check that it is ready.

Press **Ctrl+C** in the terminal to stop the server. To use it again, run the same command; you do not need to reinstall dependencies.

## Try your first search

Start with a file so you can try the complete workflow without choosing a website:

1. In the **Namespace** panel, enter `my-docs` in the **new namespace…** field and click **Add**. A namespace is simply a named library; creating one selects it automatically.
2. Click the **+** beside **Documents** and upload this project's `README.md`. You can also drag a file onto the Documents panel.
3. Wait for the upload to finish and the filename to appear in the list.
4. Select **Search**, type `How do I start the server?`, and press **Enter**.
5. Read the matching passages and follow their source links to view the original content.

Search covers only the selected namespace. To work with another library, click its name in the Namespace panel.

Namespace names must be 3–63 characters long, use only letters, numbers, hyphens, or underscores, and start and end with a letter or number. For example: `my-docs`, `payments-api`, or `team_notes`.

## Add your own content

### Documentation websites

Select a namespace, then choose a tool from the top bar:

| Tool | What to do |
| --- | --- |
| **Index Page** | Paste a page URL and press Enter to make that page searchable. This is the best place to start with a new site. |
| **Index Tree** | Paste a starting URL to index it and follow links on the same domain. Start with a small **Depth**, such as `1`, before collecting more pages. |
| **Discover Links** | Preview reachable URLs without adding their content to your library. Use it to check what a crawl might include. |

**Depth** controls how many links away from the starting page the crawl can go. Larger values can collect many more pages, including pages outside the documentation section if they share the same domain. Only index content you are permitted to access and collect.

Wait for indexing to finish before searching. For API documentation, you can provide an OpenAPI/Swagger specification URL or upload its JSON or YAML file.

### Files

Use the **+** button beside Documents or drag files onto that panel. Uploaded files become searchable in the selected namespace automatically.

Supported file types:

- **PDF:** `.pdf` with extractable text; scanned images need OCR elsewhere first.
- **Word:** `.docx` (convert older `.doc` files first).
- **Excel:** `.xlsx`.
- **Text and Markdown:** `.txt`, `.md`.
- **JSON and YAML**, including OpenAPI/Swagger specifications: `.json`, `.yaml`, `.yml`.

## Use it with an AI assistant through MCP

The browser is optional. If your assistant supports **local MCP servers over stdio**, it can start Scraper MCP and use its tools directly. Node.js and the interface build are only needed if you also want the browser interface.

After cloning the project and running `uv sync --locked`, add a server to your assistant's MCP settings with:

- **Name:** `scraper`
- **Command:** `uv` (use its full executable path if your assistant cannot find it)
- **Arguments:** `run`, `--directory`, `/absolute/path/to/scraper-mcp`, `python`, `server.py`
- **Environment:** `MCP_ONLY=1`

Replace `/absolute/path/to/scraper-mcp` with the actual location on your computer. Each argument is a separate entry, not one combined string. On Windows, you can use forward slashes in paths, such as `C:/Users/you/projects/scraper-mcp`.

`MCP_ONLY=1` runs just the MCP connection, avoiding conflicts with a separately running browser server. Omit it if you want the assistant's server to also serve the browser interface on port 8000; build the interface first and do not start another server on that port.

### Example: Codex

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.scraper]
command = "uv"
args = ["run", "--directory", "/absolute/path/to/scraper-mcp", "python", "server.py"]

[mcp_servers.scraper.env]
MCP_ONLY = "1"
```

Alternatively, let the CLI add the same configuration for you:

```bash
codex mcp add scraper --env MCP_ONLY=1 -- uv run --directory /absolute/path/to/scraper-mcp python server.py
```

Use either method, not both. If your project path contains spaces, quote it in the command. See the [Codex MCP documentation](https://developers.openai.com/codex/mcp) for client-specific options.

### Example: Claude Desktop

Open **Settings → Developer → Edit Config** to edit `claude_desktop_config.json`. Add `scraper` under `mcpServers`; preserve any servers already configured.

```json
{
  "mcpServers": {
    "scraper": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/scraper-mcp", "python", "server.py"],
      "env": {
        "MCP_ONLY": "1"
      }
    }
  }
}
```

Save the file and fully quit and reopen Claude Desktop. See the [local MCP server setup guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers) for help locating the configuration and troubleshooting connections.

### Example: VS Code with GitHub Copilot

Create `.vscode/mcp.json` in the workspace where you want to use the assistant. This format uses `servers`, not `mcpServers`:

```json
{
  "servers": {
    "scraper": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/scraper-mcp", "python", "server.py"],
      "env": {
        "MCP_ONLY": "1"
      }
    }
  }
}
```

Run **MCP: List Servers** from the Command Palette, select `scraper`, and start it. Review any trust prompt before allowing the server to run. See the [VS Code MCP documentation](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) for other configuration locations.

All examples use an absolute project path, so the assistant can launch the server from any working directory. Replace the placeholder before saving, and merge the example into existing settings rather than replacing them. You do not need to start the MCP server manually; the client launches it.

### Try the connection

Reconnect or restart your assistant as needed, and check that the `scraper` tools are available. Then try prompts such as:

> Create a namespace called my-docs, then index this documentation page: [paste your URL].

> Use the my-docs namespace and search for how authentication works. Include the source links.

The key tools are `create_namespace`, `use_namespace`, `index_page`, `index_tree`, and `search_docs`. Select a namespace before indexing or searching. Scraper MCP retrieves source material; your assistant supplies any explanation or generated answer.

## Your data and everyday use

- Libraries and indexed content are saved in `data/chroma/`; uploaded files are saved in `data/uploads/`. They survive server restarts. Back up the `data/` directory with the server stopped if you want to keep a copy.
- After restarting, select your namespace again before indexing or searching.
- Deleting a namespace removes its indexed content and uploaded files. Deleting a document removes that file and its search entries.
- Each running server has one active namespace shared by its connected clients. Avoid switching libraries in another browser tab or assistant session during an operation.
- Separate MCP-only and browser servers do not share the active selection; choose a namespace in each. Prefer one server at a time when changing stored content.

**Use on a trusted machine and network.** There is no login or access control, and the default browser server listens on all network interfaces. Do not expose it to the internet or an untrusted network. When connected to an assistant, retrieved content may be sent to that assistant's model provider.

## Troubleshooting

| Problem | What to try |
| --- | --- |
| `uv` or `npm` is not found | Install the missing prerequisite, then open a new terminal. For MCP, use the full path to `uv` if needed. |
| The browser cannot connect | Keep the server terminal open, check it for errors, and use `http://localhost:8000/ui/`. |
| `/ui/` returns “Not Found” | Run `npm ci` and `npm run build` inside `ui/`, then restart the server. |
| Port 8000 is already in use | Stop the other server, or run `uv run uvicorn router:app --host 127.0.0.1 --port 8001` for browser-only use and open `http://localhost:8001/ui/`. |
| “No namespace selected” or “Namespace is empty” | Create or select a namespace, then upload a file or index a page before searching. |
| The first upload or indexing operation is slow | Allow time for the search model to download; check your internet connection if the download fails. |
| A page cannot be indexed or has no useful text | Try a directly accessible page or upload a document instead. Pages requiring login or JavaScript rendering may not work; the scraper does not run an interactive browser. |
| Search does not find what you expected | Check the selected namespace and whether the content finished indexing. Try a more specific query or add the relevant page or file. |
