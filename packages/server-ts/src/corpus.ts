/**
 * Corpus loading + two-level BM25 retrieval over the committed KleidiAI
 * corpus — a faithful port of the Python implementation
 * (packages/server-py/src/mcp_server_kleidiai/corpus.py). Every constant,
 * formula, and tie-break mirrors the Python retriever; behavioral parity is
 * enforced by the cross-SDK checks in distribution/schema-sync (identical
 * top-1 doc on every eval question). Change the two implementations
 * together or not at all.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { parse } from "yaml";

const HEADING_RE = /^(#{1,6})\s+(.*)$/;
const TOKEN_RE = /[a-z0-9]+/g;
const STOPWORDS = new Set(
  "a an and are as at be by do for how i in is it of on or the to what when where which why with you your".split(
    " ",
  ),
);

/** One heading-bounded section of a corpus doc, carrying its provenance. */
export interface DocChunk {
  docId: string;
  url: string;
  heading: string;
  text: string;
}

/**
 * One ranked passage: provenance plus a query-focused snippet. The score is
 * the doc-level relevance (what the cross-doc ordering means). Snake_case
 * fields: this is the wire shape the tool returns, shared with Python.
 */
export interface SearchResult {
  doc_id: string;
  url: string;
  heading: string;
  snippet: string;
  score: number;
}

/** One corpus/manifest.yaml source entry (provenance fields as authored). */
export interface ManifestSource {
  id: string;
  url?: string;
  path: string;
  removed_at?: string;
  [key: string]: unknown;
}

/**
 * Locate the corpus directory. Resolution order: KLEIDIAI_CORPUS_DIR if
 * set; else the nearest ancestor containing corpus/manifest.yaml (a repo
 * checkout — this also finds the copy staged at the npm package root by
 * the prepack step, since dist/src sits beneath it).
 */
