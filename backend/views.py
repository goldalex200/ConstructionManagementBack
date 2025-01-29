from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, Q, F, Avg
from django.utils import timezone
from datetime import datetime
from .permissions import ContractorPermission
# from .models import User, Work, WorkItem, Facility, ContractorRating
from .models import User, Work, WorkItem, Facility, Payment, Comment
from .serializers import (
    UserSerializer, WorkSerializer, WorkItemSerializer,
    FacilitySerializer, NestedWorkItemSerializer, UserRoleSerializer, PaymentSerializer, CommentSerializer
    # FacilitySerializer, ContractorRatingSerializer, NestedWorkItemSerializer, UserRoleSerializer
)


class WorkViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Work.objects.all()

        # Filter based on user role
        if user.role in ['CONTRACTOR', 'CONTRACTOR_VIEWER']:
            return queryset.filter(contractor__idNum=user.idNum)
        elif user.role in ['GENERAL_ENGINEER', 'SUPER_ADMIN']:
            return queryset  # Full access
        elif user.role == 'MANAGER':
            return queryset.filter(manager=user)
        elif user.role == 'PAYMENT_ADMIN':
            return queryset  # Read-only, for filtering later in permissions

        return queryset.none()

    def create(self, request, *args, **kwargs):
        """Allow only MANAGER, GENERAL_ENGINEER, SUPER_ADMIN to create works."""
        if request.user.role not in ['MANAGER', 'GENERAL_ENGINEER', 'SUPER_ADMIN']:
            return Response(
                {"error": "You are not authorized to create new works."},
                status=403
            )
        return super().create(request, *args, **kwargs)

    def perform_update(self, serializer):
        """Restrict updating permissions for specific roles."""
        work = self.get_object()
        user = self.request.user

        if user.role == 'CONTRACTOR' and work.contractor != user:
            raise PermissionDenied("You can only edit your own works.")
        if user.role == 'PAYMENT_ADMIN':
            if set(serializer.validated_data.keys()) != {'status'} or serializer.validated_data['status'] != 'PAID':
                return Response(
                    {"error": "PAYMENT_ADMIN can only update status to 'PAID'."},
                    status=403
                )
        if user.role in ['CONTRACTOR_VIEWER']:
            raise PermissionDenied("You do not have permission to update works.")
        # Allow other roles to update
        serializer.save()

    def perform_destroy(self, instance):
        """Restrict deletion permissions."""
        user = self.request.user

        if user.role not in ['MANAGER', 'GENERAL_ENGINEER', 'SUPER_ADMIN']:
            raise PermissionDenied("You do not have permission to delete works.")

        instance.delete()

    @action(detail=False, methods=['get'])
    def classifications(self, request):  # Create new action for classifications
        classifications = {choice[0]: choice[1] for choice in Work.CLASSIFICATION_CHOICES}
        return Response(classifications)

    @action(detail=True, methods=['patch'])
    def change_payment_status(self, request, pk=None):
        """Allow Payment Admins to change payment-related fields."""
        work = self.get_object()
        user = self.request.user

        if user.role != 'PAYMENT_ADMIN':
            return Response({'error': 'Unauthorized'}, status=403)

        status = request.data.get('status')
        if status not in ['WAITING_PAYMENT', 'PAID']:
            return Response(
                {'error': 'Payment Admin can only change payment-related statuses.'},
                status=400
            )

        work.status = status
        work.save()
        return Response({'status': f'Work status changed to {status}.'})

    @action(detail=True, methods=['post'])
    def approve_work(self, request, pk=None):
        work = self.get_object()
        if request.user.role in ['GENERAL_ENGINEER', 'MANAGER']:
            work.status = 'APPROVED' if work.status == 'PENDING_APPROVAL' else 'FINISHED'
            work.save()
            return Response({'status': 'work approved'})
        return Response({'error': 'Unauthorized'}, status=403)

    @action(detail=True, methods=['post'])
    def complete_work(self, request, pk=None):
        work = self.get_object()
        if request.user == work.contractor:
            work.status = 'WAITING_MANAGER_APPROVAL'
            work.save()
            return Response({'status': 'work completed'})
        return Response({'error': 'Unauthorized'}, status=403)

    @action(detail=False, methods=['get'])
    def reports(self, request):
        queryset = self.get_queryset()
        report_type = request.query_params.get('type')
        contractor_id = request.query_params.get('contractor_id')  # Changed to contractor_id
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        facility_name = request.query_params.get('facility_name')
        classification = request.query_params.get('classification')

        # Apply filters
        if contractor_id:
            try:
                contractor = get_object_or_404(User, id=contractor_id)
                print(contractor)
                print('before', len(queryset))
                queryset = queryset.filter(contractor=contractor)  # Filter the queryset
                print('after', len(queryset))

            except (ValueError, TypeError):
                return Response({'error': 'Invalid contractor ID'}, status=400)

        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(start_date__range=(start_date, end_date))
            except ValueError:
                print(ValueError)
                return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        if facility_name:
            queryset = queryset.filter(facility__name=facility_name)

        if classification:
            queryset = queryset.filter(classification=classification)

        if report_type == 'cost':
            active_works = queryset.filter(status__in=['APPROVED', 'IN_PROGRESS'])
            paid_works = queryset.filter(status='PAID')

            budget = active_works.aggregate(Sum('items__contract_amount'))['items__contract_amount__sum'] or 0
            amount_paid = paid_works.aggregate(Sum('items__actual_amount'))['items__actual_amount__sum'] or 0

            budget_exception = queryset.filter(
                Q(items__actual_amount__gt=F('items__contract_amount')) & Q(status__in=['APPROVED', 'IN_PROGRESS'])
            ).aggregate(
                exception=Sum(F('items__actual_amount') - F('items__contract_amount'))
            )['exception'] or 0

            # Calculate free budget
            free_budget = active_works.annotate(
                free_item_budget=Sum(
                    F('items__contract_amount') - F('items__actual_amount'),
                    filter=Q(items__actual_amount__lt=F('items__contract_amount'))
                )
            ).aggregate(total_free_budget=Sum('free_item_budget'))['total_free_budget'] or 0
            return Response({
                'budget': budget,
                'amount_paid': amount_paid,
                'budget_exception': budget_exception,
                'free_budget': free_budget,
            })

        elif report_type == 'facility_faults':
            return Response(
                queryset.filter(classification='FAULT').values('facility__name').annotate(  # Changed to facility__name
                    fault_count=Count('id')
                )
            )

        elif report_type == 'time':
            now = timezone.now()
            return Response({
                'delayed': queryset.filter(due_end_date__lt=now, status__in=['IN_PROGRESS', 'APPROVED']).count(),
                'in_time': queryset.filter(due_end_date__gte=now, status__in=['IN_PROGRESS', 'APPROVED']).count(),
            })

        elif report_type == 'contractors':
            top_contractors = queryset.values('contractor__username', 'contractor__first_name',
                                              'contractor__last_name').annotate(
                avg_quality=Avg('quality_score'),
                avg_time=Avg('time_score'),
                avg_cost=Avg('cost_score'),
                overall_avg=Avg(
                    (
                            F('quality_score') + F('time_score') + F('cost_score')
                    ) / 3.0
                )
            ).order_by('-overall_avg')[:10]
            return Response(top_contractors)

        elif report_type == 'contractorsWorst':
            worst_contractors = queryset.values('contractor__username', 'contractor__first_name',
                                                'contractor__last_name').annotate(
                avg_quality=Avg('quality_score'),
                avg_time=Avg('time_score'),
                avg_cost=Avg('cost_score'),
                overall_avg=Avg(
                    (
                            F('quality_score') + F('time_score') + F('cost_score')
                    ) / 3.0
                )
            ).order_by('overall_avg')[:10]  # Order by ascending (worst first)
            return Response(worst_contractors)

        elif report_type == 'works':
            finished_statuses = ['FINISHED', 'PAID', 'WAITING_PAYMENT']
            active_works_count = Work.objects.exclude(status__in=finished_statuses).count()
            finished_works_count = Work.objects.filter(status__in=finished_statuses).count()

            return Response({
                'active_works': active_works_count,
                'finished_works': finished_works_count,
            })
        return Response({'error': 'Invalid report type'}, status=status.HTTP_400_BAD_REQUEST)

    # @action(detail=False, methods=['get'])
    # def work_statuses(self, request):
    #     statuses = [{'code': code, 'label': label} for code, label in Work.STATUS_CHOICES]
    #     return Response(statuses)
    @action(detail=False, methods=['get'])
    def work_statuses(self, request):
        user = request.user
        role = user.role  # Or however you access the user's role

        statuses = []

        for code, label in Work.STATUS_CHOICES:
            status_data = {'code': code, 'label': label, 'chosable': False}  # Default: not chosable

            if user.is_superuser or user.role == 'GENERAL_ENGINEER':
                status_data['chosable'] = True
            elif role == 'CONTRACTOR':  # Example roles - adjust as needed
                if code in ['PENDING', 'IN_PROGRESS']:  # Example: Contractor can change these
                    status_data['chosable'] = True
            elif role == 'MANAGER':
                if code not in ['PAID', 'WAITING_PAYMENT']:  # Example: Manager can change all except PAID
                    status_data['chosable'] = True
            elif role == 'PAYMENT_ADMIN':
                if code in ['WAITING_PAYMENT', 'PAID']:  # Example: Payment Admin can change these
                    status_data['chosable'] = True

            statuses.append(status_data)

        return Response(statuses)


class WorkItemViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            if hasattr(self, 'parent_object'):
                return NestedWorkItemSerializer
            else:
                return WorkItemSerializer
        return WorkItemSerializer

    # serializer_class = WorkItemSerializer
    permission_classes = [IsAuthenticated, ContractorPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            if user.role in ['GENERAL_ENGINEER', 'SUPER_ADMIN',
                             'PAYMENT_ADMIN']:  # Updated to match uppercase role names
                return WorkItem.objects.all()
            elif user.role == 'MANAGER':
                return WorkItem.objects.filter(work__manager=user)
            elif user.role in ['CONTRACTOR', 'CONTRACTOR_VIEWER']:
                return WorkItem.objects.filter(work__contractor__idNum=user.idNum)
        return WorkItem.objects.none()

    # @action(detail=False, methods=['get'])
    # def work_item_statuses(self, request):
    #     statuses = [{'code': code, 'label': label} for code, label in WorkItem.STATUS_CHOICES]
    #     return Response(statuses)

    @action(detail=False, methods=['get'])
    def work_item_statuses(self, request):
        user = request.user
        role = user.role
        statuses = []

        for code, label in WorkItem.STATUS_CHOICES:
            status_data = {'code': code, 'label': label, 'chosable': False}  # Default: not chosable

            if user.is_superuser:
                status_data['chosable'] = True
            elif role == 'CONTRACTOR':
                if code in ['IN_PROGRESS', 'COMPLETED_BY_CONTRACTOR']:
                    status_data['chosable'] = True
            elif role == 'CONTRACTOR_VIEWER':
                pass  # Default is false, so no need to change
            elif role == 'MANAGER':
                if code not in ['WAITING_PAYMENT', 'PAID']:
                    status_data['chosable'] = True
            elif role == 'GENERAL_ENGINEER':
                status_data['chosable'] = True  # Default is true, so no need to change
            elif role == 'PAYMENT_ADMIN':
                if code in ['WAITING_PAYMENT', 'PAID']:
                    status_data['chosable'] = True

            statuses.append(status_data)

        return Response(statuses)


class FacilityViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer


# class ContractorRatingViewSet(viewsets.ModelViewSet):
#     permission_classes = [IsAuthenticated]
#     serializer_class = ContractorRatingSerializer
#
#     def get_queryset(self):
#         if self.request.user.role == 'CONTRACTOR':
#             return ContractorRating.objects.filter(contractor=self.request.user)
#         return ContractorRating.objects.all()


class UserRoleListViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UserRoleSerializer

    def get_queryset(self):
        # Filter users based on request parameters
        role = self.request.query_params.get('role')
        roles = [role] if role else ['CONTRACTOR', 'MANAGER', 'SUPER_ADMIN']  # Default roles

        return User.objects.filter(role__in=roles).values('id', 'username', 'first_name', 'last_name', 'idNum', 'role')

    @action(detail=False, methods=['get'])
    def managers_and_superadmins_for_dropdown(self, request):
        queryset = User.objects.filter(role__in=['MANAGER', 'SUPER_ADMIN']).values('id', 'username', 'first_name',
                                                                                   'last_name', 'idNum', 'role')
        serializer = UserRoleSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def contractors_for_dropdown(self, request):
        queryset = User.objects.filter(role='CONTRACTOR').values('id', 'username', 'first_name', 'last_name', 'idNum',
                                                                 'role')
        serializer = UserRoleSerializer(queryset, many=True)
        return Response(serializer.data)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]  # Or more specific permissions

    def create(self, request, *args, **kwargs):
        work_id = request.data.get('work')  # Get work ID from request data
        try:
            work = Work.objects.get(pk=work_id)  # Get the work instance
        except Work.DoesNotExist:
            return Response({'error': 'Work not found'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(work=work)  # Save the payment with the work instance
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        try:
            payment = Payment.objects.get(pk=pk)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(payment, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class CommentViewSet(viewsets.ModelViewSet):
#     serializer_class = CommentSerializer
#     permission_classes = [IsAuthenticated]
#
#     def get_queryset(self):
#         return Comment.objects.filter(work_id=self.kwargs['work_pk'])
#
#     def perform_create(self, serializer):
#         work_id = self.kwargs['work_pk']  # Get work_id from URL
#         serializer.save(
#             user=self.request.user,
#             work_id=work_id  # Use work_id from URL
#         )
class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        print(f"self.kwargs: {self.kwargs}")  # Print kwargs for debugging
        work_id = self.kwargs['work_pk']
        print(f"work_id: {work_id}")  # Print work_id for debugging
        return Comment.objects.filter(work_id=work_id).order_by('created_at')

    def perform_create(self, serializer):
        work_id = self.kwargs['work_pk']
        print(f"work_id (in perform_create): {work_id}")  # Print in perform_create too
        serializer.save(user=self.request.user, work_id=work_id)
