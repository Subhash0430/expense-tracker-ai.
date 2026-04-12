from django.contrib import admin
from .models import Expense, Budget

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'amount', 'category', 'date')
    list_filter = ('category', 'date', 'user')
    search_fields = ('title', 'category', 'note')

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'monthly_limit', 'month', 'year')
    list_filter = ('category', 'month', 'year')
    search_fields = ('user__username', 'category')
