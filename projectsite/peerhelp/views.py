from __future__ import annotations

from http.client import TOO_EARLY
import os
import random
from sqlite3 import paramstyle
import requests
from typing import Dict, List
import hashlib

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timesince import timesince
from django.views.decorators.http import require_POST

from .forms import (
	IDVerificationForm,
	PROBLEM_CATEGORY_LABELS,
	ProblemForm,
	ReviewForm,
	SolutionForm,
	UserLoginForm,
	UserRegisterForm,
)
from .models import (
	AISummary,
	Problem,
	Review,
	Solution,
	SolutionAttachment,
	User,
	UserProfile,
)


def _initials_from_name(name: str) -> str:
	parts = [part for part in name.split() if part]
	if not parts:
		return name[:2].upper()
	if len(parts) == 1:
		return parts[0][:2].upper()
	return f"{parts[0][0]}{parts[1][0]}".upper()


def _ensure_profile(user) -> UserProfile:
	profile, _ = UserProfile.objects.get_or_create(user=user)
	return profile


def _navigation_items() -> List[Dict[str, str]]:
	return [
		{'id': 'dashboard', 'label': 'Dashboard', 'icon': 'home', 'url_name': 'dashboard'},
		{'id': 'browse-problems', 'label': 'Browse Problems', 'icon': 'search', 'url_name': 'browse-problems'},
		{'id': 'post-problem', 'label': 'Post Problem', 'icon': 'help-circle', 'url_name': 'post-problem'},
		{'id': 'map-view', 'label': 'In-Person Map', 'icon': 'map-pin', 'url_name': 'map-view'},
		{'id': 'ai-tools', 'label': 'AI Assistant', 'icon': 'sparkles', 'url_name': 'ai-tools'},
		{'id': 'ratings', 'label': 'Ratings', 'icon': 'star', 'url_name': 'ratings'},
	]


def _base_context(request: HttpRequest, *, current_page: str = '') -> Dict[str, object]:
	profile = _ensure_profile(request.user) if request.user.is_authenticated else None
	if profile:
		display_name = profile.user.display_name or profile.user.get_full_name() or profile.user.username
		first_name = (display_name.split()[0]) if display_name else ''
		credits = profile.credits
		avatar_url = profile.avatar.url if profile.avatar else ''
		initials = _initials_from_name(display_name)
		email = profile.user.email
	else:
		display_name = 'Guest'
		first_name = 'Guest'
		credits = 0
		avatar_url = ''
		initials = 'GU'
		email = ''

	progress_percent = min(100, credits % 100 or 25)
	badge_tier = 'Gold Helper' if credits >= 1000 else 'Silver Guide'
	return {
		'menu_items': _navigation_items(),
		'current_page': current_page,
		'show_menu_button': True,
		'user_badge_tier': badge_tier,
		'user_progress_percent': progress_percent,
		'user_progress_note': f"{max(0, 100 - progress_percent)}% to next tier",
		'user_name': display_name,
		'user_first_name': first_name,
		'user_avatar': avatar_url,
		'user_initials': initials,
		'user_email': email,
		'credits': credits,
	}


def _serialize_tags(tag_string: str) -> List[str]:
	return [item.strip() for item in tag_string.split(',') if item.strip()]


def _serialize_problem(problem: Problem) -> Dict[str, object]:
	owner_profile = _ensure_profile(problem.owner)
	owner_name = owner_profile.user.display_name or owner_profile.user.get_full_name() or owner_profile.user.username
	tags = _serialize_tags(problem.tags)
	return {
		'id': problem.id,
		'slug': problem.slug,
		'title': problem.title,
		'subject': problem.subject or 'General',
		'description': problem.description,
		'tags': tags or ['General'],
		'mode': problem.mode,
		'mode_label': problem.get_mode_display(),
		'status_label': problem.get_status_display(),
		'urgency': problem.urgency,
		'status': problem.status,
		'owner_id': problem.owner_id,
		'current_solver_id': problem.current_solver_id,
		'time': f"{timesince(problem.created_at)} ago",
		'responses': problem.solutions.count(),
		'credits': problem.credits_offered,
		'author': {
			'name': owner_name,
			'avatar': owner_profile.avatar.url if owner_profile.avatar else '',
			'initials': _initials_from_name(owner_name),
			'credits': owner_profile.credits,
			'solved': owner_profile.user.solutions.filter(is_accepted=True).count(),
			'rating': owner_profile.rating,
			'is_verified': owner_profile.id_status == UserProfile.ID_STATUS_VERIFIED,
		},
		'attachments': [],
	}


