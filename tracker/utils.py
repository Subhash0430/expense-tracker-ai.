from django.conf import settings
from .models import Expense, Budget
from django.db.models import Sum
import json
import re
from urllib import request, error

# Shared persona for chat + AI Tips (matches ExpenseIQ in templates)
EXPENSEIQ_APP_CONTEXT = """You are the AI assistant inside ExpenseIQ, a personal expense-tracking web app.
What users can do here: register/login; Dashboard (month total, category & daily charts, recent expenses); Add Expense; list/filter All Expenses; set per-category monthly Budgets; Export CSV; AI Tips page; and this AI Chat.
Expense fields: title, amount (₹ INR), category, date, optional note. Categories: Food & Dining, Transport, Shopping, Entertainment, Health & Medical, Education, Utilities, Other.
When suggesting actions, name real app areas (e.g. "set a budget on the Budget page", "check Dashboard charts")."""


def _infer_chat_limits(user_message):
    """
    How many lines to allow and token budget, from the user's wording.
    Honors e.g. "in 10 lines", "5 bullet points"; also short vs long style.
    """
    text = (user_message or "").lower()
    max_lines = 8
    max_tokens = 520

    # "10 lines", "in 10 line", common typo "linnes"
    m = re.search(r"\b(\d{1,2})\s*(?:lines?|linnes)\b", text)
    if m:
        n = int(m.group(1))
        max_lines = max(1, min(n, 25))
        max_tokens = min(200 + max_lines * 75, 2000)
        return max_lines, max_tokens

    m = re.search(r"\b(\d{1,2})\s*(?:bullet\s*points?|bullets)\b", text)
    if m:
        n = int(m.group(1))
        max_lines = max(1, min(n, 25))
        max_tokens = min(200 + max_lines * 75, 2000)
        return max_lines, max_tokens

    if re.search(
        r"\b(short|brief|concise|quick|tl;dr|few\s+lines?|couple\s+lines?|small\s+paragraph)\b",
        text,
    ):
        return 5, 320

    if re.search(
        r"\b(long|detailed|deep|elaborate|comprehensive|in\s+detail|step\s+by\s+step|explain\s+more)\b",
        text,
    ):
        return 14, 950

    return max_lines, max_tokens


def get_expense_chart_data(expenses):
    category_data = {}
    daily_data = {}
    for exp in expenses:
        # Category aggregation
        cat = exp.get_category_display()
        category_data[cat] = category_data.get(cat, 0) + float(exp.amount)
        # Daily aggregation
        day = exp.date.strftime('%d %b')
        daily_data[day] = daily_data.get(day, 0) + float(exp.amount)
    
    return category_data, daily_data


def get_budget_alerts(user, month, year):
    alerts = []
    budgets = Budget.objects.filter(user=user, month=month, year=year)

    for budget in budgets:
        spent = Expense.objects.filter(
            user=user,
            category=budget.category,
            date__month=month,
            date__year=year
        ).aggregate(total=Sum('amount'))['total'] or 0

        percent = (float(spent) / float(budget.monthly_limit)) * 100

        if percent >= 100:
            alerts.append({
                'category': budget.get_category_display(),
                'status': 'exceeded',
                'spent': spent,
                'limit': budget.monthly_limit,
                'percent': round(percent, 1),
            })
        elif percent >= 80:
            alerts.append({
                'category': budget.get_category_display(),
                'status': 'warning',
                'spent': spent,
                'limit': budget.monthly_limit,
                'percent': round(percent, 1),
            })
    return alerts


def _build_budget_vs_spent(user, month, year):
    """Per-category budget limits vs actual spend (for AI context)."""
    budgets = Budget.objects.filter(user=user, month=month, year=year).order_by('category')
    if not budgets.exists():
        return "No budgets set for this month."

    lines = ["Budget vs spending (this month, per category you set):\n"]
    for b in budgets:
        spent = Expense.objects.filter(
            user=user,
            category=b.category,
            date__month=month,
            date__year=year,
        ).aggregate(total=Sum('amount'))['total'] or 0
        spent_f = float(spent)
        limit_f = float(b.monthly_limit)
        if limit_f > 0:
            pct = (spent_f / limit_f) * 100
        else:
            pct = 0.0
        over = spent_f - limit_f
        if over > 0:
            status = f"OVER by ₹{over:.2f}"
        elif over < 0:
            status = f"₹{abs(over):.2f} under limit"
        else:
            status = "exactly at limit"
        lines.append(
            f"  - {b.get_category_display()}: spent ₹{spent_f:.2f} / budget ₹{limit_f:.2f} "
            f"({pct:.1f}%) — {status}"
        )
    return "\n".join(lines)


def _build_monthly_summary(user, month, year):
    expenses = Expense.objects.filter(
        user=user, date__month=month, date__year=year
    )

    if not expenses.exists():
        return "No expenses found for this month to analyze."

    category_totals = {}
    for exp in expenses:
        cat = exp.get_category_display()
        category_totals[cat] = category_totals.get(cat, 0) + float(exp.amount)

    total_spent = sum(category_totals.values())
    if total_spent <= 0:
        return "No positive expenses found for this month to analyze."

    summary = f"Total spent: ₹{total_spent:.2f}\nBreakdown:\n"
    for cat, amt in category_totals.items():
        summary += f"  - {cat}: ₹{amt:.2f} ({(amt/total_spent*100):.1f}%)\n"
    return summary


