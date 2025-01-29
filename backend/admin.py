from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Work, WorkItem, Facility, Payment, Comment


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number')
    ordering = ('username',)

    # Remove manager from fieldsets and add idNum
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'idNum')}),
        (_('Role'), {'fields': ('role',)}),  # Removed manager
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    # Add idNum to add_fieldsets
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email', 'first_name',
                       'last_name', 'role', 'phone_number', 'idNum'),
        }),
    )


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = (
        'work_number', 'classification', 'status', 'contractor', 'manager', 'facility', 'start_date', 'due_end_date')
    list_filter = ('classification', 'status', 'contractor', 'manager', 'facility')
    search_fields = ('work_number', 'contractor__username', 'manager__username', 'facility__name')
    date_hierarchy = 'start_date'


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = (
        'work', 'section', 'description', 'status', 'contract_amount', 'actual_amount', 'total_section_cost')
    list_filter = ('status', 'work__classification')
    search_fields = ('description', 'work__work_number')


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('facility_number', 'name', 'description')
    search_fields = ('name', 'facility_number')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['work', 'invoice_number', 'payment_date', 'amount_paid', 'payment_manager', 'approval_manager']
    search_fields = ['work__work_number', 'invoice_number', 'payment_manager__username', 'approval_manager__username']
    # readonly_fields = ['work']  # Make the 'work' field read-only


# admin.site.register(Comment)
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('work', 'user', 'text', 'created_at', 'updated_at')
    search_fields = ('work__work_number', 'user__username', 'text')  # Search by work number, username, or comment text
    readonly_fields = ('created_at', 'updated_at')  # Make created_at and updated_at read-only

    list_filter = ('work',)

    raw_id_fields = ('work', 'user')  # Use raw IDs for ForeignKeys

    fieldsets = (
        (None, {'fields': ('work', 'user', 'text')}),
    )