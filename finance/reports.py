from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from .models import Invoice, Payment, Expense


class ReportService:

    @staticmethod
    def date_range(period: str):
        today = date.today()
        if period == 'this_month':
            return today.replace(day=1), today
        if period == 'last_month':
            first = today.replace(day=1) - timedelta(days=1)
            return first.replace(day=1), first
        if period == 'this_quarter':
            q = (today.month - 1) // 3
            start = today.replace(month=q * 3 + 1, day=1)
            return start, today
        if period == 'this_year':
            return today.replace(month=1, day=1), today
        if period == 'last_30':
            return today - timedelta(days=30), today
        if period == 'last_90':
            return today - timedelta(days=90), today
        # default: this month
        return today.replace(day=1), today

    @staticmethod
    def income_statement(start: date, end: date) -> dict:
        """Revenue vs Expenses summary."""
        revenue = Payment.objects.filter(
            date__gte=start, date__lte=end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        expenses = Expense.objects.filter(
            date__gte=start, date__lte=end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        by_category = Expense.objects.filter(
            date__gte=start, date__lte=end
        ).values('category').annotate(total=Sum('amount')).order_by('-total')

        invoiced = Invoice.objects.filter(
            issue_date__gte=start, issue_date__lte=end
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

        outstanding = Invoice.objects.filter(
            status__in=['issued', 'partial', 'overdue']
        ).aggregate(
            total=Sum('total_amount'),
            paid=Sum('amount_paid')
        )
        balance_due = (outstanding['total'] or 0) - (outstanding['paid'] or 0)

        return {
            'revenue': revenue,
            'expenses': expenses,
            'net_profit': revenue - expenses,
            'invoiced': invoiced,
            'balance_due': balance_due,
            'expense_breakdown': list(by_category),
            'profit_margin': round((revenue - expenses) / revenue * 100, 1) if revenue else 0,
        }

    @staticmethod
    def accounts_receivable_aging() -> dict:
        """Classify outstanding invoices by days overdue."""
        today = date.today()
        buckets = {
            'current': [],
            '1_30': [],
            '31_60': [],
            '61_90': [],
            'over_90': [],
        }
        outstanding = Invoice.objects.filter(
            status__in=['issued', 'partial', 'overdue']
        ).select_related('client')

        totals = {k: Decimal('0') for k in buckets}

        for inv in outstanding:
            days = (today - inv.due_date).days
            bal = inv.balance_due
            if days <= 0:
                buckets['current'].append(inv)
                totals['current'] += bal
            elif days <= 30:
                buckets['1_30'].append(inv)
                totals['1_30'] += bal
            elif days <= 60:
                buckets['31_60'].append(inv)
                totals['31_60'] += bal
            elif days <= 90:
                buckets['61_90'].append(inv)
                totals['61_90'] += bal
            else:
                buckets['over_90'].append(inv)
                totals['over_90'] += bal

        return {'buckets': buckets, 'totals': totals, 'grand_total': sum(totals.values())}

    @staticmethod
    def monthly_revenue(months: int = 6) -> list:
        """Revenue collected per month for chart."""
        today = date.today()
        result = []
        for i in range(months - 1, -1, -1):
            # Go back i months
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1
            first = date(year, month, 1)
            if month == 12:
                last = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                last = date(year, month + 1, 1) - timedelta(days=1)

            rev = Payment.objects.filter(
                date__gte=first, date__lte=last
            ).aggregate(t=Sum('amount'))['t'] or 0

            exp = Expense.objects.filter(
                date__gte=first, date__lte=last
            ).aggregate(t=Sum('amount'))['t'] or 0

            result.append({
                'label': first.strftime('%b %Y'),
                'revenue': float(rev),
                'expenses': float(exp),
                'profit': float(rev) - float(exp),
            })
        return result

    @staticmethod
    def sales_by_service(start: date, end: date) -> list:
        """Which services generated the most revenue."""
        from tickets.models import Ticket
        from django.db.models import F
        result = Invoice.objects.filter(
            issue_date__gte=start, issue_date__lte=end
        ).values(
            service_name=F('ticket__service__name')
        ).annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('-total')
        return [r for r in result if r['service_name']]

    @staticmethod
    def client_revenue(start: date, end: date, limit: int = 10) -> list:
        """Top clients by revenue."""
        return list(
            Invoice.objects.filter(
                issue_date__gte=start, issue_date__lte=end
            ).values('client__name').annotate(
                total=Sum('total_amount'),
                paid=Sum('amount_paid'),
                count=Count('id')
            ).order_by('-total')[:limit]
        )