def _serialize_solution(solution: Solution) -> Dict[str, object]:
	author_profile = _ensure_profile(solution.author)
	author_name = author_profile.user.display_name or author_profile.user.get_full_name() or author_profile.user.username
	return {
		'id': solution.id,
		'content': solution.content,
		'accepted': solution.is_accepted,
		'time': f"{timesince(solution.created_at)} ago",
		'helpful': solution.reviews.count(),
		'author': {
			'name': author_name,
			'avatar': author_profile.avatar.url if author_profile.avatar else '',
			'initials': _initials_from_name(author_name),
			'credits': author_profile.credits,
			'rating': author_profile.rating,
		},
	}


def _generate_summary_placeholder(text: str) -> str:
	clean_text = (text or '').strip()
	if not clean_text:
		return 'Mentora AI summary placeholder. Add your solution to generate a concise recap.'
	excerpt = clean_text[:280]
	ellipsis = '…' if len(clean_text) > 280 else ''
	return f"Summary Preview: {excerpt}{ellipsis}"


def register_view(request: HttpRequest) -> HttpResponse:
	if request.user.is_authenticated:
		return redirect('dashboard')

	form = UserRegisterForm()
	if request.method == 'POST':
		form_data = {
			'username': request.POST.get('email'),
			'email': request.POST.get('email'),
			'display_name': request.POST.get('name'),
			'password1': request.POST.get('password'),
			'password2': request.POST.get('confirm_password'),
		}
		form = UserRegisterForm(form_data)
		if form.is_valid():
			user = form.save()
			profile = _ensure_profile(user)
			profile.location_text = request.POST.get('university', '')
			profile.save(update_fields=['location_text'])
			login(request, user, backend='django.contrib.auth.backends.ModelBackend')
			messages.success(request, 'Account created successfully. Welcome to Mentora!')
			return redirect('dashboard')
		messages.error(request, 'Please correct the highlighted errors and try again.')

	context = {
		'hide_navbar': True,
		'hide_sidebar': True,
		'register_form': form,
	}
	return render(request, 'authentication/register.html', context)


