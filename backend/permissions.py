from rest_framework.permissions import BasePermission


class ContractorPermission(BasePermission):
    """
    Custom permission to allow CONTRACTORs to only view and edit their work items.
    """

    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated and user.role == 'CONTRACTOR' and request.method == 'POST':
            return False  # Prevent CONTRACTOR from adding new work items
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == 'CONTRACTOR':
            # CONTRACTOR can only access their own work items
            return obj.work.contractor == user
        return True
