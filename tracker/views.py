from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from datetime import date
import csv
import json

from .models import Expense, Budget, CATEGORY_CHOICES
from .forms import RegisterForm, ExpenseForm, BudgetForm
from .utils import get_budget_alerts, get_ai_suggestions, get_ai_chat_reply
from .budget_ai import handle_budget_ai_conversation


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'tracker/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'tracker/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    today = date.today()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))

    expenses = Expense.objects.filter(
        user=request.user, date__month=month, date__year=year
    )

    total = expenses.aggregate(total=Sum('amount'))['total'] or 0

    category_data = {}
    for exp in expenses:
        cat = exp.get_category_display()
        category_data[cat] = category_data.get(cat, 0) + float(exp.amount)

    daily_data = {}
    for exp in expenses:
        day = exp.date.strftime('%d %b')
        daily_data[day] = daily_data.get(day, 0) + float(exp.amount)

    alerts = get_budget_alerts(request.user, month, year)
    recent_expenses = expenses[:5]

    context = {
        'total': total,
        'expenses': recent_expenses,
        'alerts': alerts,
        'month': month,
        'year': year,
        'category_labels': json.dumps(list(category_data.keys())),
        'category_values': json.dumps(list(category_data.values())),
        'daily_labels': json.dumps(list(daily_data.keys())),
        'daily_values': json.dumps(list(daily_data.values())),
    }
    return render(request, 'tracker/dashboard.html', context)


@login_required
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, 'Expense added successfully!')
            return redirect('expense_list')
    else:
        form = ExpenseForm(initial={'date': date.today()})
    return render(request, 'tracker/add_expense.html', {'form': form})


@login_required
def expense_list(request):
    expenses = Expense.objects.filter(user=request.user)
    category_filter = request.GET.get('category', '')
    if category_filter:
        expenses = expenses.filter(category=category_filter)
    return render(request, 'tracker/expense_list.html', {
        'expenses': expenses,
        'categories': CATEGORY_CHOICES,
        'selected': category_filter,
    })


@login_required
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    expense.delete()
    messages.success(request, 'Expense deleted.')
    return redirect('expense_list')


@login_required
def budget_view(request):
    today = date.today()
    budgets = Budget.objects.filter(
        user=request.user, month=today.month, year=today.year
    )
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            Budget.objects.update_or_create(
                user=request.user,
                category=budget.category,
                month=budget.month,
                year=budget.year,
                defaults={'monthly_limit': budget.monthly_limit}
            )
            messages.success(request, 'Budget saved!')
            return redirect('budget')
    else:
        form = BudgetForm(initial={'month': today.month, 'year': today.year})
    return render(request, 'tracker/budget.html', {'form': form, 'budgets': budgets})


@login_required
def budget_ai_api(request):
    if request.method != 'POST':
        return JsonResponse({'reply': 'Only POST is allowed.', 'saved': False}, status=405)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'reply': 'Invalid JSON.', 'saved': False}, status=400)
    message = (payload.get('message') or '').strip()
    if not message:
        return JsonResponse({'reply': 'Please enter a message.', 'saved': False}, status=400)
    result = handle_budget_ai_conversation(request.user, message, request.session)
    return JsonResponse(result)


@login_required
def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expenses.csv"'
    writer = csv.writer(response)
    writer.writerow(['Title', 'Amount', 'Category', 'Date', 'Note'])
    for exp in Expense.objects.filter(user=request.user):
        writer.writerow([exp.title, exp.amount, exp.get_category_display(), exp.date, exp.note])
    return response


@login_required
def ai_suggestions(request):
    today = date.today()
    month = today.month
    year = today.year
    expenses = Expense.objects.filter(
        user=request.user, date__month=month, date__year=year
    )
    total = expenses.aggregate(total=Sum('amount'))['total'] or 0

    category_data = {}
    for exp in expenses:
        cat = exp.get_category_display()
        category_data[cat] = category_data.get(cat, 0) + float(exp.amount)

    daily_data = {}
    for exp in expenses:
        day = exp.date.strftime('%d %b')
        daily_data[day] = daily_data.get(day, 0) + float(exp.amount)

    suggestion = get_ai_suggestions(request.user, today.month, today.year)
    return render(request, 'tracker/dashboard.html', {
        'ai_suggestion': suggestion,
        'show_ai': True,
        'total': total,
        'expenses': expenses[:5],
        'alerts': get_budget_alerts(request.user, month, year),
        'month': month,
        'year': year,
        'category_labels': json.dumps(list(category_data.keys())),
        'category_values': json.dumps(list(category_data.values())),
        'daily_labels': json.dumps(list(daily_data.keys())),
        'daily_values': json.dumps(list(daily_data.values())),
    })


@login_required
def chat_page(request):
    return render(request, 'tracker/chat.html')


@login_required
def chat_api(request):
    if request.method != 'POST':
        return JsonResponse({'reply': 'Only POST requests are allowed.'}, status=405)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'reply': 'Invalid JSON payload.'}, status=400)

    message = (payload.get('message') or '').strip()
    if not message:
        return JsonResponse({'reply': 'Please enter a message.'}, status=400)

    today = date.today()
    reply = get_ai_chat_reply(request.user, today.month, today.year, message)
    return JsonResponse({'reply': reply})