def login_view(request: HttpRequest) -> HttpResponse:
	if request.user.is_authenticated:
		return redirect('dashboard')

	form = UserLoginForm()
	if request.method == 'POST':
		username_or_email = request.POST.get('email')
		password = request.POST.get('password')
		user = authenticate(request, username=username_or_email, password=password)
		if not user:
			try:
				alt_user = User.objects.get(email__iexact=username_or_email)
			except User.DoesNotExist:
				alt_user = None
			if alt_user:
				user = authenticate(request, username=alt_user.username, password=password)
		if user:
			login(request, user)
			return redirect('dashboard')
		messages.error(request, 'Invalid credentials. Please try again.')

	context = {
		'hide_navbar': True,
		'hide_sidebar': True,
		'login_form': form,
	}
	return render(request, 'authentication/login.html', context)


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
	if request.method != 'POST':
		return HttpResponseForbidden('Logout must be performed via POST.')
	logout(request)
	return redirect('login')


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
	profile = _ensure_profile(request.user)
	problems = Problem.objects.filter(owner=request.user).order_by('-created_at')[:5]
	recent_activity = [
		{
			'title': p.title,
			'time': f"{timesince(p.created_at)} ago",
			'icon': 'helping-hand',
			'variant': 'teal',
			'url_name': 'problem-detail',
			'slug': p.slug,
			'meta': f"{p.solutions.count()} responses",
			'badge': {
				'label': p.status.replace('_', ' ').title(),
				'variant': 'teal',
			},
		}
		for p in problems
	]

	avg_rating = Review.objects.filter(reviewee=request.user).aggregate(avg=Avg('rating'))['avg'] or 5.0
	stats_cards = [
		{
			'label': 'Available Credits',
			'value': profile.credits,
			'icon': 'award',
			'icon_variant': 'teal',
			'trend': {'label': '+12 this week', 'icon': 'arrow-up-right'},
		},
		{
			'label': 'Problems Posted',
			'value': Problem.objects.filter(owner=request.user).count(),
			'icon': 'help-circle',
			'icon_variant': 'emerald',
			'trend': {'label': 'Active', 'icon': 'activity'},
		},
		{
			'label': 'Solutions Authored',
			'value': Solution.objects.filter(author=request.user).count(),
			'icon': 'lightbulb',
			'icon_variant': 'amber',
			'trend': None,
		},
		{
			'label': 'Average Rating',
			'value': f"{avg_rating:.1f}",
			'icon': 'star',
			'icon_variant': 'purple',
			'trend': None,
		},
	]

	quick_actions = [
		{'label': 'Browse Problems', 'icon': 'search', 'variant': 'teal', 'url_name': 'browse-problems'},
		{'label': 'Post Problem', 'icon': 'help-circle', 'variant': 'emerald', 'url_name': 'post-problem'},
		{'label': 'Submit Solution', 'icon': 'pen-line', 'variant': 'amber', 'url_name': 'browse-problems'},
		{'label': 'AI Tools', 'icon': 'sparkles', 'variant': 'purple', 'url_name': 'ai-tools'},
	]

	display_name = profile.user.display_name or profile.user.first_name or profile.user.username
	first_name = (display_name.split()[0]) if display_name else ''

	context = {
		**_base_context(request, current_page='dashboard'),
		'user_name': display_name,
		'user_first_name': first_name,
		'dashboard_alerts': {
			'new_problems': Problem.objects.exclude(owner=request.user).count(),
			'pending_solutions': Solution.objects.filter(problem__owner=request.user, is_accepted=False).count(),
		},
		'stats_cards': stats_cards,
		'quick_actions': quick_actions,
		'recent_activity': recent_activity,
	}
	return render(request, 'dashboard/index.html', context)


@login_required
def problem_browse_view(request: HttpRequest) -> HttpResponse:
	problems_qs = (
		Problem.objects.exclude(status=Problem.STATUS_SOLVED)
		.select_related('owner')
		.order_by('-created_at')
	)
	search_query = request.GET.get('query', '').strip()
	if search_query:
		problems_qs = problems_qs.filter(title__icontains=search_query)

	category_options = ['All Categories'] + PROBLEM_CATEGORY_LABELS
	subject_filter = request.GET.get('subject', 'All Categories')
	if subject_filter not in {'', 'All Categories'}:
		problems_qs = problems_qs.filter(subject__iexact=subject_filter)

	mode_param = request.GET.get('mode', 'Any')
	mode_filter_value = mode_param.replace('-', '_').lower()
	if mode_filter_value in {'online', 'in_person'}:
		problems_qs = problems_qs.filter(mode=mode_filter_value)

	sort_option = request.GET.get('sort', 'recent')
	if sort_option == 'credits-desc':
		problems_qs = problems_qs.order_by('-credits_offered')
	elif sort_option == 'responses-desc':
		problems_qs = problems_qs.annotate(num_responses=Count('solutions')).order_by('-num_responses')

	filters_open = (
		subject_filter not in {'', 'All Categories'}
		or mode_param not in {'Any', ''}
		or sort_option != 'recent'
	)

	paginator = Paginator(problems_qs, 5)
	page_number = request.GET.get('page') or 1
	page_obj = paginator.get_page(page_number)
	problems_payload = [_serialize_problem(problem) for problem in page_obj]
	query_params = request.GET.copy()
	query_params.pop('page', None)
	pagination_query = query_params.urlencode()

	context = {
		**_base_context(request, current_page='browse-problems'),
		'search_query': search_query,
		'filter_subjects': category_options,
		'selected_subject': subject_filter,
		'filter_modes': ['Any', 'Online', 'In-Person'],
		'selected_mode': mode_param,
		'sort_options': [
			{'label': 'Most Recent', 'value': 'recent'},
			{'label': 'Highest Credits', 'value': 'credits-desc'},
			{'label': 'Most Responses', 'value': 'responses-desc'},
		],
		'selected_sort': sort_option,
		'filters_open': filters_open,
		'problems': problems_payload,
		'page_obj': page_obj,
		'paginator': paginator,
		'pagination_query': pagination_query,
	}
	return render(request, 'problems/browse.html', context)


