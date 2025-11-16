from django.contrib import admin
from peerhelp.models import (User, UserProfile, 
                             Problem, ProblemAttachment, 
                             Solution, SolutionAttachment, 
                             AIHint, AISummary, 
                             Review, Portfolio, Badge, UserBadge, Location)

# Register your models here.

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'is_helper', 'rating','total_credits','students_helped','created_at', 'updated_at')
    search_fields = ('name', 'email')
    list_filter = ('is_helper',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name','credits','problems_solved',
                    'badges_count','bio','location','phone','rating','verified')
    search_fields = ('full_name', 'location', 'phone')
    list_filter = ('verified',)

@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'help_mode', 'created_at', 'updated_at')
    search_fields = ('title', 'description')
    list_filter = ('category', 'help_mode')

@admin.register(ProblemAttachment)
class ProblemAttachmentAdmin(admin.ModelAdmin):
    list_display = ('problem', 'file', 'created_at', 'updated_at')
    search_fields = ('problem__title',)

@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ('problem', 'solver', 'is_accepted', 'created_at', 'updated_at')
    search_fields = ('problem__title', 'solver__username')
    list_filter = ('is_accepted',)

@admin.register(SolutionAttachment)
class SolutionAttatchmentAdmin(admin.ModelAdmin):
    list_display = ('solution', 'file', 'created_at', 'updated_at')

admin.site.register(AIHint)
admin.site.register(AISummary)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('rating', 'review', 'created_at', 'updated_at')
    search_fields = ('review',)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('user', 'problems', 'solutions', 'ratings_received', 'created_at', 'updated_at')
    search_fields = ('user__username',)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'students_required', 'created_at', 'updated_at')
    search_fields = ('name',)

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'awarded_at', 'created_at', 'updated_at')
    search_fields = ('user__username', 'badge__name')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('latitude', 'longitude', 'address', 'radius_km','is_active','created_at', 'updated_at')
    search_fields = ('address',)