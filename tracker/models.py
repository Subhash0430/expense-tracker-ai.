from django.db import models
from django.contrib.auth.models import User


CATEGORY_CHOICES = [
    ('food', 'Food & Dining'),
    ('transport', 'Transport'),
    ('shopping', 'Shopping'),
    ('entertainment', 'Entertainment'),
    ('health', 'Health & Medical'),
    ('education', 'Education'),
    ('utilities', 'Utilities'),
    ('other', 'Other'),
]


class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    date = models.DateField()
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.title} - ₹{self.amount}"


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    monthly_limit = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.IntegerField()
    year = models.IntegerField()

    class Meta:
        unique_together = ('user', 'category', 'month', 'year')

    def __str__(self):
        return f"{self.user.username} - {self.category} - ₹{self.monthly_limit}"