@login_required
def problem_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
	problem = get_object_or_404(Problem.objects.select_related('owner', 'current_solver'), slug=slug)
	solutions = problem.solutions.select_related('author').order_by('-created_at')
	is_owner = problem.owner_id == request.user.id
	is_current_solver = problem.current_solver_id == request.user.id
	is_locked_by_other = problem.current_solver_id is not None and not is_current_solver
	is_solved = problem.status == Problem.STATUS_SOLVED
	can_accept = (
		not is_owner
		and not is_solved
		and (problem.current_solver_id in {None, request.user.id})
	)
	solver_details = None
	owner_solver_solution = None
	owner_solver_review = None
	owner_review_form = None
	owner_solution_matches_solver = False
	owner_solution_author_name = ''
	if problem.current_solver:
		solver_profile = _ensure_profile(problem.current_solver)
		solver_name = solver_profile.user.display_name or solver_profile.user.get_full_name() or solver_profile.user.username
		solver_details = {
			'id': problem.current_solver.id,
			'name': solver_name,
			'avatar': solver_profile.avatar.url if solver_profile.avatar else '',
			'initials': _initials_from_name(solver_name),
			'credits': solver_profile.credits,
			'rating': solver_profile.rating,
		}
	if is_owner:
		owner_solver_solution = (
			Solution.objects
			.filter(problem=problem)
			.select_related('author')
			.order_by('-created_at')
			.first()
		)
		if owner_solver_solution:
			owner_solution_author_name = (
				owner_solver_solution.author.display_name
				or owner_solver_solution.author.get_full_name()
				or owner_solver_solution.author.username
			)
			owner_solution_matches_solver = owner_solver_solution.author_id == problem.current_solver_id
			if owner_solution_matches_solver:
				owner_solver_review = Review.objects.filter(solution=owner_solver_solution, reviewer=request.user).first()
				if not owner_solver_review and not owner_solver_solution.is_accepted:
					owner_review_form = ReviewForm(initial={'rating': 5})
	solution_payload = []
	for solution in solutions:
		solution_data = _serialize_solution(solution)
		can_modify = solution.author_id == request.user.id
		solution_data.update({
			'edit_url': reverse('solution-edit', args=[solution.id]) if can_modify else '',
			'delete_url': reverse('solution-delete', args=[solution.id]) if can_modify else '',
			'can_edit': can_modify,
			'can_delete': can_modify,
		})
		solution_payload.append(solution_data)
	context = {
		**_base_context(request, current_page='browse-problems'),
		'problem': _serialize_problem(problem),
		'solutions': solution_payload,
		'is_owner': is_owner,
		'is_current_solver': is_current_solver,
		'is_locked_by_other': is_locked_by_other,
		'can_accept_problem': can_accept,
		'is_problem_solved': is_solved,
		'owner_solver_details': solver_details,
		'owner_solver_solution': owner_solver_solution,
		'owner_solver_review': owner_solver_review,
		'owner_review_form': owner_review_form,
		'owner_solution_matches_solver': owner_solution_matches_solver,
		'owner_solution_author_name': owner_solution_author_name,
		'problem_edit_url': reverse('problem-edit', args=[problem.slug]) if is_owner else '',
		'problem_delete_url': reverse('problem-delete', args=[problem.slug]) if is_owner else '',
		'is_user_verified': _ensure_profile(request.user).id_status == UserProfile.ID_STATUS_VERIFIED,
	}
	return render(request, 'problems/detail.html', context)


