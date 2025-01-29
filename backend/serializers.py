from rest_framework import serializers
# from .models import User, Work, WorkItem, Facility, ContractorRating
from .models import User, Work, WorkItem, Facility, Payment, Comment
from django.contrib.auth import get_user_model
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import UserDetailsSerializer

User = get_user_model()


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'idNum', 'role')


class CustomUserDetailsSerializer(UserDetailsSerializer):
    class Meta(UserDetailsSerializer.Meta):
        fields = UserDetailsSerializer.Meta.fields + (
            'username', 'first_name', 'last_name', 'phone_number', 'idNum', 'role')
        # fields = ('pk', 'email', 'first_name', 'last_name', 'phone_number', 'idNum', 'role')


class CustomRegisterSerializer(RegisterSerializer):
    first_name = serializers.CharField(max_length=150, required=True)  # Make these required
    last_name = serializers.CharField(max_length=150, required=True)
    phone_number = serializers.CharField(max_length=20)
    role = serializers.ChoiceField(choices=User.ROLES)
    idNum = serializers.CharField(max_length=9, required=True)

    # Removed the manager field:
    # manager = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), allow_null=True, required=False)

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data['first_name'] = self.validated_data.get('first_name', '')
        data['last_name'] = self.validated_data.get('last_name', '')
        data['phone_number'] = self.validated_data.get('phone_number', '')
        data['role'] = self.validated_data.get('role', '')
        data['idNum'] = self.validated_data.get('idNum', '')

        # Removed the manager field:
        # data['manager'] = self.validated_data.get('manager', None)
        return data

    def save(self, request):
        user = super().save(request)
        user.phone_number = self.validated_data['phone_number']
        user.role = self.validated_data['role']
        user.first_name = self.validated_data['first_name']
        user.last_name = self.validated_data['last_name']
        user.idNum = self.validated_data['idNum']
        # Removed the manager field:
        # user.manager = self.validated_data.get('manager')
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'phone_number', 'role')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class NestedWorkItemSerializer(serializers.ModelSerializer):
    total_section_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = WorkItem
        fields = ['id', 'section', 'description', 'contract_amount', 'actual_amount', 'unit_cost', 'status',
                  'work_type', 'total_section_cost', 'status_display']


class WorkItemSerializer(serializers.ModelSerializer):
    total_section_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    work = serializers.PrimaryKeyRelatedField(queryset=Work.objects.all())  # This is the key change
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # work_number = serializers.CharField(source='work.work_number', read_only=True)

    class Meta:
        model = WorkItem
        fields = ['id', 'section', 'description', 'contract_amount', 'actual_amount', 'unit_cost', 'status',
                  'work_type', 'total_section_cost', 'work', 'status_display']


class WorkSerializer(serializers.ModelSerializer):
    items = NestedWorkItemSerializer(many=True, required=False)
    # items = WorkItemSerializer(many=True, required=False)  # Remove `read_only=True`
    average_score = serializers.FloatField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    contractor_name = serializers.CharField(source='contractor.username', read_only=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True)
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    phone_number = serializers.CharField(source='contractor.phone_number', read_only=True)
    classification_display = serializers.CharField(source='get_classification_display', read_only=True)

    class Meta:
        model = Work
        fields = '__all__'

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        work = Work.objects.create(**validated_data)
        for item_data in items_data:
            WorkItem.objects.create(work=work, **item_data)
        return work

    def update(self, instance, validated_data):
        # Handle nested items
        items_data = validated_data.pop('items', [])

        # Update the work instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Get existing items to track what should be deleted
        existing_items = {item.id: item for item in instance.items.all()}

        # Update or create items
        updated_items = []
        for item_data in items_data:
            item_id = item_data.get('id')
            if item_id and item_id in existing_items:
                # Update existing item
                item = existing_items.pop(item_id)
                for attr, value in item_data.items():
                    setattr(item, attr, value)
                item.save()
            else:
                # Create new item
                item = WorkItem.objects.create(work=instance, **item_data)
            updated_items.append(item)

        # Delete items that weren't included in the update
        for item in existing_items.values():
            item.delete()

        return instance


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = '__all__'


# class ContractorRatingSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ContractorRating
#         fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'  # Or specify the fields you want to expose
        # If you want to make work read only
        # extra_kwargs = {'work': {'read_only': True}}


class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user = serializers.PrimaryKeyRelatedField(read_only=True) # Add this back for the ID
    work = serializers.PrimaryKeyRelatedField(read_only=True)  # Add this line - crucial!

    class Meta:
        model = Comment
        fields = ['id', 'work', 'user', 'user_name', 'text', 'created_at']
        read_only_fields = ['user', 'created_at','work']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
