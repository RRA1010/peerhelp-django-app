from django.contrib import admin
from peerhelp.models import User, UserProfile, Problem, ProblemAttachment, Solution, SolutionAttachment, AIHint, AISummary, Review, Portfolio, Badge, UserBadge, Location
# Register your models here.

admin.site.register(User)
admin.site.register(UserProfile)
admin.site.register(Problem)
admin.site.register(ProblemAttachment)
admin.site.register(Solution)
admin.site.register(SolutionAttachment)
admin.site.register(AIHint)
admin.site.register(AISummary)
admin.site.register(Review)
admin.site.register(Portfolio)
admin.site.register(Badge)
admin.site.register(UserBadge)
admin.site.register(Location)