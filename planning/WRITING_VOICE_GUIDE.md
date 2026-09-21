# Nomobug Writing Voice Guide

Retained writing reference; not a pipeline setup step.

## Purpose

This guide records the writing style used in the current CP1 proposal. It should be treated as the reference for future CP2 reports, methodology explanations, progress updates, logbook entries, dashboard commentary, and presentation scripts.

The goal is not to manipulate an AI detector. Detectors can misclassify both human and assisted writing, so no style can guarantee a result. The goal is to keep future writing recognisably mine: formal enough for a capstone, but based on my experience, decisions, limitations, and understanding of the Nomobug project.

## What Changed in the Current Proposal

The current proposal was compared with the earlier Git version. The strongest improvements are:

- It starts from my experience working part-time at Nomobug instead of beginning with a generic industry statement.
- It explains why I selected the project and why each decision matters to the company.
- It uses first-person ownership for genuine choices: `I chose`, `I learned`, `I plan`, `I use`, and `I will`.
- It connects technical choices to actual constraints such as messy Sheets, Calendar formats, cost, company feedback, and around 200 warranty records.
- It contains a natural mixture of short and long sentences. A sentence such as `The problem is proving it` interrupts longer explanations effectively.
- It reduces repeated sentence openings. In the earlier version, `I use...` appeared as a sentence opening much more often.
- It gives sources a purpose instead of only reporting what each paper says.
- It admits uncertainty. Platforms, field names, model suitability, and source relationships are presented as matters to confirm during CP2.

The comparison also found that the current version has slightly more variation in sentence length and vocabulary. That variation helps the report sound less mechanically produced, provided clarity is not lost.

## Core Voice

The target voice is **a student explaining a real project that he understands and intends to build**.

Write as someone who:

- has seen Nomobug's administrative and operational work;
- knows why the business problem matters;
- is learning and making reasoned technical choices;
- can explain a technical idea in ordinary language;
- is honest about missing data, uncertainty, cost, time, and small samples;
- does not pretend that CP2 results already exist.

The tone should be personal and direct without becoming casual. Use first person when describing my experience, judgement, plan, work, or interpretation. Use neutral academic language for established facts and findings from research.

First person is not required in every technical paragraph. When code has already been run or a result has been measured, begin with the program, test, dataset, or result itself. For example, `The program checked the complete 35-column header` is clearer than beginning with a broad statement about the importance of schema validation.

## Evidence-Led Technical Writing

The Big Data assignment provides an additional reference for future CP2 implementation writing. Its strongest paragraphs do four things:

1. state the observed result or completed action;
2. provide exact evidence, configuration, or calculation;
3. explain the technical reason for the result; and
4. state the boundary of what the test proves.

This is the preferred pattern for benchmark results, pipeline checks, data-quality findings, model evaluation, and dashboard validation.

### Result, evidence, explanation, boundary

Example structure:

> Both implementations produced the same analytical outputs. The comparison checked group names, counts, and numerical values and returned exit status 0. This means the performance difference was not caused by different calculations. However, the test covered only the tables and dataset used in the experiment.

The paragraph does not need a general introduction or a concluding claim about innovation. The evidence carries the point.

### Method, rule, reason

When documenting code or data preparation, name the exact rule and explain why it was used:

> The program kept records where `cancelled = 0` and `diverted = 0`. It then checked that completed flights did not have a missing arrival delay. Negative delay values were retained because they represent early arrivals.

Use the same approach for Nomobug work. State the field, condition, fallback key, date window, threshold, or exclusion rule. Avoid replacing the rule with a broad phrase such as `the data was cleaned appropriately`.

### Comparison based on a controlled difference

When comparing tools or methods, confirm what remained the same. Mention shared definitions, input data, filters, output tables, and timing boundaries where relevant. This prevents the paragraph from becoming a generic tool comparison.

For example, a future Superset or pipeline comparison should state whether both versions used the same source extract, cleaning rules, date range, and KPI definitions before discussing speed or usability.

### Limitations tied to the experiment

State a specific limitation rather than adding a generic future-work sentence. Useful limitations include:

- only one dataset size was tested;
- only one infrastructure configuration was used;
- a small number of warranty outcomes was available;
- some Calendar events could not be matched confidently;
- weather coverage was available only for certain dates or areas;
- an observed association does not establish causation.

Use direct wording such as `This test does not prove...` or `The result applies only to...` when that is the accurate conclusion.

