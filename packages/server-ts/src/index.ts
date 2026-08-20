#!/usr/bin/env node
/** Entry point: run the MCP server over stdio. */

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { server } from "./server.js";

const transport = new StdioServerTransport();
await server.connect(transport);