@login_required
@require_POST
def problem_accept_view(request: HttpRequest, slug: str) -> HttpResponse:
	with transaction.atomic():
		problem = get_object_or_404(Problem.objects.select_for_update(), slug=slug)
		if problem.status == Problem.STATUS_SOLVED:
			messages.info(request, 'This problem has already been solved.')
			return redirect('problem-detail', slug=slug)
		solver_profile = _ensure_profile(request.user)
		if solver_profile.id_status != UserProfile.ID_STATUS_VERIFIED:
			messages.error(request, 'You must verify your ID before accepting problems.')
			return redirect('problem-detail', slug=slug)
		if problem.owner_id == request.user.id:
			messages.error(request, 'You cannot accept your own problem.')
			return redirect('problem-detail', slug=slug)
		if problem.current_solver_id and problem.current_solver_id != request.user.id:
			messages.error(request, 'Another solver is already working on this problem.')
			return redirect('problem-detail', slug=slug)

		updated_fields: List[str] = []
		if problem.current_solver_id != request.user.id:
			problem.current_solver = request.user
			updated_fields.append('current_solver')
		if problem.status != Problem.STATUS_IN_PROGRESS:
			problem.status = Problem.STATUS_IN_PROGRESS
			updated_fields.append('status')
		if updated_fields:
			problem.save(update_fields=updated_fields)
	messages.success(request, 'Problem locked. You can now work on your solution.')
	return redirect('problem-detail', slug=slug)


@login_required
@require_POST
def problem_release_view(request: HttpRequest, slug: str) -> HttpResponse:
	with transaction.atomic():
		problem = get_object_or_404(Problem.objects.select_for_update(), slug=slug)
		if problem.current_solver_id != request.user.id:
			messages.error(request, 'You are not the current solver for this problem.')
			return redirect('problem-detail', slug=slug)
		if problem.status == Problem.STATUS_SOLVED:
			messages.info(request, 'Solved problems cannot be released.')
			return redirect('problem-detail', slug=slug)
		problem.current_solver = None
		problem.status = Problem.STATUS_OPEN
		problem.save(update_fields=['current_solver', 'status'])
	messages.info(request, 'The problem lock has been released for other solvers.')
	return redirect('problem-detail', slug=slug)


@login_required
def problem_submit_view(request: HttpRequest) -> HttpResponse:
	form = ProblemForm()
	if request.method == 'POST':
		form = ProblemForm(request.POST)
		if form.is_valid():
			problem = form.save(commit=False)
			problem.owner = request.user
			problem.credits_offered = 10
			problem.save()
			messages.success(request, 'Problem posted successfully.')
			return redirect('problem-detail', slug=problem.slug)
		messages.error(request, 'Please review the form and try again.')

	context = {
		**_base_context(request, current_page='post-problem'),
		'problem_form': form,
		'editing': False,
	}
	return render(request, 'problems/post.html', context)


@login_required
def problem_edit_view(request: HttpRequest, slug: str) -> HttpResponse:
	problem = get_object_or_404(Problem, slug=slug, owner=request.user)
	form = ProblemForm(instance=problem)
	if request.method == 'POST':
		form = ProblemForm(request.POST, instance=problem)
		if form.is_valid():
			updated_problem = form.save(commit=False)
			updated_problem.credits_offered = 10
			updated_problem.save()
			messages.success(request, 'Problem updated.')
			return redirect('problem-detail', slug=problem.slug)
		messages.error(request, 'Please correct the errors below.')

	context = {
		**_base_context(request, current_page='post-problem'),
		'problem_form': form,
		'editing': True,
	}
	return render(request, 'problems/post.html', context)


@login_required
def problem_delete_view(request: HttpRequest, slug: str) -> HttpResponse:
	problem = get_object_or_404(Problem, slug=slug, owner=request.user)
	if request.method == 'POST':
		problem.delete()
		messages.info(request, 'Problem removed.')
		return redirect('browse-problems')
	messages.warning(request, 'Please confirm deletion via POST request.')
	return redirect('problem-detail', slug=slug)