## What Makes the Reference Text Effective

- Paragraphs begin with a concrete subject: `Both implementations`, `The program`, `Pandas`, or `Spark`.
- Verbs describe observable work: `checked`, `stopped`, `retained`, `calculated`, `summed`, `counted`, and `wrote`.
- Numbers and settings are included only when they support the claim.
- Technical terms remain because they are precise, not because they sound advanced.
- Cause-and-effect explanations identify a mechanism, such as memory use, intermediate copies, partitioning, or task retries.
- Claims are calibrated. The writing says what the test demonstrates and what it does not demonstrate.
- Paragraphs do not all end with a sentence about relevance, usefulness, or significance.
- Transitions come from the logic of the evidence rather than repeated linking words.

For future Nomobug implementation writing, use the same qualities with actual project evidence: row counts, missing-value rates, unmatched-record counts, Calendar match confidence, weather-enrichment coverage, query results, model metrics, refresh duration, and dashboard validation results.

## Preferred Paragraph Pattern

Do not force every paragraph into one template. Choose the pattern that fits the point.

### Experience to problem

1. Describe something observed in Nomobug's work.
2. Explain why it creates a business or customer problem.
3. Connect it to the project.

Example pattern:

> A completed booking does not always mean that the pest problem is resolved. A customer may contact the company again, which creates another visit and affects the schedule. This is why service outcomes need to be analysed together with warranty and Calendar records.

### Decision to reason

1. State what I plan to do.
2. Explain why it suits the actual data or constraint.
3. Mention what would make the decision change.

Example pattern:

> I will begin with recurrence windows and rainfall-lag analysis because these methods can still produce understandable results with a small warranty dataset. Logistic regression will only be added if the cleaned labels are sufficient for proper validation.

### Source to interpretation

1. Introduce the useful finding from a source.
2. Explain how it affects the Nomobug design.
3. Mention a limitation or difference where relevant.

Avoid ending every source paragraph with the same phrase such as `This is relevant to my project because...`.

### Comparison

1. Identify where two studies or methods agree or differ.
2. Explain which part is useful for Nomobug.
3. State the resulting design choice.

This pattern is especially useful in the literature review because it shows understanding instead of producing one isolated summary per paper.

## Sentence Style

- Mix ordinary sentences with occasional longer technical explanations.
- Keep one main idea in most sentences.
- Use short sentences when they express a real point, not merely to create artificial variation.
- Prefer `because`, `but`, `so`, `although`, and `however` when they reflect the actual reasoning.
- Use concrete subjects such as `Nomobug`, `management`, `customers`, `the Calendar records`, or `the warranty dataset`.
- Use active wording when ownership is clear: `I will profile the sheets` is better than `profiling will be conducted`.
- Use an evidence-led subject when the work has already been completed: `The validation script rejected three rows with invalid dates` is better than `data validation was successfully carried out`.
- Keep technical terms when they are necessary, then explain what they do in the project.
- Do not deliberately insert grammar mistakes to appear human. Natural writing can still be clear and correct.

## Vocabulary

Prefer direct wording:

| Prefer | Use cautiously |
|---|---|
| use | utilise, employ |
| help | facilitate, enable the optimisation of |
| show | demonstrate, illustrate, highlight |
| check | evaluate, assess, investigate |
| choose | select, adopt, leverage |
| because | due to the fact that |
| data from several sheets | heterogeneous multi-source operational datasets |
| clean tables for the dashboard | pre-dashboard-ready transformed data artefacts |

Technical vocabulary such as `DBSCAN`, `KDE`, `ELT`, `data contract`, `lineage`, and `recurrence window` should remain where accurate. The problem is not technical language itself. The problem is stacking several abstract technical nouns when a simpler explanation would be clearer.

## Citations and Literature Review

- Begin with the research question or Nomobug issue when possible, not always with an author's surname.
- Explain what I take from a paper and what I do not take from it.
- Group related studies instead of writing every paragraph in the same author-method-result-relevance format.
- Compare papers when they support different methods or contexts.
- Keep citations close to the claim they support.
- Do not add several citations merely to make a sentence appear academic.
- Avoid claiming that a paper proves something about Nomobug when it studied agriculture, another country, or another pest setting.
- Follow a citation with my interpretation when that interpretation affects the project design.

Useful phrasing includes:

