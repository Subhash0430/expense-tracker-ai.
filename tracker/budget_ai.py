"""
ExpenseIQ budget assistant: multi-turn flow on the Budget page.
Collects category → month/year → amount (₹), then confirms and saves.
"""
import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .models import Budget, CATEGORY_CHOICES

SESSION_KEY = 'expenseiq_budget_ai'

_MONTH_PATTERNS = [
    (1, r'\bjan(?:uary)?\b'),
    (2, r'\bfeb(?:ruary)?\b'),
    (3, r'\bmar(?:ch)?\b'),
    (4, r'\bapr(?:il)?\b'),
    (5, r'\bmay\b'),
    (6, r'\bjun(?:e)?\b'),
    (7, r'\bjul(?:y)?\b'),
    (8, r'\baug(?:ust)?\b'),
    (9, r'\bsep(?:t(?:ember)?)?\b'),
    (10, r'\boct(?:ober)?\b'),
    (11, r'\bnov(?:ember)?\b'),
    (12, r'\bdec(?:ember)?\b'),
]


def _category_line():
    return ', '.join(label for _, label in CATEGORY_CHOICES)


def _label_for_code(code):
    for k, v in CATEGORY_CHOICES:
        if k == code:
            return v
    return code or ''


def _parse_category(text):
    tl = text.lower().strip()
    if not tl:
        return None
    padded = f' {tl} '
    for code, label in CATEGORY_CHOICES:
        if f' {code} ' in padded:
            return code
        ln = label.lower()
        if ln in tl or ln.replace(' & ', ' and ') in tl.replace(' & ', ' and '):
            return code
    hints = (
        ('food', r'\b(food|dining|grocer|restaurant|eat|lunch|dinner)\b'),
        ('transport', r'\b(transport|uber|taxi|fuel|petrol|diesel|metro|bus|train)\b'),
        ('shopping', r'\b(shopping|clothes|amazon|flipkart)\b'),
        ('entertainment', r'\b(entertainment|movie|netflix|game|spotify)\b'),
        ('health', r'\b(health|medical|doctor|pharmacy|medicine|gym)\b'),
        ('education', r'\b(education|course|books|tuition|school)\b'),
        ('utilities', r'\b(utilities|electric|water|internet|wifi|rent bill)\b'),
        ('other', r'\b(other|misc|miscellaneous)\b'),
    )
    for code, pat in hints:
        if re.search(pat, tl):
            return code
    return None


def _parse_month_year(text, today=None):
    today = today or date.today()
    tl = text.lower()

    if re.search(r'\bnext\s+month\b', tl):
        if today.month == 12:
            return 1, today.year + 1
        return today.month + 1, today.year
    if re.search(r'\bthis\s+month\b', tl):
        return today.month, today.year

    m = re.search(r'\b(\d{1,2})\s*[/\-]\s*(\d{4})\b', tl)
    if m:
        mo, yr = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return mo, yr

    for num, pat in _MONTH_PATTERNS:
        if re.search(pat, tl, re.I):
            yr = today.year
            ym = re.search(r'\b(?:19\d{2}|20\d{2})\b', tl)
            if ym:
                yr = int(ym.group(0))
            return num, yr

    return None


def _parse_amount(text):
    """Extract ₹ amount; avoid treating years (e.g. 2026) as money unless currency given."""
    raw = text.replace(',', '')
    m = re.search(r'(?:₹|rs\.?|inr)\s*([\d]{1,9}(?:\.\d{1,2})?)', raw, re.I)
    if m:
        val = m.group(1)
    else:
        m = re.search(r'\b([\d]{1,9}(?:\.\d{1,2})?)\b', raw)
        if not m:
            return None
        val = m.group(1)
        if '.' not in val and len(val) == 4 and val.startswith(('19', '20')):
            return None
    try:
        d = Decimal(str(val))
        if d <= 0 or d > Decimal('99999999'):
            return None
        return str(d.quantize(Decimal('0.01')))
    except (InvalidOperation, ValueError):
        return None


def _fresh_state():
    return {
        'active': True,
        'category': None,
        'month': None,
        'year': None,
        'amount': None,
        'awaiting_confirm': False,
    }


def _apply_parsers(state, msg):
    if not state.get('category'):
        c = _parse_category(msg)
        if c:
            state['category'] = c
    my = _parse_month_year(msg)
    if my:
        state['month'], state['year'] = my
    amt = _parse_amount(msg)
    if amt:
        state['amount'] = amt


