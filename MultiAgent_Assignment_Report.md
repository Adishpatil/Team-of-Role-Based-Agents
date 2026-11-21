# Unit 4 (CO-4): Multi-Agent Collaboration for a Catering Quote

## 1. Shared Task and Why It Needs More Than One Agent

**Shared Task:** Produce an accurate, professional customer quote email for Asha's catering order consisting of:
- 20 portions of Veg biryani
- 10 portions of Paneer tikka
- 30 portions of Gulab jamun

The quote must reflect current catalogue prices, compute exact item totals and the grand total, follow proper business communication etiquette, and pass independent verification before reaching the customer.

**Why Multiple Agents Are Necessary:**
A production-grade workflow requires distinct capabilities that operate under fundamentally conflicting constraints:
1. **Authoritative Grounding vs. Hallucination:** Looking up pricing requires querying a reliable external database or cache without inventing or assuming values. Generative models trained on open-ended text naturally predict plausible-sounding tokens rather than verifying database truth.
2. **Deterministic Arithmetic vs. Stochastic Language Modeling:** Calculating line amounts ($20 \times 180$, $10 \times 220$, $30 \times 60$) and summing them ($3,600 + 2,200 + 1,800 = 7,600$) requires zero-error mathematical precision. Autoregressive LLMs are notoriously prone to arithmetic slips and rounding errors when multiplying and summing numbers.
3. **Linguistic Synthesis vs. Rigid Structure:** Drafting a polite, tailored customer response requires natural language synthesis, appropriate tone, and context-specific phrasing. However, the writer must never alter or recalculate the verified financial figures.
4. **Independent Adversarial Review:** Self-review by a single agent exhibits inherent cognitive bias: an agent that misunderstands a price or miscalculates a sum will typically rationalise its own error during self-reflection. An independent Reviewer agent—operating with separate access to ground-truth data and explicit validation rules—ensures errors are intercepted before the quote is released to the customer.

By decomposing the problem into specialized role-based agents, each subtask is governed by strict boundary conditions and verified before downstream consumption.

---

## 2. Role Table

| Agent | Core Role | Tools & Implementation | Must Never |
|---|---|---|---|
| **Researcher** | Retrieves unit pricing for all ordered items from the catalogue or cache. | `price_lookup(order)`: Queries local cache; triggers live catalogue refresh upon reviewer rejection. | Invent a price, guess an unlisted item's rate, or use unverified figures. |
| **Calculator** | Computes line item amounts and grand total. | Pure Python arithmetic (`*` and `sum`); deterministic execution (no language model). | Round figures, estimate totals, or modify input unit prices. |
| **Writer** | Composes the customer-facing quote email. | Template-based generator (default), or local LLM via Ollama (`qwen2.5:3b` / `llama3.1:8b`) with `--llm`. | Recalculate, round, add, or alter any number provided by the Calculator. |
| **Reviewer** | Validates unit prices against live catalogue; audits email draft for number integrity and required item names. | Deterministic Python inspection: set-based numerical comparison, exact string checking, live catalogue comparison. | Rewrite text, modify figures, or approve drafts containing unauthorized numbers or price discrepancies. |
| **Supervisor** | Orchestrates the end-to-end workflow, routes messages between agents, and manages the multi-round negotiation loop. | Control flow loop in Python; tracks negotiation rounds (capped at 3); triggers human escalation on unresolved conflict. | Permit unverified drafts to reach the customer without Reviewer sign-off. |

---

## 3. How the Agents Hand Work to Each Other

### Workflow Diagram

```
                              [ Supervisor ]
                                    │
                  ┌─────────────────┴─────────────────┐
                  │ 1. Assign Task                    │
                  ▼                                   │
           [ Researcher ]                             │
                  │                                   │
                  │ 2. Submit Prices                  │
                  ▼                                   │
            [ Reviewer ]                              │
             (Price Check vs. LIVE Catalogue)         │
                  │                                   │
         ┌────────┴────────┐                          │
         │ Mismatch        │ Approved                 │
         ▼                 ▼                          │
   "Re-fetch Live"    [ Calculator ]                  │
   (Back to Res.)          │                          │
                           │ 3. Verified Figures      │
                           ▼                          │
                       [ Writer ]                     │
                           │                          │
                           │ 4. Draft Quote           │
                           ▼                          │
                      [ Reviewer ]                    │
                    (Audit Draft:                     │
                  Numbers + Content)                  │
                           │                          │
         ┌─────────────────┴─────────────────┐        │
         │ Rejected (Feedback)               │ Passed │
         ▼                                   ▼        │
   [ Writer Re-drafts ]             [ Supervisor ] ◄──┘
   (Max 3 Negotiation Rounds)                │
         │                                   │ 5. Deliver
         ▼ (Exceeded Max Rounds)             ▼
   [ Human Escalation ]                 [ Customer ]
```