- `I use this study to justify...`
- `The study is useful here, although...`
- `For Nomobug, the important part is...`
- `This does not mean that...`
- `The finding supports the use of..., but the final decision depends on...`

Do not repeat any one of these phrases throughout a section.

## Section-Specific Guidance

### Abstract and introduction

Start with the real workplace situation, customer effect, or reason I chose the project. Explain the system only after the problem is clear.

### Problem statement

Show both sides: what customers experience and what the company has difficulty reviewing. Use concrete records and consequences rather than a list of generic market problems.

### Literature review

Use papers to make decisions. Compare methods, contexts, limitations, and relevance. Avoid twenty paragraphs that all follow the same six-sentence structure.

### Methodology

Explain the order of work and the reason for that order. Distinguish between what is already confirmed, what is planned, and what will be decided after profiling.

### CP2 implementation report

Write from evidence:

- what source was inspected;
- what was found;
- what cleaning or matching decision was made;
- why that decision was reasonable;
- what limitation remains;
- what will be tested next.

Include actual counts, date ranges, missing-value percentages, matching rates, or model results when available. Do not replace evidence with broad claims such as `the system performed effectively`.

A strong implementation paragraph should usually answer three questions: what happened, why it happened, and what the result is limited to. It does not need to repeat the project objective or explain that the result is important unless that point adds new information.

### Logbook

Write what I actually completed, what I learned, a problem I encountered, how I responded, and the next task. Do not turn weekly entries into miniature proposal sections.

## Patterns to Avoid

- A perfectly predictable topic sentence, three supporting facts, and a concluding sentence in every paragraph.
- Repeated openings such as `This project...`, `The study...`, or `I use...` across consecutive sentences.
- Long catalogues of tools without explaining the choice or trade-off.
- Generic claims such as `This innovative solution will significantly enhance operational efficiency`.
- Inflated substitutions that make a simple idea harder to understand.
- Excessive transitions such as `Furthermore`, `Moreover`, and `Additionally`.
- Claiming that planned CP2 work has already been implemented or evaluated.
- Presenting weather or technician indicators as proven causes.
- Rewriting a clear sentence only to make it sound more academic.
- Introducing personal experiences, company facts, results, or supervisor feedback that I did not provide.
- Opening a measured result with a broad statement such as `In today's data-driven environment`.
- Describing an action as successful without naming the check, output, or acceptance rule.
- Ending every technical paragraph with `This shows that the approach is effective`.
- Adding exact numbers that do not support the claim being made.

## Revision Process

1. Begin with factual notes: what I observed, did, chose, found, or still need to confirm.
2. Draft the explanation in plain language before adding academic terminology.
3. Add sources only where they support a specific claim or choice.
4. Check that each paragraph contributes something different.
5. Replace vague claims with Nomobug examples, real data fields, measured results, or a stated limitation.
6. Read the paragraph aloud. If it sounds like a brochure, software manual, or literature-summary template, simplify it.
7. Preserve my wording when it is already clear. Do not rewrite an entire section merely for polish.
8. Perform a final technical, citation, grammar, and privacy check.

## Final Voice Checklist

Before accepting new text, check:

- Does it sound like I understand and own the decision?
- Is there a real Nomobug observation, constraint, or purpose where one is relevant?
- Does it distinguish facts, research findings, my interpretation, and future plans?
- Are sentence openings and paragraph structures varied naturally?
- Is any sentence more formal or complicated than the idea requires?
- Are citations connected to an argument rather than inserted as decoration?
- Are limitations and uncertainty stated honestly?
- Have technical claims, figures, and company details been verified?
- Does the text avoid unsupported causal language and technician blame?
- Has the original proposal remained unchanged unless I explicitly requested an edit?
- For completed technical work, does the paragraph begin with the action, result, dataset, or test rather than a generic introduction?
- Does the evidence support the claim, and is the limitation stated at the correct level?
- If two tools or methods are compared, does the text explain what was kept consistent?

## Instruction for Future Codex Tasks

Use this file as the writing-style authority for Nomobug work. Preserve my formal but personal student voice. Ground writing in the experience, actions, constraints, data, and decisions I provide. Do not invent first-hand experience or project results. Avoid formulaic academic paragraph structures, inflated vocabulary, citation dumping, and blanket rewrites. When information from me is missing, ask for it or clearly mark the point as unconfirmed. Technical accuracy, citation integrity, and my actual meaning remain more important than any detector result.
