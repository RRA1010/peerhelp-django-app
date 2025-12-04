from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Problem, Review, Solution, User, UserProfile


PROBLEM_CATEGORY_LABELS = [
    'General',
    'Sports',
    'Missing Item',
    'Found Item',
    'Arts and Humanities',
    'Business and Economics',
    'Engineering and Technology',
    'Health and Medical Sciences',
    'Natural Sciences',
    'Social and Behavioral Sciences',
    'Education',
    'Communication and Media',
    'Law and Legal Studies',
]

PROBLEM_CATEGORY_CHOICES = [('', 'Select a category')] + [
    (label, label) for label in PROBLEM_CATEGORY_LABELS
]


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class UserRegisterForm(UserCreationForm):
    display_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'display_name', 'password1', 'password2')


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'autofocus': True}))


class ProblemForm(forms.ModelForm):
    subject = forms.ChoiceField(
        choices=PROBLEM_CATEGORY_CHOICES,
        label='Category',
        widget=forms.Select(attrs={'class': 'form-select select-pill text-capitalize'}),
    )
    in_person_mode = forms.BooleanField(
        required=False,
        label='In-Person Mode',
        widget=forms.CheckboxInput(attrs={
            'class': 'd-none',
            'data-in-person-flag': 'true',
            'aria-hidden': 'true',
        }),
    )

    class Meta:
        model = Problem
        fields = (
            'title',
            'subject',
            'description',
            'tags',
            'mode',
            'in_person_mode',
            'urgency',
            'location_label',
        )
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control input-control', 'placeholder': 'Need help with dynamic programming'}),
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'form-control input-control', 'placeholder': 'Describe what you tried so far...'}),
            'tags': forms.TextInput(attrs={'class': 'form-control input-control', 'placeholder': 'python, debugging'}),
            'mode': forms.Select(attrs={'class': 'form-select select-pill text-capitalize', 'data-mode-select': 'true'}),
            'urgency': forms.Select(attrs={'class': 'form-select select-pill text-capitalize'}),
            'location_label': forms.TextInput(attrs={'class': 'form-control input-control', 'placeholder': 'Library study room / Zoom link'}),
        }


class SolutionForm(forms.ModelForm):
    attachments = forms.FileField(
        widget=MultiFileInput(attrs={'multiple': True, 'class': 'form-control'}),
        required=False,
        help_text='Optional supporting files.'
    )

    class Meta:
        model = Solution
        fields = ('content',)
        widgets = {
            'content': forms.Textarea(attrs={'rows': 6, 'class': 'form-control solution-input', 'id': 'solutionInput', 'placeholder': 'Write the summary of what happened here...'}),
        }


class ReviewForm(forms.ModelForm):
    rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.HiddenInput(attrs={'data-rating-value': ''}),
        label='Rating',
    )

    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Share feedback', 'class': 'form-control'}),
        }


class IDVerificationForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('id_document',)
        widgets = {
            'id_document': forms.FileInput(attrs={'accept': 'image/*,.pdf'})
        }
        help_texts = {
            'id_document': 'Upload a clear image or PDF of your ID. Review remains pending until processed.'
        }