### Sequence of Agent Interactions
1. **Task Initialization:** The Supervisor receives the customer order (`Asha`, 3 items) and prompts the Researcher to retrieve unit prices.
2. **First Gate (Price Validation):** The Researcher retrieves prices. Before the figures enter calculation, the Reviewer compares the Researcher's prices against the authoritative `LIVE_CATALOGUE`. If a stale price is detected, the Reviewer rejects it and directs the Researcher to re-fetch from the live catalogue.
3. **Deterministic Computation:** Once prices are verified, the Calculator multiplies quantities by unit rates and computes the grand total, outputting a structured `FIGURES` block.
4. **Drafting & Negotiation Loop:** The Writer ingests the `FIGURES` and composes the customer email. The draft is submitted to the Reviewer, which executes two structural checks:
   - *Number Check:* Verifies that every number present in the email draft exists in the authorized `FIGURES` set (preventing invented discounts, dates, or altered totals).
   - *Content Check:* Verifies that the customer's name and all ordered item names are explicitly present.
5. **Resolution or Escalation:** If the draft passes, the Reviewer notifies the Supervisor, who sends the final email to the customer. If validation fails, the Reviewer returns actionable feedback to the Writer for revision. If consensus is not reached within 3 rounds, the Supervisor escalates to human review.

---

## 4. Code and Run Output

