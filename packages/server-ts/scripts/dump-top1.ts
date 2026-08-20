/**
 * Dump top-1 doc id for every eval question — TS side of the cross-SDK
 * retrieval-parity check (see distribution/schema-sync/dump_top1.py).
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { parse } from "yaml";

import { findCorpusDir, loadChunks, search } from "../src/corpus.js";

const root = dirname(findCorpusDir());
const questionsPath = join(root, "evals", "questions.yaml");
const questions: Array<{ id: string; question: string }> = parse(
  readFileSync(questionsPath, "utf8"),
).questions;

const chunks = loadChunks();
for (const q of questions) {
  const results = search(q.question, chunks, 1);
  console.log(`${q.id}\t${results[0]?.doc_id ?? ""}`);
}