export function findCorpusDir(start?: string): string {
  const env = process.env.KLEIDIAI_CORPUS_DIR;
  if (env) return resolve(env);
  let dir = resolve(start ?? import.meta.dirname);
  for (;;) {
    if (existsSync(join(dir, "corpus", "manifest.yaml"))) return join(dir, "corpus");
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error("Could not locate corpus/manifest.yaml; set KLEIDIAI_CORPUS_DIR");
}

/** Return the active source entries from corpus/manifest.yaml. */
export function loadManifest(corpusDir: string): ManifestSource[] {
  const data = parse(readFileSync(join(corpusDir, "manifest.yaml"), "utf8")) ?? {};
  const sources: ManifestSource[] = data.sources ?? [];
  return sources.filter((s) => !s.removed_at);
}

function chunkMarkdown(text: string): Array<[string, string]> {
  let heading = "";
  let body: string[] = [];
  const chunks: Array<[string, string]> = [];
  for (const line of text.split("\n")) {
    const m = HEADING_RE.exec(line);
    if (m) {
      const joined = body.join("\n").trim();
      if (heading || joined) chunks.push([heading, joined]);
      heading = (m[2] ?? "").trim();
      body = [];
    } else {
      body.push(line);
    }
  }
  const joined = body.join("\n").trim();
  if (heading || joined) chunks.push([heading, joined]);
  return chunks;
}

/** Load every manifest-listed doc and split it into heading-bounded chunks. */
export function loadChunks(corpusDir?: string): DocChunk[] {
  const dir = corpusDir ?? findCorpusDir();
  const chunks: DocChunk[] = [];
  for (const src of loadManifest(dir)) {
    const path = join(dir, src.path);
    if (!existsSync(path)) continue;
    const text = readFileSync(path, "utf8");
    for (const [heading, body] of chunkMarkdown(text)) {
      chunks.push({ docId: src.id, url: src.url ?? "", heading, text: body });
    }
  }
  return chunks;
}

function tokens(s: string): string[] {
  return (s.toLowerCase().match(TOKEN_RE) ?? []).filter((t) => !STOPWORDS.has(t));
}

function snippet(text: string, terms: Set<string>, width = 280): string {
  const lower = text.toLowerCase();
  let pos = -1;
  for (const t of terms) {
    const p = lower.indexOf(t);
    if (p !== -1 && (pos === -1 || p < pos)) pos = p;
  }
  if (pos === -1) return text.slice(0, width).trim();
  const start = Math.max(0, pos - 60);
  const end = start + width;
  return (
    (start > 0 ? "…" : "") + text.slice(start, end).trim() + (end < text.length ? "…" : "")
  );
}

// BM25 parameters: identical to the Python retriever (standard Okapi
// defaults; heading terms weighted; ≤2 passages per doc).
const K1 = 1.5;
const B = 0.75;
const HEADING_WEIGHT = 3;
const MAX_PER_DOC = 2;

interface Index {
  chunks: DocChunk[];
  termFreqs: Array<Map<string, number>>;
  lengths: number[];
  avgLength: number;
  idf: Map<string, number>;
  docTermFreqs: Map<string, Map<string, number>>;
  docLengths: Map<string, number>;
  docAvgLength: number;
  docIdf: Map<string, number>;
}

let index: Index | null = null;

function buildIndex(chunks: DocChunk[]): Index {
  const termFreqs: Array<Map<string, number>> = [];
  const lengths: number[] = [];
  const df = new Map<string, number>();
  const docTf = new Map<string, Map<string, number>>();
  for (const ch of chunks) {
    const tf = new Map<string, number>();
    for (const t of tokens(ch.text)) tf.set(t, (tf.get(t) ?? 0) + 1);
    for (const t of tokens(ch.heading)) tf.set(t, (tf.get(t) ?? 0) + HEADING_WEIGHT);
    termFreqs.push(tf);
    let len = 0;
    for (const n of tf.values()) len += n;
    lengths.push(len);
    for (const t of tf.keys()) df.set(t, (df.get(t) ?? 0) + 1);
    let dtf = docTf.get(ch.docId);
    if (!dtf) {
      dtf = new Map();
      docTf.set(ch.docId, dtf);
    }
    for (const [t, n] of tf) dtf.set(t, (dtf.get(t) ?? 0) + n);
  }
  const n = chunks.length;
  const avg = n ? lengths.reduce((a, b) => a + b, 0) / n : 0;
  const idf = new Map<string, number>();
  for (const [t, d] of df) idf.set(t, Math.log((n - d + 0.5) / (d + 0.5) + 1.0));

  const docLengths = new Map<string, number>();
  for (const [d, tf] of docTf) {
    let len = 0;
    for (const v of tf.values()) len += v;
    docLengths.set(d, len);
  }
  const nd = docTf.size;
  let docTotal = 0;
  for (const v of docLengths.values()) docTotal += v;
  const docAvg = nd ? docTotal / nd : 0;
  const docDf = new Map<string, number>();
  for (const tf of docTf.values()) {
    for (const t of tf.keys()) docDf.set(t, (docDf.get(t) ?? 0) + 1);
  }
  const docIdf = new Map<string, number>();
  for (const [t, d] of docDf) docIdf.set(t, Math.log((nd - d + 0.5) / (d + 0.5) + 1.0));
  return {
    chunks,
    termFreqs,
    lengths,
    avgLength: avg,
    idf,
    docTermFreqs: docTf,
    docLengths,
    docAvgLength: docAvg,
    docIdf,
  };
}

function bm25(
  matched: Set<string>,
  tf: Map<string, number>,
  idf: Map<string, number>,
  length: number,
  avg: number,
): number {
  const norm = K1 * (1.0 - B + (B * length) / avg);
  let s = 0;
  for (const t of matched) {
    const f = tf.get(t) ?? 0;
    s += (idf.get(t) ?? 0) * ((f * (K1 + 1.0)) / (f + norm));
  }
  return s;
}

/** Rank corpus passages for a query with two-level BM25 (see corpus.py). */
export function search(query: string, chunks: DocChunk[], limit = 5): SearchResult[] {
  const q = new Set(tokens(query));
  if (q.size === 0) return [];
  if (index === null || index.chunks !== chunks) index = buildIndex(chunks);
  const idx = index;

  const docScore = new Map<string, number>();
  for (const [docId, dtf] of idx.docTermFreqs) {
    const matched = new Set<string>();
    for (const t of q) if (dtf.has(t)) matched.add(t);
    if (matched.size === 0) continue;
    const s = bm25(matched, dtf, idx.docIdf, idx.docLengths.get(docId) ?? 0, idx.docAvgLength);
    docScore.set(docId, s * (matched.size / q.size));
  }

  const scored: Array<{ docS: number; chunkS: number; i: number }> = [];
  for (let i = 0; i < chunks.length; i++) {
    const ch = chunks[i]!;
    const dS = docScore.get(ch.docId);
    if (dS === undefined || ch.text.trim() === "") continue;
    const tf = idx.termFreqs[i]!;
    const matched = new Set<string>();
    for (const t of q) if (tf.has(t)) matched.add(t);
    if (matched.size === 0) continue;
    const chunkS = bm25(matched, tf, idx.idf, idx.lengths[i]!, idx.avgLength);
    scored.push({ docS: dS, chunkS, i });
  }
  // Same ordering as Python's reverse tuple sort: doc score desc, chunk
  // score desc, then chunk index desc.
  scored.sort((a, b) => b.docS - a.docS || b.chunkS - a.chunkS || b.i - a.i);

  const results: SearchResult[] = [];
  const perDoc = new Map<string, number>();
  for (const { docS, i } of scored) {
    const ch = chunks[i]!;
    const seen = perDoc.get(ch.docId) ?? 0;
    if (seen >= MAX_PER_DOC) continue;
    perDoc.set(ch.docId, seen + 1);
    const tf = idx.termFreqs[i]!;
    const matched = new Set<string>();
    for (const t of q) if (tf.has(t)) matched.add(t);
    results.push({
      doc_id: ch.docId,
      url: ch.url,
      heading: ch.heading,
      snippet: snippet(ch.text, matched),
      score: Math.round(docS * 1000) / 1000,
    });
    if (results.length >= limit) break;
  }
  return results;
}
