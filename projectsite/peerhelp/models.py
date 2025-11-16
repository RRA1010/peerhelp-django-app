from django.db import models

# Create your models here.

class User(models.Model):
    name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    is_helper = models.BooleanField(default=False)
    rating = models.FloatField(default=0.0)
    total_credits = models.IntegerField(default=0)
    students_helped = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    credits = models.IntegerField(default=0)
    problems_solved = models.IntegerField(default=0)
    badges_count = models.IntegerField(default=0)
    bio = models.CharField(max_length=1000)
    location = models.CharField(max_length=100)
    phone = models.CharField(max_length=100)
    rating = models.FloatField(default=0)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return self.full_name


class Problem(models.Model):
    MODE = [
        ('online', 'Online'),
        ('in_person', 'In Person'),
    ]

    CATEGORIES = [
        ('general', 'General'),
        ('comp_studies', 'Computer Studies'),
        ('engineering', 'Engineering'),
        ('health_sci', 'Health Sciences'),
        ('business', 'Business And Management'),
        ('science', 'Science'),
        ('math', 'Mathematics'),
        ('education', 'Education'),
        ('humanities', 'Humanities'),
        ('arts_and_design', 'Arts and Design'),
        ('others', 'Others'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORIES, default="general")
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    help_mode = models.CharField(max_length=20, choices=MODE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    reward = models.IntegerField(default=0)

    def __str__(self):
        return self.title
    
class ProblemAttachment(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='problem_attachments/')


class Solution(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    text = models.TextField()
    solver = models.ForeignKey(User, on_delete=models.CASCADE)
    ai_summary = models.TextField(blank=True)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Solution from {self.solver.name} for {self.problem.title}"


class SolutionAttachment(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='solution_attachments/')


class AIHint(models.Model):
    problem_description = models.TextField()
    created_at = models.DateField(auto_now_add=True)


class AISummary(models.Model):
    solution = models.TextField()
    generated_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Review(models.Model):
    rating = models.FloatField(default=0.0)
    review = models.TextField()


class Portfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    problems = models.ForeignKey(Problem, on_delete=models.CASCADE)
    solutions = models.ForeignKey(Solution, on_delete=models.CASCADE)
    ratings_received = models.FloatField(default=0.0)
    reviews = models.ForeignKey(Review, on_delete=models.CASCADE)


class Badge(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=100)
    students_required = models.IntegerField(default=0)


class UserBadge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    awarded_at = models.DateTimeField(auto_now_add=True)


class Location(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.CharField(max_length=100)
    radius_km = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)
