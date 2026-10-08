You are writing test questions for a documentation search tool. The tool
answers questions from developers who use KleidiAI (Arm's library of
optimized AI math routines, called micro-kernels) and llama.cpp (an
open-source program that runs language models) on Arm processors.

Read the file {SECTIONS}. It is a JSON list of documentation sections, each
with a `section_id`, the name of the document it comes from (`source`), its
`heading` and its `text`.

For each section, write ONE question that a developer might type into the
search tool, and whose answer is in that section's text.

Rules:
1. Write the question in your own words, as someone who has not read the
   section would ask it. Do not copy any run of 4 or more consecutive words
   from the section's text or heading.
2. You may name the software, hardware or technique as a developer naturally
   would (for example KleidiAI, llama.cpp, Arm, int4, SME). Do not mention
   the document, the section or its heading.
3. The section's text alone must answer the question.
4. Vary the kind of question across sections: how to do something, what
   something is, why something happens, which option or function to use.
5. If no reasonable developer question is answered by a section (for
   example, it is only a license notice, a list of links or a table of
   contents), give no question for it and say why in one short line.

Work only from {SECTIONS}. Do not open any other file, run any search or
command, or look at any repository or website.

Write the result to {OUT} as JSON Lines, one line per section, in the same
order as the input, every section included:
{"section_id": "...", "question": "..." or null, "skip_reason": null or "..."}

Then reply with only the number of questions written and the number of
sections skipped.
