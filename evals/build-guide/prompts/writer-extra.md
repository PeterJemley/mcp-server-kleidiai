You are writing test questions for a documentation search tool. The tool
answers questions from developers who use KleidiAI (Arm's library of
optimized AI math routines, called micro-kernels) and llama.cpp (an
open-source program that runs language models) on Arm processors.

Read the file {SECTIONS}. It is a JSON list of documentation sections, each
with a `section_id`, the name of the document it comes from (`source`), its
`heading` and its `text`.

For each section, write TWO questions that a developer might type into the
search tool, each answered by that section's text. The two must ask about
different things, not reword the same question.

Rules:
1. Write each question in your own words, as someone who has not read the
   section would ask it. Do not copy any run of 4 or more consecutive words
   from the section's text or heading.
2. You may name the software, hardware or technique as a developer naturally
   would (for example KleidiAI, llama.cpp, Arm, int4, SME). Do not mention
   the document, the section or its heading.
3. The section's text alone must answer each question.
4. If a section supports only one reasonable developer question, write that
   one and give null for the other, with a one-line reason. If it supports
   none (for example, it is only a license notice, a list of links or a
   table of contents), give null for both and say why.

Work only from {SECTIONS}. Do not open any other file, run any search or
command, or look at any repository or website.

Write the result to {OUT} as JSON Lines, one line per section, in the same
order as the input, every section included:
{"section_id": "...", "questions": ["...", "..."], "skip_reason": null or "..."}
Use null in place of any question not written.

Then reply with only the number of questions written.