@login_required
def solution_submit_view(request: HttpRequest, slug: str) -> HttpResponse:
	problem = get_object_or_404(Problem, slug=slug)
	if problem.owner_id == request.user.id:
		messages.error(request, 'You cannot submit a solution to your own problem.')
		return redirect('problem-detail', slug=slug)
	if problem.status == Problem.STATUS_SOLVED:
		messages.info(request, 'This problem is already solved.')
		return redirect('problem-detail', slug=slug)
	if problem.current_solver_id != request.user.id:
		messages.error(request, 'Please accept the problem before submitting a solution.')
		return redirect('problem-detail', slug=slug)
	form = SolutionForm()
	if request.method == 'POST':
		form = SolutionForm(request.POST, request.FILES)
		if form.is_valid():
			with transaction.atomic():
				locked_problem = Problem.objects.select_for_update().get(pk=problem.pk)
				if locked_problem.current_solver_id != request.user.id:
					messages.error(request, 'The lock for this problem is no longer assigned to you.')
					return redirect('problem-detail', slug=locked_problem.slug)
				solution = form.save(commit=False)
				solution.problem = locked_problem
				solution.author = request.user
				solution.save()
				for attachment in request.FILES.getlist('attachments'):
					SolutionAttachment.objects.create(solution=solution, file=attachment)
				AISummary.objects.create(problem=locked_problem, summary_text=_generate_summary_placeholder(solution.content))
				fields_to_update: List[str] = []
				if locked_problem.current_solver_id != request.user.id:
					locked_problem.current_solver = request.user
					fields_to_update.append('current_solver')
				if locked_problem.status != Problem.STATUS_IN_PROGRESS:
					locked_problem.status = Problem.STATUS_IN_PROGRESS
					fields_to_update.append('status')
				if fields_to_update:
					locked_problem.save(update_fields=fields_to_update)
			messages.success(request, 'Solution submitted successfully. Waiting for the problem owner to review it.')
			return redirect('problem-detail', slug=problem.slug)
		messages.error(request, 'Unable to submit solution. Please review the form.')

	context = {
		**_base_context(request, current_page='browse-problems'),
		'problem': _serialize_problem(problem),
		'solution_form': form,
		'guidelines': [
			'State your assumptions before crunching numbers.',
			'Highlight intermediate steps so peers can follow along.',
			'Attach visuals or screenshots when possible.',
		],
		'attachments': [],
	}
	return render(request, 'problems/submit.html', context)


@login_required
@require_POST
def solution_accept_view(request: HttpRequest, pk: int) -> HttpResponse:
	solution = get_object_or_404(
		Solution.objects.select_related('problem__owner', 'author'),
		pk=pk,
	)
	problem = solution.problem
	if problem.owner_id != request.user.id:
		return HttpResponseForbidden('Only the problem owner can accept a solution.')
	if problem.current_solver_id != solution.author_id:
		messages.error(request, 'This solution does not belong to the current solver.')
		return redirect('problem-detail', slug=problem.slug)
	form = ReviewForm(request.POST)
	if not form.is_valid():
		messages.error(request, 'Please provide a rating and short review before accepting the solution.')
		return redirect('problem-detail', slug=problem.slug)
	with transaction.atomic():
		locked_solution = Solution.objects.select_for_update().select_related('problem').get(pk=solution.pk)
		locked_problem = Problem.objects.select_for_update().get(pk=problem.pk)
		locked_solution.is_accepted = True
		locked_solution.save(update_fields=['is_accepted'])
		locked_problem.status = Problem.STATUS_SOLVED
		locked_problem.current_solver = locked_solution.author
		locked_problem.save(update_fields=['status', 'current_solver'])
		review, _ = Review.objects.update_or_create(
			reviewer=request.user,
			solution=locked_solution,
			defaults={
				'reviewee': locked_solution.author,
				'rating': form.cleaned_data['rating'],
				'comment': form.cleaned_data['comment'],
			},
		)
	messages.success(request, 'Solution accepted and reviewer feedback recorded.')
	return redirect('problem-detail', slug=problem.slug)


@login_required
def solution_edit_view(request: HttpRequest, pk: int) -> HttpResponse:
	solution = get_object_or_404(Solution, pk=pk, author=request.user)
	form = SolutionForm(instance=solution)
	if request.method == 'POST':
		form = SolutionForm(request.POST, request.FILES, instance=solution)
		if form.is_valid():
			solution = form.save()
			for attachment in request.FILES.getlist('attachments'):
				SolutionAttachment.objects.create(solution=solution, file=attachment)
			AISummary.objects.create(problem=solution.problem, summary_text=_generate_summary_placeholder(solution.content))
			messages.success(request, 'Solution updated successfully.')
			return redirect('problem-detail', slug=solution.problem.slug)
		messages.error(request, 'Unable to update the solution.')

	context = {
		**_base_context(request),
		'problem': _serialize_problem(solution.problem),
		'solution_form': form,
		'guidelines': ['Update your content below and resubmit.'],
		'attachments': [
			{'name': attachment.file.name.split('/')[-1], 'type': attachment.file.name.split('.')[-1].upper()}
			for attachment in solution.attachments.all()
		],
	}
	return render(request, 'problems/submit.html', context)


