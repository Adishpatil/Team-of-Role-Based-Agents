#!/usr/bin/env python3
"""
multi_agent.py
Four role-based agents collaborate to produce one customer quote email.

  Researcher  - looks up unit prices (deterministic tool agent)
  Calculator  - computes line totals and the grand total (deterministic)
  Writer      - drafts the quote email from a template (default), or from a
                local LLM via Ollama with --llm
  Reviewer    - checks prices against the live catalogue, checks every number
                and required content in the draft (all plain code, no model)

The supervisor routes work between them and runs a negotiation loop:
Writer drafts -> Reviewer sends back feedback -> Writer revises, up to 3 rounds.

Setup:
  ollama pull llama3.1:8b          (or any model you have)
  ollama serve                     (if it is not already running)
  python3 multi_agent.py                 normal run, no model needed
  python3 multi_agent.py --fault         simulate a stale price cache (failure case)
  python3 multi_agent.py --llm           draft with Ollama instead of the template

Environment (optional): MODEL, OLLAMA_URL
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.environ.get("MODEL", "llama3.1:8b")
MAX_ROUNDS = 3
USE_LLM = "--llm" in sys.argv   # Ollama is used only for drafting, and only when asked

# Shared task data. LIVE_CATALOGUE is the source of truth.
LIVE_CATALOGUE = {"Veg biryani": 180, "Paneer tikka": 220, "Gulab jamun": 60}
STALE_CACHE = {"Veg biryani": 180, "Paneer tikka": 200, "Gulab jamun": 60}  # out of date
ORDER = [("Veg biryani", 20), ("Paneer tikka", 10), ("Gulab jamun", 30)]
CUSTOMER = "Asha"


def llm(system, user):
    """Send one chat turn to the local Ollama model and return the reply text."""
    body = json.dumps({
        "model": MODEL,
        "stream": False,
        "options": {"temperature": 0},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["message"]["content"].strip()


def say(sender, receiver, kind, content):
    print(f"\n[{sender} -> {receiver}] {kind}:\n{content}")


# ---------------------------------------------------------------- agents

class Researcher:
    name = "Researcher"
    role = "Look up the unit price of every ordered item."
    tools = ["price_lookup(item): reads the price cache, or the live catalogue on refresh"]
    never = "Invent a price, or use a price that a lookup did not return."

    def __init__(self, fault):
        self.source_name = "cache" if fault else "live catalogue"
        self.source = STALE_CACHE if fault else LIVE_CATALOGUE

    def lookup(self, order, live=False):
        source, label = (LIVE_CATALOGUE, "live catalogue") if live else (self.source, self.source_name)
        prices = {item: source[item] for item, _ in order}
        return prices, label


class Calculator:
    name = "Calculator"
    role = "Compute line amounts and the grand total from prices and quantities."
    tools = ["arithmetic only (no language model)"]
    never = "Round, estimate, or change any input price."

    def run(self, order, prices):
        lines = [{"item": i, "qty": q, "price": prices[i], "amount": q * prices[i]}
                 for i, q in order]
        return {"lines": lines, "total": sum(l["amount"] for l in lines)}


WRITER_SYS = """You write short catering quote emails to a customer.
Use ONLY the numbers in the FIGURES block. Never change, round, add, or recalculate any number.
If REVIEWER FEEDBACK is given, fix exactly those problems and nothing else.
Output the email body only, with a greeting and a sign-off."""


class Writer:
    name = "Writer"
    role = "Draft the customer-facing quote email."
    tools = ["template (default)", "local LLM via Ollama (only with --llm)"]
    never = "Change or recalculate any figure supplied by the Calculator."

    def draft(self, figures, feedback=None):
        if USE_LLM:
            user = f"FIGURES:\n{figures_text(figures)}\n"
            if feedback:
                user += f"\nREVIEWER FEEDBACK TO FIX:\n{feedback}\n"
            return llm(WRITER_SYS, user)
        lines = "\n".join(f"- {l['item']}: {l['qty']} x Rs {l['price']} = Rs {l['amount']}"
                          for l in figures["lines"])
        return (f"Dear {CUSTOMER},\n\nThank you for your catering order. Here is your quote:\n\n"
                f"{lines}\n\nTotal: Rs {figures['total']}\n\nRegards,\nCatering team")


class Reviewer:
    name = "Reviewer"
    role = "Check prices against the live catalogue and check every number in each draft. Approve or send back."
    tools = ["live price check", "number check", "content check (no model)"]
    never = "Rewrite the email or change any figure. It only approves or gives feedback."

    def check_prices(self, prices):
        bad = {i: (p, LIVE_CATALOGUE[i]) for i, p in prices.items() if LIVE_CATALOGUE[i] != p}
        if not bad:
            return True, ""
        detail = ", ".join(f"{i} is Rs {p}, live price is Rs {live}" for i, (p, live) in bad.items())
        return False, f"Price mismatch against the live catalogue: {detail}."

    def check_numbers(self, draft, figures):
        found = set(re.findall(r"\d+", draft.replace(",", "")))
        allowed = {str(figures["total"])}
        for l in figures["lines"]:
            allowed |= {str(l["qty"]), str(l["price"]), str(l["amount"])}
        if str(figures["total"]) not in found:
            return False, f"The grand total Rs {figures['total']} is missing from the email."
        extra = sorted(found - allowed)
        if extra:
            return False, f"These numbers are not in the FIGURES: {', '.join(extra)}. Use only the FIGURES."
        return True, ""

    def check_content(self, draft, figures):
        missing = [w for w in [CUSTOMER] + [l["item"] for l in figures["lines"]] if w not in draft]
        if missing:
            return False, f"The email is missing: {', '.join(missing)}."
        return True, ""


def figures_text(figures):
    lines = [f"- {l['item']}: {l['qty']} x Rs {l['price']} = Rs {l['amount']}" for l in figures["lines"]]
    return f"Customer: {CUSTOMER}\n" + "\n".join(lines) + f"\nTOTAL: Rs {figures['total']}"


# ---------------------------------------------------------------- supervisor

def main():
    fault = "--fault" in sys.argv
    researcher, calc, writer, reviewer = Researcher(fault), Calculator(), Writer(), Reviewer()

    print("ROLES")
    for a in (researcher, calc, writer, reviewer):
        print(f"  {a.name}: {a.role}")
        print(f"    tools: {'; '.join(a.tools)}")
        print(f"    must never: {a.never}")
    print(f"\nTASK: quote for {CUSTOMER}: " +
          ", ".join(f"{q} x {i}" for i, q in ORDER) + f"   (mode: {'FAULT' if fault else 'normal'})")

    # 1. Researcher gets prices
    say("Supervisor", researcher.name, "task", f"look up prices for {ORDER}")
    prices, label = researcher.lookup(ORDER)
    say(researcher.name, calc.name, "prices", f"source={label}: {prices}")

    # 2. Reviewer checks prices against the live catalogue (independent source)
    ok, problem = reviewer.check_prices(prices)
    if not ok:
        say(reviewer.name, researcher.name, "rejected", problem + " Re-fetch from the live catalogue.")
        prices, label = researcher.lookup(ORDER, live=True)
        say(researcher.name, calc.name, "prices", f"source={label}: {prices}")
    else:
        say(reviewer.name, calc.name, "approved", "prices match the live catalogue")

    # 3. Calculator computes the figures
    figures = calc.run(ORDER, prices)
    ftext = figures_text(figures)
    say(calc.name, writer.name, "figures", ftext)

    # 4. Negotiation loop: Writer drafts, Reviewer checks
    feedback = None
    for round_no in range(1, MAX_ROUNDS + 1):
        draft = writer.draft(figures, feedback)
        say(writer.name, reviewer.name, f"draft (round {round_no})", draft)

        ok_n, msg_n = reviewer.check_numbers(draft, figures)
        ok_c, msg_c = reviewer.check_content(draft, figures)
        if ok_n and ok_c:
            say(reviewer.name, "Supervisor", "approved", f"draft approved in round {round_no}")
            say("Supervisor", "Customer", "final quote", draft)
            return
        feedback = " ".join(m for m in (msg_n, msg_c) if m)
        say(reviewer.name, writer.name, "rejected", feedback)

    print("\nESCALATED: no approved draft after", MAX_ROUNDS, "rounds; a human should review.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError:
        print("Could not reach Ollama at", OLLAMA_URL,
              "\nStart it with: ollama serve   and pull a model: ollama pull", MODEL)
        sys.exit(1)