def _openai_response(prompt, max_output_tokens=400):
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        return None

    payload = {
        "model": "gpt-4.1-mini",
        "input": prompt,
        "max_output_tokens": max_output_tokens,
    }
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            output_text = (body.get("output_text") or "").strip()
            if output_text:
                return output_text

            # Fallback parser for responses that return text in nested output/content blocks.
            chunks = []
            for item in body.get("output", []) or []:
                for content in item.get("content", []) or []:
                    if content.get("type") in ("output_text", "text"):
                        text_value = (content.get("text") or "").strip()
                        if text_value:
                            chunks.append(text_value)
            if chunks:
                return "\n".join(chunks)

            return "AI returned an empty response. Please try again."
    except error.HTTPError as e:
        try:
            details = e.read().decode("utf-8")
        except Exception:
            details = str(e)
        return f"OpenAI error: {details}"
    except Exception as e:
        return f"OpenAI error: {str(e)}"


def _anthropic_response(prompt, max_tokens=400):
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        return f"Anthropic error: {str(e)}"


def _cap_lines(text, max_lines=5, ellipsis="…"):
    """Hard cap visible lines so UI stays short even if the model is verbose."""
    if not text or not str(text).strip():
        return text
    t = str(text).strip().replace("\r\n", "\n")
    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
    if len(lines) == 1:
        blob = lines[0]
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", blob) if p.strip()]
        if len(parts) > max_lines:
            return "\n".join(parts[:max_lines]) + f"\n{ellipsis}"
        return blob
    if len(lines) <= max_lines:
        return t
    return "\n".join(lines[:max_lines]) + f"\n{ellipsis}"


def _maybe_cap_response(text, max_lines):
    """Cap length for normal replies; leave API error strings untouched."""
    if not text or not str(text).strip():
        return text
    s = str(text).strip()
    if s.startswith("OpenAI error") or s.startswith("Anthropic error"):
        return text
    return _cap_lines(text, max_lines=max_lines)


def get_ai_suggestions(user, month, year):
    summary = _build_monthly_summary(user, month, year)
    if summary.startswith("No "):
        return summary

    budget_block = _build_budget_vs_spent(user, month, year)
    prompt = f"""{EXPENSEIQ_APP_CONTEXT}

You are generating the "AI Tips" panel for month {month}/{year}. Use only the data below (₹ amounts).

{budget_block}

Monthly expense summary:
{summary}

Output rules:
- Exactly 3 bullet lines, each starting with "- ".
- One clear tip per line (max ~18 words). No greeting or sign-off.
- Prioritize categories that are over budget or near limit; otherwise biggest spend categories.
- Tips should feel actionable in ExpenseIQ (e.g. adjust budget, cut a category, review Dashboard)."""

    openai_reply = _openai_response(prompt, max_output_tokens=260)
    if openai_reply:
        return _maybe_cap_response(openai_reply, max_lines=5)

    anthropic_reply = _anthropic_response(prompt, max_tokens=260)
    if anthropic_reply:
        return _maybe_cap_response(anthropic_reply, max_lines=5)

    return "AI suggestions unavailable: configure OPENAI_API_KEY or ANTHROPIC_API_KEY."


def get_ai_chat_reply(user, month, year, user_message):
    summary = _build_monthly_summary(user, month, year)
    budget_block = _build_budget_vs_spent(user, month, year)
    max_lines, max_tokens = _infer_chat_limits(user_message)

    prompt = f"""{EXPENSEIQ_APP_CONTEXT}

Chat context — calendar month {month}/{year} (₹ INR):

{budget_block}

Monthly spending overview (all categories combined):
{summary}

LENGTH (follow closely):
- Use at most {max_lines} non-empty lines (each line = one sentence OR one "- "/ "• " bullet).
- If the user asked for a specific number of lines (e.g. ten), aim for that many substantive lines, never more than {max_lines}.
- Avoid filler intros ("Sure!", "Here you go"); end without a long wrap-up.

CONTENT:
- Budget/overspend questions: lead with the matching category from "Budget vs spending" (spent vs limit, over/under ₹).
- Do not reply with only the month total unless they clearly ask for overall monthly total.
- Reference ExpenseIQ features when it helps (Dashboard, Budget page, Add Expense, export).

User message: {user_message}"""

    openai_reply = _openai_response(prompt, max_output_tokens=max_tokens)
    if openai_reply:
        return _maybe_cap_response(openai_reply, max_lines=max_lines)

    anthropic_reply = _anthropic_response(prompt, max_tokens=max_tokens)
    if anthropic_reply:
        return _maybe_cap_response(anthropic_reply, max_lines=max_lines)

    return "AI chat unavailable: configure OPENAI_API_KEY or ANTHROPIC_API_KEY."