@login_required
def solution_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
	solution = get_object_or_404(Solution, pk=pk, author=request.user)
	problem_slug = solution.problem.slug
	if request.method == 'POST':
		solution.delete()
		messages.info(request, 'Solution deleted.')
	else:
		messages.warning(request, 'Please confirm deletion via POST request.')
	return redirect('problem-detail', slug=problem_slug)


@login_required
def ai_tools_view(request: HttpRequest) -> HttpResponse:
	context = {
		**_base_context(request, current_page='ai-tools'),
		'ai_header': {
			'title': 'AI Summarizer',
			'subtitle': 'Generate a concise recap of your solution for sharing later.',
			'badge': 'Preview',
		},
		'summary_guidelines': [
			'Focus on the core challenge, the strategy you used, and the outcome.',
			'Write in first-person to highlight your contribution.',
			'Keep it under 3 sentences so it is portfolio-ready.',
		],
		'summary_placeholder': _generate_summary_placeholder('Your summary will appear here once you paste your solution into the text area.'),
	}
	return render(request, 'tools/ai.html', context)


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
	profile = _ensure_profile(request.user)
	if request.method == 'POST':
		profile.user.display_name = request.POST.get('name') or profile.user.display_name
		profile.skills = request.POST.get('major', profile.skills)
		profile.bio = request.POST.get('bio', profile.bio)
		profile.user.save(update_fields=['display_name'])
		profile.save(update_fields=['skills', 'bio'])
		messages.success(request, 'Profile updated successfully.')
		return redirect('user-profile')

	profile_stats = [
		{'label': 'Total Credits', 'value': profile.credits, 'icon': 'award', 'variant': 'teal'},
		{'label': 'Students Helped', 'value': Review.objects.filter(reviewee=request.user).count(), 'icon': 'users', 'variant': 'emerald'},
		{'label': 'Average Rating', 'value': profile.rating, 'icon': 'star', 'variant': 'amber'},
		{'label': 'Badges Earned', 'value': request.user.badges.count(), 'icon': 'shield', 'variant': 'purple'},
	]

	profile_badges = [
		{
			'name': badge.badge.name,
			'icon': '⚡',
			'variant': 'teal',
			'earned': True,
		}
		for badge in request.user.badges.select_related('badge')
	]

	context = {
		**_base_context(request, current_page='user-profile'),
		'profile': {
			'name': profile.user.display_name or profile.user.get_full_name() or profile.user.username,
			'avatar': profile.avatar.url if profile.avatar else '',
			'initials': _initials_from_name(profile.user.username),
			'major': profile.skills or 'Generalist',
			'university': profile.location_text or 'Campus',
			'joined': profile.user.date_joined.strftime('%B %Y'),
			'bio': profile.bio,
			'badge_summary': f"{len(profile_badges)} unlocked",
			'is_verified': profile.id_status == UserProfile.ID_STATUS_VERIFIED,
		},
		'profile_stats': profile_stats,
		'profile_badges': profile_badges,
	}
	return render(request, 'profile/index.html', context)


@login_required
def reviews_view(request: HttpRequest) -> HttpResponse:
	reviews_qs = (
		Review.objects
		.filter(reviewee=request.user, solution__author=request.user)
		.select_related('reviewer')
		.order_by('-created_at')
	)
	review_entries = []
	for rev in reviews_qs:
		reviewer_profile = _ensure_profile(rev.reviewer)
		review_entries.append(
			{
				'author': {
					'name': rev.reviewer.display_name or rev.reviewer.get_full_name() or rev.reviewer.username,
					'avatar': reviewer_profile.avatar.url if reviewer_profile.avatar else '',
					'initials': _initials_from_name(rev.reviewer.username),
				},
				'rating': rev.rating,
				'comment': rev.comment,
				'helpful': random.randint(0, 12),
				'time': f"{timesince(rev.created_at)} ago",
			}
		)
	avg_rating_all = reviews_qs.aggregate(avg=Avg('rating'))['avg'] or 5.0
	context = {
		**_base_context(request, current_page='ratings'),
		'average_rating': round(avg_rating_all, 1),
		'total_reviews': len(review_entries),
		'rating_distribution': [
			{'stars': stars, 'percentage': 20 * stars, 'count': sum(1 for rev in review_entries if rev['rating'] == stars)}
			for stars in range(5, 0, -1)
		],
		'reviews': review_entries,
	}
	return render(request, 'reviews/index.html', context)


