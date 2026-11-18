# Playground Serial (Claude Desktop extension)

A local MCP server that lets Playground IDE artifacts use a real USB controller
from inside the Claude desktop app. Artifacts reach it as `host:Playground_Serial` (the app names it after display_name).

Tools: `status`, `list_ports`, `open {path, baud=115200}`, `write {text, newline?}`,
`read` (lines since last read), `close`. `status`, `list_ports`, `read` are marked read-only.
Writes are paced like ChatBroadcast's serialAdapter (256-byte chunks, 10 ms apart).

Build: `npm install --omit=dev && npx @anthropic-ai/mcpb@2.1.2 pack . playground-serial.mcpb`
Install: double-click `playground-serial.mcpb` (Claude desktop app opens it), click Install.
Test page: `../artifact/serial-mcp-test.html` (published privately: https://claude.ai/artifact/RKNJvSugDBZgFSxxEVMuqE).

Known limit: right now only an artifact's owner can call local (`host:`) servers from it.
