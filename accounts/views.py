from django.views.generic import CreateView, ListView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from .models import User, Role, UserRole
from .forms import ClientRegisterForm, CustomLoginForm


class ClientRegisterView(CreateView):
    model = User
    form_class = ClientRegisterForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.user_type = 'client'
        user.username = form.cleaned_data['email']
        user.is_active = True
        user.save()
        role, _ = Role.objects.get_or_create(code='CLIENT', defaults={'name': 'Client'})
        UserRole.objects.create(user=user, role=role)
        messages.success(self.request, 'Account created! Please log in.')
        return redirect(self.success_url)


class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'accounts/login.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['login_hint'] = 'Sign in with your email or phone number'
        return ctx


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login')


class StaffListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'accounts/staff_list.html'
    context_object_name = 'staff'

    def get_queryset(self):
        return User.objects.filter(user_type='staff').prefetch_related('user_roles__role')


from django.views.generic import TemplateView


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'