**Code Repository:** [GitHub - Adishpatil/Team-of-Role-Based-Agents](https://github.com/Adishpatil/Team-of-Role-Based-Agents)  
**Source Code:** `multi_agent.py`  
**Execution Environment:** Python 3.14 on Windows; Ollama running local model `qwen2.5:3b`.

### 4.1 Normal Run Output (`python3 multi_agent.py`)
In the normal run, the Researcher accesses current data, the Calculator computes accurate totals, and the Writer produces an approved email in Round 1:

```text
ROLES
  Researcher: Look up the unit price of every ordered item.
    tools: price_lookup(item): reads the price cache, or the live catalogue on refresh
    must never: Invent a price, or use a price that a lookup did not return.
  Calculator: Compute line amounts and the grand total from prices and quantities.
    tools: arithmetic only (no language model)
    must never: Round, estimate, or change any input price.
  Writer: Draft the customer-facing quote email.
    tools: template (default); local LLM via Ollama (only with --llm)
    must never: Change or recalculate any figure supplied by the Calculator.
  Reviewer: Check prices against the live catalogue and check every number in each draft. Approve or send back.
    tools: live price check; number check; content check (no model)
    must never: Rewrite the email or change any figure. It only approves or gives feedback.

TASK: quote for Asha: 20 x Veg biryani, 10 x Paneer tikka, 30 x Gulab jamun   (mode: normal)

[Supervisor -> Researcher] task:
look up prices for [('Veg biryani', 20), ('Paneer tikka', 10), ('Gulab jamun', 30)]

[Researcher -> Calculator] prices:
source=live catalogue: {'Veg biryani': 180, 'Paneer tikka': 220, 'Gulab jamun': 60}

[Reviewer -> Calculator] approved:
prices match the live catalogue

[Calculator -> Writer] figures:
Customer: Asha
- Veg biryani: 20 x Rs 180 = Rs 3600
- Paneer tikka: 10 x Rs 220 = Rs 2200
- Gulab jamun: 30 x Rs 60 = Rs 1800
TOTAL: Rs 7600

[Writer -> Reviewer] draft (round 1):
Dear Asha,

Thank you for your catering order. Here is your quote:

- Veg biryani: 20 x Rs 180 = Rs 3600
- Paneer tikka: 10 x Rs 220 = Rs 2200
- Gulab jamun: 30 x Rs 60 = Rs 1800

Total: Rs 7600

Regards,
Catering team

[Reviewer -> Supervisor] approved:
draft approved in round 1

[Supervisor -> Customer] final quote:
Dear Asha,

Thank you for your catering order. Here is your quote:

- Veg biryani: 20 x Rs 180 = Rs 3600
- Paneer tikka: 10 x Rs 220 = Rs 2200
- Gulab jamun: 30 x Rs 60 = Rs 1800

Total: Rs 7600

Regards,
Catering team
```

---

### 4.2 Simulated Injected Fault Run (`python3 multi_agent.py --fault`)
In this run, a stale price cache is simulated. The Researcher initially reads an outdated price of Rs 200 for Paneer tikka:

```text
ROLES
  Researcher: Look up the unit price of every ordered item.
    tools: price_lookup(item): reads the price cache, or the live catalogue on refresh
    must never: Invent a price, or use a price that a lookup did not return.
  Calculator: Compute line amounts and the grand total from prices and quantities.
    tools: arithmetic only (no language model)
    must never: Round, estimate, or change any input price.
  Writer: Draft the customer-facing quote email.
    tools: template (default); local LLM via Ollama (only with --llm)
    must never: Change or recalculate any figure supplied by the Calculator.
  Reviewer: Check prices against the live catalogue and check every number in each draft. Approve or send back.
    tools: live price check; number check; content check (no model)
    must never: Rewrite the email or change any figure. It only approves or gives feedback.

TASK: quote for Asha: 20 x Veg biryani, 10 x Paneer tikka, 30 x Gulab jamun   (mode: FAULT)

[Supervisor -> Researcher] task:
look up prices for [('Veg biryani', 20), ('Paneer tikka', 10), ('Gulab jamun', 30)]

[Researcher -> Calculator] prices:
source=cache: {'Veg biryani': 180, 'Paneer tikka': 200, 'Gulab jamun': 60}

[Reviewer -> Researcher] rejected:
Price mismatch against the live catalogue: Paneer tikka is Rs 200, live price is Rs 220. Re-fetch from the live catalogue.

[Researcher -> Calculator] prices:
source=live catalogue: {'Veg biryani': 180, 'Paneer tikka': 220, 'Gulab jamun': 60}

[Calculator -> Writer] figures:
Customer: Asha
- Veg biryani: 20 x Rs 180 = Rs 3600
- Paneer tikka: 10 x Rs 220 = Rs 2200
- Gulab jamun: 30 x Rs 60 = Rs 1800
TOTAL: Rs 7600

[Writer -> Reviewer] draft (round 1):
Dear Asha,

Thank you for your catering order. Here is your quote:

- Veg biryani: 20 x Rs 180 = Rs 3600
- Paneer tikka: 10 x Rs 220 = Rs 2200
- Gulab jamun: 30 x Rs 60 = Rs 1800

Total: Rs 7600

Regards,
Catering team

[Reviewer -> Supervisor] approved:
draft approved in round 1

[Supervisor -> Customer] final quote:
Dear Asha,

Thank you for your catering order. Here is your quote:

- Veg biryani: 20 x Rs 180 = Rs 3600
- Paneer tikka: 10 x Rs 220 = Rs 2200
- Gulab jamun: 30 x Rs 60 = Rs 1800

Total: Rs 7600

Regards,
Catering team
```

---

### 4.3 Real Local LLM Run Trace (`python3 multi_agent.py --fault --llm`, Model: `qwen2.5:3b`)
In this run, both the stale price fault and the real local LLM (`qwen2.5:3b` running on Ollama) were executed end-to-end:

```text
ROLES
  Researcher: Look up the unit price of every ordered item.
    tools: price_lookup(item): reads the price cache, or the live catalogue on refresh
    must never: Invent a price, or use a price that a lookup did not return.
  Calculator: Compute line amounts and the grand total from prices and quantities.
    tools: arithmetic only (no language model)
    must never: Round, estimate, or change any input price.
  Writer: Draft the customer-facing quote email.
    tools: template (default); local LLM via Ollama (only with --llm)
    must never: Change or recalculate any figure supplied by the Calculator.
  Reviewer: Check prices against the live catalogue and check every number in each draft. Approve or send back.
    tools: live price check; number check; content check (no model)
    must never: Rewrite the email or change any figure. It only approves or gives feedback.

TASK: quote for Asha: 20 x Veg biryani, 10 x Paneer tikka, 30 x Gulab jamun   (mode: FAULT)

[Supervisor -> Researcher] task:
look up prices for [('Veg biryani', 20), ('Paneer tikka', 10), ('Gulab jamun', 30)]

[Researcher -> Calculator] prices:
source=cache: {'Veg biryani': 180, 'Paneer tikka': 200, 'Gulab jamun': 60}

[Reviewer -> Researcher] rejected:
Price mismatch against the live catalogue: Paneer tikka is Rs 200, live price is Rs 220. Re-fetch from the live catalogue.

[Researcher -> Calculator] prices:
source=live catalogue: {'Veg biryani': 180, 'Paneer tikka': 220, 'Gulab jamun': 60}

[Calculator -> Writer] figures:
Customer: Asha
- Veg biryani: 20 x Rs 180 = Rs 3600
- Paneer tikka: 10 x Rs 220 = Rs 2200
- Gulab jamun: 30 x Rs 60 = Rs 1800
TOTAL: Rs 7600

[Writer -> Reviewer] draft (round 1):
Subject: Catering Quotation for Your Event

Dear Asha,

This is to confirm your catering order. The details are as follows:

- Veg Biryani: 20 portions at Rs 180 each = Rs 3600
- Paneer Tikka: 10 portions at Rs 220 each = Rs 2200
- Gulab Jamun: 30 pieces at Rs 60 each = Rs 1800

The total amount for your order is Rs 7600.

Please let me know if you have any questions or need any adjustments.

Best regards,  
[Your Name]

[Reviewer -> Writer] rejected:
The email is missing: Veg biryani, Paneer tikka, Gulab jamun.

[Writer -> Reviewer] draft (round 2):
Subject: Your Catering Order Confirmation

Dear Asha,

Thank you for your order. Below are the details of your catering order:

- Veg Biryani: 20 pieces at Rs 180 each = Rs 3600
- Paneer Tikka: 10 pieces at Rs 220 each = Rs 2200
- Gulab Jamun: 30 pieces at Rs 60 each = Rs 1800

TOTAL: Rs 7600

Best regards,  
[Your Name]  
[Your Position]  
[Your Contact Information]

[Reviewer -> Writer] rejected:
The email is missing: Veg biryani, Paneer tikka, Gulab jamun.

[Writer -> Reviewer] draft (round 3):
Subject: Your Catering Order Confirmation

Dear Asha,

Thank you for your order. Below are the details of your catering order:

- Veg Biryani: 20 pieces at Rs 180 each = Rs 3600
- Paneer Tikka: 10 pieces at Rs 220 each = Rs 2200
- Gulab Jamun: 30 pieces at Rs 60 each = Rs 1800

TOTAL: Rs 7600

Best regards,  
[Your Name]

[Reviewer -> Writer] rejected:
The email is missing: Veg biryani, Paneer tikka, Gulab jamun.

ESCALATED: no approved draft after 3 rounds; a human should review.
```

---

## 5. Failure Analysis and How the Multi-Agent System Handled It

The multi-agent system intercepted two distinct failure modes: one simulated data-source error and one genuine real-world stochastic LLM communication failure.

### 5.1 Failure 1 (Injected): Stale Price Cache Mismatch
- **The Failure:** The Researcher queried an unrefreshed local cache where Paneer tikka was stored at Rs 200 per unit instead of the current live price of Rs 220. 
- **The Potential Blast Radius:** If unchecked, the Calculator would have evaluated $10 \times 200 = \text{Rs } 2,000$, producing an incorrect total of Rs 7,400 instead of Rs 7,600. A single unified agent would have blindly relied on its initial cached context and issued an erroneous contract quote to the customer.
- **How It Was Reduced:** The multi-agent architecture introduces an explicit verification checkpoint before calculation begins. The Reviewer compared the Researcher's dictionary against the authoritative `LIVE_CATALOGUE`. Upon identifying that `Paneer tikka is Rs 200, live price is Rs 220`, the Reviewer rejected the price set and instructed the Researcher to re-fetch. The Calculator subsequently computed with verified prices ($10 \times 220$), generating the correct Rs 7,600 total.
- **Key Insight:** This guardrail is structural code, not a prompt instruction. If an LLM were simply prompted to "double-check that your prices are accurate," it would confirm them against its own internal hallucination or cached context. Real reliability requires an independent software verification gate.

### 5.2 Failure 2 (Real Model Failure): Orthographic Mismatch and Negotiation Deadlock
- **The Failure:** When using local model `qwen2.5:3b` via Ollama (`--llm`), the LLM adhered to proper formal English letter-writing standards by title-casing the food items:
  - Writer produced: `Veg Biryani`, `Paneer Tikka`, `Gulab Jamun`
  - Catalogue keys: `Veg biryani`, `Paneer tikka`, `Gulab jamun` (lowercase second words)
- **The Reviewer's Reaction:** The Reviewer executed a strict case-sensitive substring search (`w not in draft`). Because `"Veg biryani"` was not in `"Veg Biryani: 20 portions..."`, the check evaluated to `False` and returned:
  `"The email is missing: Veg biryani, Paneer tikka, Gulab jamun."`
- **The Deadlock:** In Round 2 and Round 3, the feedback was injected into the prompt: `REVIEWER FEEDBACK TO FIX: The email is missing: Veg biryani, Paneer tikka, Gulab jamun.`
  The LLM perceived that the dishes were already prominently included in the itemized list. It attempted to address the feedback by rewording descriptions (changing "portions" to "pieces", adjusting sign-offs), but retained Title Case capitalization as required by English linguistic conventions.
- **How the System Handled It (Graceful Escalation):** Because the Reviewer refused to compromise its strict validation policy and the Writer could not deduce the subtle case-sensitivity mismatch, the supervisor terminated the negotiation loop after Round 3:
  `ESCALATED: no approved draft after 3 rounds; a human should review.`
  Instead of silently dispatching an unverified email or entering an infinite loop, the multi-agent supervisor halted the transaction and alerted human operators.
- **Design Lesson:** Rigid syntactic checks without semantic normalization (`str.lower()` or case-insensitive regex) create fragile boundary friction when interacting with generative language models.

---

## 6. Architectural Reflections and Explanations

### Where the Multi-Agent Design Succeeded
1. **Separation of Operational Rules:** Each agent has narrow, clear responsibilities. By isolating arithmetic to a deterministic Calculator, we completely eliminated LLM hallucination in sums and products.
2. **Structural Adversarial Verification:** Placing an independent Reviewer between the Researcher and the Calculator caught the stale pricing bug before any calculations were performed.
3. **Bounded Negotiation and Fail-Safe Escalation:** Rather than crashing or releasing invalid content, the supervisor bounded the interaction to a maximum of 3 turns and triggered a human-in-the-loop escalation path.

### Where the Multi-Agent Design Struggled
1. **Semantic vs. Syntactic Impedance Mismatch:** Language models operate in probabilistic semantic space, whereas code-based reviewers operate on deterministic, literal byte patterns. The literal check `item not in draft` failed to recognize that `Veg Biryani` is semantically identical to `Veg biryani`.
2. **Ambiguous Feedback Loops:** The Reviewer's rejection message (`"The email is missing: Veg biryani..."`) was syntactically accurate according to its code, but semantically misleading to the LLM, which saw the item already present. Effective multi-agent systems require feedback that explains *why* a constraint failed (e.g., specifying exact case sensitivity).
3. **Limitation of the Set-Difference Number Check:** The current Reviewer verifies that all numbers in the draft belong to the set of allowed figures (`allowed = {total, qty, price, amount}`). While this effectively blocks hallucinated numbers (such as arbitrary discounts or invented delivery dates), it cannot detect an *intra-set swap* (e.g., if the Writer mistakenly reported 10 Veg biryanis and 20 Paneer tikkas). Truly robust validation requires structural semantic pairing (e.g., verifying that each quantity is bound to its corresponding item name).

### Why the Calculator Is Deterministic (Code over LLM)
In production agentic architectures, language models should be reserved for fuzzy linguistic tasks (summarization, tone adaptation, conversational synthesis), while exact analytical tasks (arithmetic, tax calculation, database lookups) must be delegated to deterministic tools. Designing the Calculator as pure Python code guarantees zero arithmetic hallucination.
