from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.validators import EmailValidator


class User(AbstractUser):
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    ROLES = (
        ('CONTRACTOR', 'Contractor'),
        ('CONTRACTOR_VIEWER', 'Contractor_Viewer'),
        ('MANAGER', 'Manager'),
        ('GENERAL_ENGINEER', 'General Engineer'),
        ('PAYMENT_ADMIN', 'Payment Admin'),
        ('SUPER_ADMIN', 'Super Admin'),
    )
    email = models.EmailField(unique=True, validators=[EmailValidator()])  # No _ here!

    phone_number = models.CharField(max_length=20)
    role = models.CharField(max_length=20, choices=ROLES)
    # Override first_name and last_name to make them required:
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    idNum = models.CharField(max_length=150)

    # manager = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.username  # Or self.email if you use email as the primary identifier


# class ContractorRating(models.Model):
#     contractor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings')
#     quality_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
#     time_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
#     cost_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
#     work = models.ForeignKey('Work', on_delete=models.CASCADE)
#     rated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
#     created_at = models.DateTimeField(auto_now_add=True)


class Facility(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    facility_number = models.IntegerField(unique=True)


class Work(models.Model):
    CLASSIFICATION_CHOICES = (
        ('FAULT', 'תקלה'),
        ('UPGRADE', 'שדרוג'),
        ('WORK', 'תחזוקה'),
        ('GENERAL', 'כללי'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'ממתין'),
        ('IN_PROGRESS', 'בביצוע'),
        ('WAITING_PAYMENT', 'ממתין לתשלום'),
        ('PAID', 'שולם'),
    )

    work_number = models.CharField(max_length=50, unique=True)
    project = models.CharField(max_length=50)  # Changed to CharField

    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES)
    start_date = models.DateTimeField()
    due_end_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    contractor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contracted_works')
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name='managed_works')
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    location_name = models.CharField(max_length=200)
    remarks = models.TextField(blank=True)

    # ratings
    quality_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], null=True, blank=True)
    time_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], null=True, blank=True)
    cost_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def average_score(self):
        scores = [self.quality_score, self.time_score, self.cost_score]
        valid_scores = [score for score in scores if score is not None]
        if valid_scores:
            return round(sum(valid_scores) / len(valid_scores), 1)
        return 0


class WorkItem(models.Model):
    # STATUS_CHOICES = (
    #     ('PENDING', 'Pending'),
    #     ('IN_PROGRESS', 'In Progress'),
    #     ('QUALITY_CONTROL', 'Quality Control'),
    #     ('COMPLETED', 'Completed'),
    # )

    STATUS_CHOICES = (
        ('PENDING', 'ממתין'),
        ('IN_PROGRESS', 'בביצוע'),
        ('COMPLETED_BY_CONTRACTOR', 'בוצע על ידי הקבלן'),
        ('QUALITY_CONTROL', 'בקרת איכות'),
        ('COMPLETED', 'בוצע'),
        ('WAITING_PAYMENT', 'ממתין לתשלום'),
        ('PAID', 'שולם'),
    )
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='items')
    section = models.IntegerField()
    description = models.TextField()
    contract_amount = models.DecimalField(max_digits=10, decimal_places=2)
    actual_amount = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    work_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_section_cost(self):
        return self.actual_amount * self.unit_cost

    def __str__(self):
        return str(self.id) + '   ' + self.work_type  # Or self.email if you use email as the primary identifier


class Payment(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='payments')  # ForeignKey to Work
    invoice_number = models.CharField(max_length=50, blank=True, null=True)
    payment_account_details = models.TextField(blank=True, null=True)  # Details of the account
    payment_date = models.DateField()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_manager = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='made_payments', null=True,
                                        blank=True)  # User who made the payment
    approval_manager = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='approved_payments', null=True,
                                         blank=True)
    payment_terms = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Payment for Work: {self.work.work_number}, Amount: {self.amount_paid}"


class Comment(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
