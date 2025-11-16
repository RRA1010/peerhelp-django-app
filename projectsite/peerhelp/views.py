from django.shortcuts import render
from django.views.generic.list import ListView
from django.views.generic.detail import CreateView, UpdateView, DeleteView

# import models and forms here
from peerhelp.models import Problem, Solution, UserProfile
from peerhelp.forms import ProblemForm, SolutionForm

# import for query and time
from django.db.models import Q
from django.utils import timezone

import os
import requests # We may use this later for API calls e.g. OCR, HuggingFace or otherss.


# Create your views here.