def _is_complete(state):
    return (
        state.get('category')
        and state.get('month') is not None
        and state.get('year') is not None
        and state.get('amount')
    )


def _next_prompt(state):
    if not state.get('category'):
        return (
            'Which category should this budget be for?\n'
            f'Choose one: {_category_line()}.'
        )
    if state.get('month') is None or state.get('year') is None:
        return (
            'Which month should this apply to?\n'
            'Say “this month”, “next month”, or a month name like “May 2026” '
            f'(year defaults to {date.today().year} if you omit it).'
        )
    if not state.get('amount'):
        return (
            'How much is the monthly limit in ₹?\n'
            'Example: 5000 or ₹12,000.'
        )
    return 'Reply yes to confirm or no to cancel.'


_START_INTENT = re.compile(
    r'\b(?:set|create|add|update|change|make)\s+(?:a\s+|my\s+|the\s+)?budget\b|'
    r'\bbudget\s+(?:for|to)\b|'
    r'\bhelp\s+(?:me\s+)?(?:set|with)\s+(?:a\s+)?budget\b',
    re.I,
)


def handle_budget_ai_conversation(user, message, session):
    msg = (message or '').strip()
    lower = msg.lower()

    if re.search(r'\b(cancel|stop|reset|start\s+over|never\s*mind)\b', lower):
        session.pop(SESSION_KEY, None)
        session.modified = True
        return {
            'reply': 'Cancelled. Say “Set a budget” when you want to try again.',
            'saved': False,
        }

    state = session.get(SESSION_KEY)

    if not state or not state.get('active'):
        if not _START_INTENT.search(lower):
            return {
                'reply': (
                    'I can walk you through setting a budget.\n'
                    'Say something like “Set a budget for next month”. I’ll ask which category, '
                    'which month, and how much (₹), then save when you confirm.\n'
                    f'Categories: {_category_line()}.'
                ),
                'saved': False,
            }
        state = _fresh_state()
        _apply_parsers(state, msg)
        session[SESSION_KEY] = state
        session.modified = True

        if _is_complete(state):
            state['awaiting_confirm'] = True
            session[SESSION_KEY] = state
            session.modified = True
            label = _label_for_code(state['category'])
            mo, yr = state['month'], state['year']
            return {
                'reply': (
                    f'Please confirm: {label} · {calendar.month_name[mo]} {yr} · ₹{state["amount"]}\n'
                    'Reply yes to save or no to cancel.'
                ),
                'saved': False,
            }

        return {'reply': _next_prompt(state), 'saved': False}

    if state.get('awaiting_confirm'):
        sn = lower.strip().rstrip('!.')
        if sn in ('n', 'no', 'nope', 'nah', 'cancel'):
            session.pop(SESSION_KEY, None)
            session.modified = True
            return {'reply': 'Okay — not saved. Say “Set a budget” to start over.', 'saved': False}
        if sn in ('y', 'yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'confirm', 'save', 'do it') or (
            len(sn) <= 40 and re.match(r'^(yes|ok|save|confirm)\b', sn)
        ):
            try:
                Budget.objects.update_or_create(
                    user=user,
                    category=state['category'],
                    month=state['month'],
                    year=state['year'],
                    defaults={'monthly_limit': Decimal(state['amount'])},
                )
            except Exception as e:
                return {'reply': f'Could not save budget: {e}', 'saved': False}
            label = _label_for_code(state['category'])
            mo, yr = state['month'], state['year']
            session.pop(SESSION_KEY, None)
            session.modified = True
            return {
                'reply': (
                    f'Saved {label} — ₹{state["amount"]} for {calendar.month_name[mo]} {yr}.\n'
                    'The page will refresh so the table updates.'
                ),
                'saved': True,
            }
        return {
            'reply': 'Please reply yes to save this budget or no to cancel.',
            'saved': False,
        }

    _apply_parsers(state, msg)
    session[SESSION_KEY] = state
    session.modified = True

    if _is_complete(state):
        state['awaiting_confirm'] = True
        session[SESSION_KEY] = state
        session.modified = True
        label = _label_for_code(state['category'])
        mo, yr = state['month'], state['year']
        return {
            'reply': (
                f'Please confirm: {label} · {calendar.month_name[mo]} {yr} · ₹{state["amount"]}\n'
                'Reply yes to save or no to cancel.'
            ),
            'saved': False,
        }

    return {'reply': _next_prompt(state), 'saved': False}
