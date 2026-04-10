from django.urls import path
from . import views

urlpatterns = [
    # AUTH
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # DASHBOARD
    path('dashboard/', views.dashboard, name='dashboard'),

    # EXPENSES
    path('add/', views.add_expense, name='add_expense'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('delete/<int:pk>/', views.delete_expense, name='delete_expense'),

    # BUDGET
    path('budget/', views.budget_view, name='budget'),
    path('budget-ai/', views.budget_ai_api, name='budget_ai_api'),

    # EXPORT
    path('export/', views.export_csv, name='export_csv'),
    path('ai-suggestions/', views.ai_suggestions, name='ai_suggestions'),

    # 🔥 AI CHAT
    path('chat/', views.chat_page, name='chat'),
    path('chat-api/', views.chat_api, name='chat_api'),
]