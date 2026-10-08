You are deciding the correct answers for a documentation search test. The
documents are about KleidiAI (Arm's library of optimized AI math routines,
called micro-kernels) and llama.cpp (an open-source program that runs
language models) on Arm processors.

Read two files:
- {DOCS}: a JSON list of 7 documents, each with a `doc_id`, a `title` and
  its full `text`.
- {QUESTIONS}: JSON Lines, each with a `qid` and a `question`.

For each question, list every document whose text answers it: the document
states the answer, or the key fact a developer would need to act on it.
A document that only mentions the topic without answering the question does
not count. If no document answers the question, give an empty list.

Judge only from the documents' text. Do not open any other file, run any
search or command, or look at any repository or website.

Write the result to {OUT} as JSON Lines, one line per question, in the same
order as the input:
{"qid": "...", "answering_doc_ids": ["...", ...], "note": "one short line"}

Then reply with only the number of questions labelled.
