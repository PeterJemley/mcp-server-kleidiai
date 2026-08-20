# What is this, really?

A friendly tour of what this project does — for anyone who hasn't spent the last few years inside the on-device AI rabbit hole. No prerequisites required.

## The big picture

There's a small revolution happening with AI: models that used to need a refrigerator-sized server are starting to run directly on the laptop or phone in your pocket. The chips inside Apple, Qualcomm, and Amazon devices are quietly really good at this — they're all part of a family of processors called **Arm**, the same family that powers about 95% of smartphones worldwide.

But "running" an AI model on Arm efficiently — fast, without melting your battery — takes specific tricks. Multiplying matrices (the math AI models do all day) needs to happen in just the right way for each Arm chip. Arm built a library called **KleidiAI** that bundles these tricks. The popular open-source AI inference tool **llama.cpp** uses KleidiAI under the hood whenever it's running on Arm. The result: a Mac M-series, a new Snapdragon laptop, or an Amazon Graviton server can run substantial AI models surprisingly well, locally, with no cloud round-trip.

The problem: this is a lot of moving parts, and the documentation is spread across:

- Arm's KleidiAI repository on GitHub
- A separate examples repository with patch files showing real integrations
- The llama.cpp project's own build documentation
- A growing collection of "learning paths" on Arm's developer site
- Scattered engineering blog posts

If you're an AI assistant — say, helping a developer port their code to run faster on Arm — you can't easily *find* the right information across all those places. Nobody's collected and curated this knowledge for AI agents to use yet.

## What this project does

This project builds a small, focused **knowledge server** for that exact niche.

It takes all the scattered documentation about KleidiAI + llama.cpp on Arm, organizes it into a curated, searchable collection with full source attribution, and exposes it to AI assistants via something called the **Model Context Protocol (MCP)** — basically a universal "plug" that AI assistants from many different companies can use to connect to specialized tools.

So when a developer asks their AI assistant *"how do I get the most out of KleidiAI when running Llama 3 locally on my M-series Mac?"*, the assistant can plug into this server, search the curated knowledge, and answer with confidence — citing real Arm documentation rather than fabricating an answer that sounds plausible but might be wrong.

## Three pieces

1. **The server itself** — answers questions about KleidiAI + llama.cpp by drawing from the curated knowledge base. Distributed as a Python package today, and a TypeScript package shortly after — so anyone with an AI assistant can install it in seconds.
2. **An evaluation system** — measures how *accurate* the server's answers are, against a real held-out set of questions, with score reports committed right into the repo for anyone to read. This is the part most similar projects skip. We don't.
3. **A demonstration** — an end-to-end recorded session where an AI agent uses the server to actually port a piece of code to KleidiAI, then benchmarks the speedup. Real numbers, on real hardware.

## Why it's exciting

- **It's the first of its kind.** No KleidiAI-focused MCP server exists today. We're not competing with anyone — we're carving out the niche.
- **It runs on hardware you already own.** Apple Silicon Macs, Snapdragon laptops, anything with a recent Arm chip. The whole story unfolds locally, no cloud bill, no cloud privacy worry.
- **It demonstrates the near future of AI assistance.** Specialized knowledge + agentic tool use + on-device inference, stitched together into something a real developer would actually use.
- **It's small enough to ship.** Six weeks from scaffold to v1.0 published. Not a moonshot — a real, scoped, completable project.

## Where to learn more

- For the technical pitch and install instructions: [`README.md`](./README.md)
- For how the pieces fit together: [`architecture.md`](./architecture.md)
- For the locked design decisions and milestone plan: [`v0-decisions.md`](./v0-decisions.md)
- For working context (the operating handbook for the project): [`CLAUDE.md`](./CLAUDE.md)
