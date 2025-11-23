from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify


class User(AbstractUser):
    display_name = models.CharField(max_length=150, blank=True)

    def __str__(self) -> str:
        return self.display_name or self.username


class UserProfile(models.Model):
    ID_STATUS_PENDING = 'pending'
    ID_STATUS_VERIFIED = 'verified'
    ID_STATUS_REJECTED = 'rejected'
    ID_STATUS_CHOICES = [
        (ID_STATUS_PENDING, 'Pending'),
        (ID_STATUS_VERIFIED, 'Verified'),
        (ID_STATUS_REJECTED, 'Rejected'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    skills = models.CharField(max_length=255, blank=True)
    credits = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('5.00'))
    id_document = models.FileField(upload_to='ids/', blank=True, null=True)
    id_status = models.CharField(max_length=20, choices=ID_STATUS_CHOICES, default=ID_STATUS_PENDING)
    location_text = models.CharField(max_length=255, blank=True)
    id_document_hash = models.CharField(max_length=64, blank=True, null=True, unique=True)

    def __str__(self) -> str:
        return f"Profile for {self.user}"


class Badge(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, help_text='Reference to static icon class or filename')
    criteria = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return self.name


class Problem(models.Model):
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_SOLVED = 'solved'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_SOLVED, 'Solved'),
    ]

    SESSION_MODE_CHOICES = [
        ('online', 'Online'),
        ('in_person', 'In Person'),
    ]

    URGENCY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='problems')
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    subject = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    tags = models.CharField(max_length=200, blank=True)
    mode = models.CharField(max_length=20, choices=SESSION_MODE_CHOICES, default='online')
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')
    credits_offered = models.PositiveIntegerField(default=10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    location_label = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    current_solver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_problems',
    )

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or 'problem'
            candidate = base_slug
            suffix = 1
            while Problem.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                suffix += 1
                candidate = f"{base_slug}-{suffix}"
            self.slug = candidate
        super().save(*args, **kwargs)


class Solution(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='solutions')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solutions')
    content = models.TextField()
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Solution by {self.author} for {self.problem}"


class SolutionAttachment(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='solution_attachments/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Attachment for {self.solution}"


class AISummary(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='ai_summaries')
    summary_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Summary for {self.problem}"


class Review(models.Model):
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_reviews')
    reviewee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_reviews')
    solution = models.ForeignKey(Solution, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews')
    rating = models.PositiveSmallIntegerField(default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Review for {self.reviewee} ({self.rating}★)"


class Portfolio(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='portfolio_items')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    featured = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.title} ({self.user})"


class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='earned_by')
    awarded_at = models.DateTimeField(auto_now_add=True)
    progress = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))

    class Meta:
        unique_together = ('user', 'badge')

    def __str__(self) -> str:
        return f"{self.user} - {self.badge}"


class Location(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='locations', null=True, blank=True)
    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='locations')
    title = models.CharField(max_length=200)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