@login_required
def map_view(request: HttpRequest) -> HttpResponse:
	problems = list(Problem.objects.filter(mode='in_person').select_related('owner')[:12])
	marker_variants = ['teal', 'emerald', 'purple', 'amber']
	map_markers = []
	in_person_requests = []
	for idx, problem in enumerate(problems):
		map_markers.append(
			{
				'id': str(problem.id),
				'variant': marker_variants[idx % len(marker_variants)],
				'top': 25 + (idx * 11) % 50,
				'left': 30 + (idx * 17) % 40,
			}
		)
		in_person_requests.append(
			{
				'id': str(problem.id),
				'title': problem.title,
				'subject': problem.subject or 'General',
				'location': problem.location_label or 'On-campus location',
				'distance': f"{random.uniform(0.2, 1.8):.1f} miles",
				'credits': problem.credits_offered,
				'tags': _serialize_tags(problem.tags)[:3],
			}
		)

	context = {
		**_base_context(request, current_page='map-view'),
		'map_markers': map_markers,
		'in_person_requests': in_person_requests,
	}
	return render(request, 'map/index.html', context)


@login_required
def verify_id_view(request: HttpRequest) -> HttpResponse:
	profile = _ensure_profile(request.user)
	form = IDVerificationForm(instance=profile)

	if request.method == 'POST' and profile.id_status == UserProfile.ID_STATUS_VERIFIED:
		messages.info(request, 'Your ID is already verified.')
		return redirect('verification')

	if request.method == 'POST':
		form = IDVerificationForm(request.POST, request.FILES, instance=profile)
		if form.is_valid():
			form.save()
			
			api_key = os.getenv("OCRSPACE_API_KEY")
			uploaded_file = request.FILES.get('id_document')
	
			if uploaded_file and api_key:
				uploaded_file.seek(0)
				file_hash = hashlib.sha256(uploaded_file.read()).hexdigest()
				existing = UserProfile.objects.filter(id_document_hash=file_hash).exclude(user=request.user).first()
				if existing:
					messages.error(request, 'This ID has already been used by another user.')
					return redirect('verification')
				try:
					uploaded_file.seek(0)
					response = requests.post('https://api.ocr.space/parse/image', files={'file': (uploaded_file.name, uploaded_file.read(), uploaded_file.content_type)}, data={'apikey': api_key,}, timeout=30)
					response.raise_for_status()
					result = response.json()
     
					extracted_text = ""
					if result.get("ParsedResults"):
						extracted_text = result["ParsedResults"][0].get("ParsedText", "")

					user_name = request.user.display_name or request.user.get_full_name()
					name_parts = user_name.lower().split()
					lowered_text = extracted_text.lower()

					has_psu = "palawan state" in lowered_text or "psu" in lowered_text
					has_name = any(part in lowered_text for part in name_parts if len(part) >= 2)
	
					if has_psu and has_name:
						profile.id_status = UserProfile.ID_STATUS_VERIFIED
						profile.id_document_hash = file_hash
						messages.success(request, 'ID verified successfully.')
					else:
						profile.id_status = UserProfile.ID_STATUS_REJECTED
						messages.error(request, 'ID verification failed.')
				except requests.exceptions.RequestException as e:
					profile.id_status = UserProfile.ID_STATUS_PENDING
					messages.warning(request, 'ID uploaded but verification service is currently not available. Status set to pending for manual review.')
			else:
				profile.id_status = UserProfile.ID_STATUS_PENDING
    
			profile.save(update_fields=['id_status', 'id_document_hash'])
			return redirect('verification')
		messages.error(request, 'Unable to upload ID. Please try again.')
  
	context	= {
		**_base_context(request, current_page='verification'),
		'id_form': form,
		'id_status': profile.id_status,
	}
 
	return render(request, 'profile/verification.html', context)
       

