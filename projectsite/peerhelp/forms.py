from django.forms import ModelForm
from django import forms
from peerhelp.models import (User, UserProfile,
                             Problem, ProblemAttachment,
                             Solution, SolutionAttachment,
                             Review, Portfolio, Badge,
                             UserBadge, Location
                             ) # to consider if all models should be imported

class UserForm(ModelForm):
    class Meta:
        model = User
        fields = "__all__"

class ProblemForm(ModelForm):
    class Meta:
        model = Problem
        fields = "__all__"

class SolutionForm(ModelForm):
    class Meta:
        model = Solution
        fields = "__all__"

class ReviewForm(ModelForm):
    class Meta:
        model = Review
        fields = "__all__"

class PortfolioForm(ModelForm):
    class Meta:
        model = Portfolio
        fields = "__all__"