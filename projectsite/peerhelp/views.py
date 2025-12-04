from __future__ import annotations
from http.client import TOO_EARLY
import os
import random
from sqlite3 import paramstyle
import requests
from typing import Dict, List, Tuple

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
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
	Problem,
	Review,
	Solution,
	SolutionAttachment,
	User,
	UserProfile,
)
NAV_ITEMS = [
	{'id': 'dashboard', 'label': 'Dashboard', 'icon': 'home', 'url_name': 'dashboard'}, {'id': 'browse-problems', 'label': 'Browse Problems', 'icon': 'search', 'url_name': 'browse-problems'},
	{'id': 'post-problem', 'label': 'Post Problem', 'icon': 'help-circle', 'url_name': 'post-problem'}, {'id': 'map-view', 'label': 'In-Person Map', 'icon': 'map-pin', 'url_name': 'map-view'},
	{'id': 'ratings', 'label': 'Ratings', 'icon': 'star', 'url_name': 'ratings'},
]


def apply_in_person_preferences(problem: Problem) -> None:
	if problem.in_person_mode:
		problem.mode = 'in_person'
		return
	if problem.mode == 'in_person':
		problem.mode = 'online'
	problem.meeting_lat = problem.meeting_lng = None


def initials_from_name(name: str) -> str:
	parts = [part for part in name.split() if part]
	if not parts:
		return name[:2].upper()
	if len(parts) == 1:
		return parts[0][:2].ljust(2, parts[0][:1]).upper()
	return (parts[0][0] + parts[-1][0]).upper()


def ensure_profile(user) -> UserProfile:
	return UserProfile.objects.get_or_create(user=user)[0]


def display_name(user: User) -> str:
	return user.display_name or user.get_full_name() or user.username


def avatar_payload(profile: UserProfile, *, include_rating: bool = False) -> Dict[str, object]:
	name = display_name(profile.user)
	data = {
		'name': name,
		'avatar': profile.avatar.url if profile.avatar else '',
		'initials': initials_from_name(name),
	}
	if include_rating:
		data['rating'] = profile.rating
	return data


def stat_card(
	label: str,
	value,
	icon: str,
	variant: str,
	*,
	variant_key: str = 'variant',
	trend: Dict[str, str] | None = None,
	include_trend: bool = False,
) -> Dict[str, object]:
	card = {'label': label, 'value': value, 'icon': icon, variant_key: variant}
	if include_trend or trend is not None:
		card['trend'] = trend
	return card


def base_context(request: HttpRequest, *, current_page: str = '') -> Dict[str, object]:
	profile = ensure_profile(request.user) if request.user.is_authenticated else None
	name = display_name(profile.user) if profile else 'Guest'
	return {
		'menu_items': NAV_ITEMS,
		'current_page': current_page,
		'show_menu_button': True,
		'user_name': name,
		'user_first_name': name.split()[0] if name else '',
		'user_avatar': profile.avatar.url if profile and profile.avatar else '',
		'user_initials': initials_from_name(name) if profile else 'GU',
		'user_email': profile.user.email if profile else '',
		'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
	}


def render_page(request: HttpRequest, template: str, *, current_page: str = '', **extra) -> HttpResponse:
	return render(
		request,
		template,
		{**base_context(request, current_page=current_page), **extra},
	)


def flash_redirect(request: HttpRequest, level: str, message_text: str, url_name: str, *args, **kwargs) -> HttpResponse:
	getattr(messages, level)(request, message_text)
	return redirect(url_name, *args, **kwargs)


def guard_redirect(
	request: HttpRequest,
	url_name: str,
	*,
	checks: List[Tuple[str, str, bool]],
	url_kwargs: Dict[str, object] | None = None,
	url_args: Tuple[object, ...] = (),
) -> HttpResponse | None:
	for level, message_text, condition in checks:
		if condition:
			return flash_redirect(request, level, message_text, url_name, *url_args, **(url_kwargs or {}))
	return None


def serialize_tags(tag_string: str) -> List[str]:
	return [item.strip() for item in tag_string.split(',') if item.strip()]


def _serialize_meeting_thread(problem: Problem) -> Dict[str, object]:
	proposal, reply = (problem.solver_meeting_note or '').strip(), (problem.owner_meeting_reply or '').strip()
	return {
		'has_proposal': bool(proposal),
		'proposal': proposal,
		'proposal_time': f"{timesince(problem.solver_meeting_note_at)} ago" if problem.solver_meeting_note_at else '',
		'has_reply': bool(reply),
		'reply': reply,
		'reply_time': f"{timesince(problem.owner_meeting_reply_at)} ago" if problem.owner_meeting_reply_at else '',
		'pending_owner_reply': bool(proposal and not reply),
	}


PROBLEM_SIMPLE_FIELDS = ('id', 'slug', 'title', 'description', 'mode', 'in_person_mode', 'meeting_lat', 'meeting_lng', 'status', 'urgency', 'owner_id', 'current_solver_id')


def serialize_problem(problem: Problem) -> Dict[str, object]:
	payload = {field: getattr(problem, field) for field in PROBLEM_SIMPLE_FIELDS}
	owner_profile = ensure_profile(problem.owner)
	author_block = avatar_payload(owner_profile, include_rating=True)
	author_block['solved'] = owner_profile.user.solutions.filter(is_accepted=True).count()
	payload.update({
		'subject': problem.subject or 'General',
		'tags': serialize_tags(problem.tags) or ['General'],
		'mode_label': problem.get_mode_display(),
		'status_label': problem.get_status_display(),
		'time': f"{timesince(problem.created_at)} ago",
		'responses': problem.solutions.count(),
		'author': author_block,
		'attachments': [],
		'meeting_thread': _serialize_meeting_thread(problem),
	})
	return payload


def serialize_solution(solution: Solution) -> Dict[str, object]:
	author_profile = ensure_profile(solution.author)
	return {
		'id': solution.id,
		'content': solution.content,
		'accepted': solution.is_accepted,
		'time': f"{timesince(solution.created_at)} ago",
		'helpful': solution.reviews.count(),
		'author': avatar_payload(author_profile, include_rating=True),
	}


def solver_details(problem: Problem) -> Dict[str, object] | None:
	if not problem.current_solver:
		return None
	profile = ensure_profile(problem.current_solver)
	return {'id': problem.current_solver.id, **avatar_payload(profile, include_rating=True)}


def owner_solution_context(problem: Problem, owner: User) -> Tuple[Solution | None, Review | None, ReviewForm | None, bool, str]:
	solution = (
		Solution.objects.filter(problem=problem)
		.select_related('author')
		.order_by('-created_at')
		.first()
	)
	if not solution:
		return None, None, None, False, ''
	match_solver = solution.author_id == problem.current_solver_id
	review = Review.objects.filter(solution=solution, reviewer=owner).first() if match_solver else None
	form = ReviewForm(initial={'rating': 5}) if match_solver and not review and not solution.is_accepted else None
	return solution, review, form, match_solver, display_name(solution.author)


def serialize_solutions_for_user(solutions, user: User) -> List[Dict[str, object]]:
	return [
		{
			**serialize_solution(solution),
			'edit_url': reverse('solution-edit', args=[solution.id]) if (is_author := solution.author_id == user.id) else '',
			'delete_url': reverse('solution-delete', args=[solution.id]) if is_author else '',
			'can_edit': is_author,
			'can_delete': is_author,
		}
		for solution in solutions
	]


def solution_page_payload(
	problem: Problem,
	form: SolutionForm,
	*,
	current_page: str = 'browse-problems',
	attachments: List[Dict[str, str]] | None = None,
	guidelines: List[str] | None = None,
) -> Dict[str, object]:
	payload = {
		'current_page': current_page,
		'problem': serialize_problem(problem),
		'solution_form': form,
		'attachments': attachments or [],
	}
	if guidelines:
		payload['guidelines'] = guidelines
	return payload


def serialize_map_problem(problem: Problem) -> Dict[str, object]:
	data = serialize_problem(problem)
	data.update({
		'location': problem.location_label or 'On-campus location',
		'owner': data.pop('author'),
		'created_at': problem.created_at.isoformat(),
		'tags': data['tags'][:4],
		'detail_url': reverse('problem-detail', args=[problem.slug]),
	})
	return data


def meeting_thread_flags(problem: Problem, is_owner: bool, is_current_solver: bool) -> Tuple[bool, bool]:
	show_thread = bool(problem.solver_meeting_note and (is_owner or is_current_solver))
	owner_can_reply = bool(is_owner and show_thread and problem.mode == 'in_person' and not problem.owner_meeting_reply and problem.current_solver_id)
	return show_thread, owner_can_reply


def problem_status_flags(problem: Problem, user: User) -> Tuple[bool, bool, bool, bool, bool]:
	is_owner = problem.owner_id == user.id
	is_current_solver = problem.current_solver_id == user.id
	is_solved = problem.status == Problem.STATUS_SOLVED
	is_locked_by_other = bool(problem.current_solver_id and not is_current_solver)
	can_accept = not is_owner and not is_solved and (problem.current_solver_id in {None, user.id})
	return is_owner, is_current_solver, is_locked_by_other, is_solved, can_accept


def recent_owner_activity(user: User) -> List[Dict[str, object]]:
	return [
		{'title': p.title, 'time': f"{timesince(p.created_at)} ago", 'icon': 'helping-hand', 'variant': 'teal', 'url_name': 'problem-detail', 'slug': p.slug, 'meta': f"{p.solutions.count()} responses", 'badge': {'label': p.status.replace('_', ' ').title(), 'variant': 'teal'}}
		for p in Problem.objects.filter(owner=user).order_by('-created_at')[:5]
	]


def dashboard_stats(user: User) -> List[Dict[str, object]]:
	user_problems = Problem.objects.filter(owner=user)
	user_solutions = Solution.objects.filter(author=user)
	accepted = user_solutions.filter(is_accepted=True).count()
	avg_rating = Review.objects.filter(reviewee=user).aggregate(avg=Avg('rating'))['avg'] or 5.0
	return [
		stat_card('Open Problems', user_problems.filter(status=Problem.STATUS_OPEN).count(), 'map-pin', 'teal', trend={'label': 'Need action', 'icon': 'alert-circle'}, variant_key='icon_variant', include_trend=True),
		stat_card('Problems Posted', user_problems.count(), 'help-circle', 'emerald', trend={'label': 'All time', 'icon': 'activity'}, variant_key='icon_variant', include_trend=True),
		stat_card('Solutions Authored', user_solutions.count(), 'lightbulb', 'amber', trend={'label': f"{accepted} accepted", 'icon': 'check'}, variant_key='icon_variant', include_trend=True),
		stat_card('Average Rating', f"{avg_rating:.1f}", 'star', 'purple', variant_key='icon_variant', include_trend=True),
	]


def dashboard_quick_actions() -> List[Dict[str, str]]:
	return [
		{'label': 'Browse Problems', 'icon': 'search', 'variant': 'teal', 'url_name': 'browse-problems'},
		{'label': 'Post Problem', 'icon': 'help-circle', 'variant': 'emerald', 'url_name': 'post-problem'},
		{'label': 'Submit Solution', 'icon': 'pen-line', 'variant': 'amber', 'url_name': 'browse-problems'},
		{'label': 'View Ratings', 'icon': 'star', 'variant': 'purple', 'url_name': 'ratings'},
	]


def base_problem_queryset():
	return Problem.objects.exclude(status=Problem.STATUS_SOLVED).select_related('owner').order_by('-created_at')


def extract_problem_filters(request: HttpRequest) -> Dict[str, str]:
	return {
		'search': request.GET.get('query', '').strip(),
		'subject': request.GET.get('subject', 'All Categories'),
		'mode': request.GET.get('mode', 'Any'),
		'sort': request.GET.get('sort', 'recent'),
	}


def apply_problem_filters(queryset, filters: Dict[str, str]):
	filtered = queryset
	if search := filters['search']:
		filtered = filtered.filter(title__icontains=search)
	if (subject := filters['subject']) not in {'', 'All Categories'}:
		filtered = filtered.filter(subject__iexact=subject)
	if (mode_value := filters['mode'].replace('-', '_').lower()) in {'online', 'in_person'}:
		filtered = filtered.filter(mode=mode_value)
	if filters['sort'] == 'responses-desc':
		filtered = filtered.annotate(num_responses=Count('solutions')).order_by('-num_responses')
	return filtered


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
			profile = ensure_profile(user)
			profile.location_text = request.POST.get('university', '')
			profile.save(update_fields=['location_text'])
			login(request, user)
			return flash_redirect(request, 'success', 'Account created successfully. Welcome to Mentora!', 'dashboard')
		messages.error(request, 'Please correct the highlighted errors and try again.')

	return render_page(request, 'authentication/register.html', hide_navbar=True, hide_sidebar=True, register_form=form)


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

	return render_page(request, 'authentication/login.html', hide_navbar=True, hide_sidebar=True, login_form=form)


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
	if request.method != 'POST':
		return HttpResponseForbidden('Logout must be performed via POST.')
	logout(request)
	return redirect('login')


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
	return render_page(request, 'dashboard/index.html', current_page='dashboard', dashboard_alerts={'new_problems': Problem.objects.exclude(owner=request.user).count(), 'pending_solutions': Solution.objects.filter(problem__owner=request.user, is_accepted=False).count()}, stats_cards=dashboard_stats(request.user), quick_actions=dashboard_quick_actions(), recent_activity=recent_owner_activity(request.user))


@login_required
def problem_browse_view(request: HttpRequest) -> HttpResponse:
	filters = extract_problem_filters(request)
	category_options = ['All Categories'] + PROBLEM_CATEGORY_LABELS
	problems_qs = apply_problem_filters(base_problem_queryset(), filters)
	if filters['sort'] != 'responses-desc':
		filters['sort'] = 'recent'
	filters_open = (
		filters['search']
		or filters['subject'] not in {'', 'All Categories'}
		or filters['mode'] not in {'Any', ''}
		or filters['sort'] != 'recent'
	)

	paginator = Paginator(problems_qs, 5)
	page_number = request.GET.get('page') or 1
	page_obj = paginator.get_page(page_number)
	problems_payload = [serialize_problem(problem) for problem in page_obj]
	query_params = request.GET.copy(); query_params.pop('page', None); pagination_query = query_params.urlencode()

	return render_page(request, 'problems/browse.html', current_page='browse-problems', search_query=filters['search'], filter_subjects=category_options, selected_subject=filters['subject'], filter_modes=['Any', 'Online', 'In-Person'], selected_mode=filters['mode'], sort_options=[{'label': 'Most Recent', 'value': 'recent'}, {'label': 'Most Responses', 'value': 'responses-desc'}], selected_sort=filters['sort'], filters_open=filters_open, problems=problems_payload, page_obj=page_obj, paginator=paginator, pagination_query=pagination_query)


@login_required
def problem_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
	problem = get_object_or_404(Problem.objects.select_related('owner', 'current_solver'), slug=slug)
	solutions = problem.solutions.select_related('author').order_by('-created_at')
	(
		is_owner,
		is_current_solver,
		is_locked_by_other,
		is_solved,
		can_accept,
	) = problem_status_flags(problem, request.user)
	owner_ctx = owner_solution_context(problem, request.user) if is_owner else (None, None, None, False, '')
	(
		owner_solver_solution,
		owner_solver_review,
		owner_review_form,
		owner_solution_matches_solver,
		owner_solution_author_name,
	) = owner_ctx
	solution_payload = serialize_solutions_for_user(solutions, request.user)
	show_meeting_thread, owner_can_reply = meeting_thread_flags(problem, is_owner, is_current_solver)
	return render_page(request, 'problems/detail.html', current_page='browse-problems', problem=serialize_problem(problem), solutions=solution_payload, is_owner=is_owner, is_current_solver=is_current_solver, is_locked_by_other=is_locked_by_other, can_accept_problem=can_accept, is_problem_solved=is_solved, owner_solver_details=solver_details(problem), owner_solver_solution=owner_solver_solution, owner_solver_review=owner_solver_review, owner_review_form=owner_review_form, owner_solution_matches_solver=owner_solution_matches_solver, owner_solution_author_name=owner_solution_author_name, problem_edit_url=reverse('problem-edit', args=[problem.slug]) if is_owner else '', problem_delete_url=reverse('problem-delete', args=[problem.slug]) if is_owner else '', show_meeting_thread=show_meeting_thread, can_reply_meeting_thread=owner_can_reply)


@login_required
@require_POST
def problem_accept_view(request: HttpRequest, slug: str) -> HttpResponse:
	meeting_note = (request.POST.get('meeting_note') or '').strip()
	with transaction.atomic():
		problem = get_object_or_404(Problem.objects.select_for_update(), slug=slug)
		requires_meeting_note = problem.mode == 'in_person'
		if response := guard_redirect(
			request,
			'problem-detail',
			checks=[
				('info', 'This problem has already been solved.', problem.status == Problem.STATUS_SOLVED),
				('error', 'You cannot accept your own problem.', problem.owner_id == request.user.id),
				('error', 'Another solver is already working on this problem.', bool(problem.current_solver_id and problem.current_solver_id != request.user.id)),
				('error', 'Please propose a meeting time before accepting this in-person problem.', requires_meeting_note and not meeting_note),
			],
			url_kwargs={'slug': slug},
		):
			return response

		updated_fields: List[str] = []
		if problem.current_solver_id != request.user.id:
			problem.current_solver = request.user
			updated_fields.append('current_solver')
		if problem.status != Problem.STATUS_IN_PROGRESS:
			problem.status = Problem.STATUS_IN_PROGRESS
			updated_fields.append('status')
		if requires_meeting_note:
			problem.solver_meeting_note = meeting_note; problem.solver_meeting_note_at = timezone.now()
			problem.owner_meeting_reply = ''; problem.owner_meeting_reply_at = None
			updated_fields.extend(['solver_meeting_note', 'solver_meeting_note_at', 'owner_meeting_reply', 'owner_meeting_reply_at'])
		if updated_fields:
			problem.save(update_fields=updated_fields)
	return flash_redirect(request, 'success', 'Problem locked. The owner has received your meeting proposal.', 'problem-detail', slug=slug)


@login_required
@require_POST
def problem_release_view(request: HttpRequest, slug: str) -> HttpResponse:
	with transaction.atomic():
		problem = get_object_or_404(Problem.objects.select_for_update(), slug=slug)
		if response := guard_redirect(
			request,
			'problem-detail',
			checks=[
				('error', 'You are not the current solver for this problem.', problem.current_solver_id != request.user.id),
				('info', 'Solved problems cannot be released.', problem.status == Problem.STATUS_SOLVED),
			],
			url_kwargs={'slug': slug},
		):
			return response
		problem.current_solver = None; problem.status = Problem.STATUS_OPEN
		problem.solver_meeting_note = ''; problem.solver_meeting_note_at = None
		problem.owner_meeting_reply = ''; problem.owner_meeting_reply_at = None
		problem.save(
			update_fields=[
				'current_solver',
				'status',
				'solver_meeting_note',
				'solver_meeting_note_at',
				'owner_meeting_reply',
				'owner_meeting_reply_at',
			],
		)
	return flash_redirect(request, 'info', 'The problem lock has been released for other solvers.', 'problem-detail', slug=slug)


@login_required
@require_POST
def problem_meeting_reply_view(request: HttpRequest, slug: str) -> HttpResponse:
	reply_text = (request.POST.get('owner_reply') or '').strip()
	with transaction.atomic():
		problem = get_object_or_404(Problem.objects.select_for_update(), slug=slug)
		if problem.owner_id != request.user.id:
			return HttpResponseForbidden('Only the problem owner can reply to meeting proposals.')
		if response := guard_redirect(
			request,
			'problem-detail',
			checks=[
				('error', 'A solver must accept the problem before you can reply.', not problem.current_solver_id),
				('error', 'There is no meeting proposal to reply to yet.', not problem.solver_meeting_note),
				('error', 'Please provide a meeting response before submitting.', not reply_text),
			],
			url_kwargs={'slug': slug},
		):
			return response
		problem.owner_meeting_reply = reply_text; problem.owner_meeting_reply_at = timezone.now()
		problem.save(update_fields=['owner_meeting_reply', 'owner_meeting_reply_at'])
	return flash_redirect(request, 'success', 'Meeting reply sent to your solver.', 'problem-detail', slug=slug)


@login_required
def problem_submit_view(request: HttpRequest) -> HttpResponse: return _problem_form(request)


@login_required
def problem_edit_view(request: HttpRequest, slug: str) -> HttpResponse: return _problem_form(request, slug)


def _problem_form(request: HttpRequest, slug: str | None = None) -> HttpResponse:
	editing = slug is not None
	problem = get_object_or_404(Problem, slug=slug, owner=request.user) if editing else None
	form = ProblemForm(request.POST or None, instance=problem)
	if request.method == 'POST':
		if form.is_valid():
			saved = form.save(commit=False)
			apply_in_person_preferences(saved)
			if not editing:
				saved.owner = request.user
			saved.save()
			success_text = 'Problem updated.' if editing else 'Problem posted successfully.'
			if saved.in_person_mode and not (saved.meeting_lat and saved.meeting_lng):
				messages.success(request, success_text)
				info_text = 'Pick a campus meeting spot to complete the in-person setup.' if editing else 'Select a campus meeting spot to finish setting up your in-person problem.'
				return flash_redirect(request, 'info', info_text, 'pick_location', problem_id=saved.id)
			return flash_redirect(request, 'success', success_text, 'problem-detail', slug=saved.slug)
		messages.error(request, 'Please correct the errors below.' if editing else 'Please review the form and try again.')
	return render_page(request, 'problems/post.html', current_page='post-problem', problem_form=form, editing=editing, problem_obj=problem)


@login_required
def pick_location(request: HttpRequest, problem_id: int) -> HttpResponse:
	problem = get_object_or_404(Problem, pk=problem_id, owner=request.user)
	if request.method == 'POST':
		lat_raw = request.POST.get('meeting_lat')
		lng_raw = request.POST.get('meeting_lng')
		if not lat_raw or not lng_raw:
			messages.error(request, 'Please tap inside the campus boundary to choose a meeting point.')
		else:
			try:
				lat_value = float(lat_raw); lng_value = float(lng_raw)
			except ValueError:
				messages.error(request, 'Invalid coordinates provided. Please try again.')
			else:
				problem.meeting_lat, problem.meeting_lng = lat_value, lng_value
				problem.in_person_mode = True
				updated_fields = ['meeting_lat', 'meeting_lng', 'in_person_mode']
				if problem.mode != 'in_person':
					problem.mode = 'in_person'
					updated_fields.append('mode')
				problem.save(update_fields=updated_fields)
				return flash_redirect(request, 'success', 'Meeting location saved successfully.', 'problem-detail', slug=problem.slug)
	return render_page(request, 'problems/location_picker.html', current_page='post-problem', problem_detail_url=reverse('problem-detail', args=[problem.slug]), problem=problem, meeting_lat=problem.meeting_lat, meeting_lng=problem.meeting_lng)


@login_required
def problem_delete_view(request: HttpRequest, slug: str) -> HttpResponse:
	problem = get_object_or_404(Problem, slug=slug, owner=request.user)
	if request.method == 'POST':
		problem.delete()
		return flash_redirect(request, 'info', 'Problem removed.', 'browse-problems')
	return flash_redirect(request, 'warning', 'Please confirm deletion via POST request.', 'problem-detail', slug=slug)

@login_required
def solution_submit_view(request: HttpRequest, slug: str) -> HttpResponse:
	problem = get_object_or_404(Problem, slug=slug)
	if response := guard_redirect(
		request,
		'problem-detail',
		checks=[
			('error', 'You cannot submit a solution to your own problem.', problem.owner_id == request.user.id),
			('info', 'This problem is already solved.', problem.status == Problem.STATUS_SOLVED),
			('error', 'Please accept the problem before submitting a solution.', problem.current_solver_id != request.user.id),
		],
		url_kwargs={'slug': slug},
	):
		return response
	form = SolutionForm()
	if request.method == 'POST':
		form = SolutionForm(request.POST, request.FILES)
		if form.is_valid():
			with transaction.atomic():
				locked_problem = Problem.objects.select_for_update().get(pk=problem.pk)
				if response := guard_redirect(
					request,
					'problem-detail',
					checks=[('error', 'The lock for this problem is no longer assigned to you.', locked_problem.current_solver_id != request.user.id)],
					url_kwargs={'slug': locked_problem.slug},
				):
					return response
				solution = form.save(commit=False); solution.problem = locked_problem; solution.author = request.user; solution.save()
				for attachment in request.FILES.getlist('attachments'):
					SolutionAttachment.objects.create(solution=solution, file=attachment)
				fields_to_update: List[str] = []
				if locked_problem.current_solver_id != request.user.id:
					locked_problem.current_solver = request.user; fields_to_update.append('current_solver')
				if locked_problem.status != Problem.STATUS_IN_PROGRESS:
					locked_problem.status = Problem.STATUS_IN_PROGRESS; fields_to_update.append('status')
				if fields_to_update:
					locked_problem.save(update_fields=fields_to_update)
			return flash_redirect(request, 'success', 'Solution submitted successfully. Waiting for the problem owner to review it.', 'problem-detail', slug=problem.slug)
		messages.error(request, 'Unable to submit solution. Please review the form.')

	return render_page(request, 'problems/submit.html', **solution_page_payload(problem, form))


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
		return flash_redirect(request, 'error', 'This solution does not belong to the current solver.', 'problem-detail', slug=problem.slug)
	form = ReviewForm(request.POST)
	if not form.is_valid():
		return flash_redirect(request, 'error', 'Please provide a rating and short review before accepting the solution.', 'problem-detail', slug=problem.slug)
	with transaction.atomic():
		locked_solution = Solution.objects.select_for_update().select_related('problem').get(pk=solution.pk)
		locked_problem = Problem.objects.select_for_update().get(pk=problem.pk)
		locked_solution.is_accepted = True; locked_solution.save(update_fields=['is_accepted'])
		locked_problem.status = Problem.STATUS_SOLVED; locked_problem.current_solver = locked_solution.author
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
	return flash_redirect(request, 'success', 'Solution accepted and reviewer feedback recorded.', 'problem-detail', slug=problem.slug)


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
			return flash_redirect(request, 'success', 'Solution updated successfully.', 'problem-detail', slug=solution.problem.slug)
		messages.error(request, 'Unable to update the solution.')

	return render_page(request, 'problems/submit.html', **solution_page_payload(solution.problem, form, current_page='', guidelines=['Update your content below and resubmit.'], attachments=[{'name': attachment.file.name.split('/')[-1], 'type': attachment.file.name.split('.')[-1].upper()} for attachment in solution.attachments.all()]))


@login_required
def solution_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
	solution = get_object_or_404(Solution, pk=pk, author=request.user)
	problem_slug = solution.problem.slug
	if request.method == 'POST':
		solution.delete()
		return flash_redirect(request, 'info', 'Solution deleted.', 'problem-detail', slug=problem_slug)
	return flash_redirect(request, 'warning', 'Please confirm deletion via POST request.', 'problem-detail', slug=problem_slug)

@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
	profile = ensure_profile(request.user)
	if request.method == 'POST':
		profile.user.display_name = request.POST.get('name') or profile.user.display_name
		profile.skills = request.POST.get('major', profile.skills); profile.bio = request.POST.get('bio', profile.bio)
		profile.user.save(update_fields=['display_name']); profile.save(update_fields=['skills', 'bio'])
		return flash_redirect(request, 'success', 'Profile updated successfully.', 'user-profile')

	profile_stats = [
		stat_card('Students Helped', Review.objects.filter(reviewee=request.user).count(), 'users', 'emerald'),
		stat_card('Average Rating', profile.rating, 'star', 'amber'),
		stat_card('Badges Earned', request.user.badges.count(), 'shield', 'purple'),
	]
	profile_badges = [{'name': badge.badge.name, 'icon': '⚡', 'variant': 'teal', 'earned': True} for badge in request.user.badges.select_related('badge')]

	return render_page(request, 'profile/index.html', current_page='user-profile', profile={'name': display_name(profile.user), 'avatar': profile.avatar.url if profile.avatar else '', 'initials': initials_from_name(profile.user.username), 'major': profile.skills or 'Generalist', 'university': profile.location_text or 'Campus', 'joined': profile.user.date_joined.strftime('%B %Y'), 'bio': profile.bio, 'badge_summary': f"{len(profile_badges)} unlocked"}, profile_stats=profile_stats, profile_badges=profile_badges)


@login_required
def reviews_view(request: HttpRequest) -> HttpResponse:
	reviews_qs = (
		Review.objects
		.filter(reviewee=request.user, solution__author=request.user)
		.select_related('reviewer')
		.order_by('-created_at')
	)
	review_entries = [
		{'author': avatar_payload(reviewer_profile), 'rating': rev.rating, 'comment': rev.comment, 'helpful': random.randint(0, 12), 'time': f"{timesince(rev.created_at)} ago"}
		for rev in reviews_qs
		for reviewer_profile in [ensure_profile(rev.reviewer)]
	]
	avg_rating_all = reviews_qs.aggregate(avg=Avg('rating'))['avg'] or 5.0
	return render_page(request, 'reviews/index.html', current_page='ratings', average_rating=round(avg_rating_all, 1), total_reviews=len(review_entries), rating_distribution=[{'stars': stars, 'percentage': 20 * stars, 'count': sum(1 for rev in review_entries if rev['rating'] == stars)} for stars in range(5, 0, -1)], reviews=review_entries)


@login_required
def map_view(request: HttpRequest) -> HttpResponse:
	problems = (
		Problem.objects
		.filter(
			in_person_mode=True,
			meeting_lat__isnull=False,
			meeting_lng__isnull=False,
			status__in=[Problem.STATUS_OPEN, Problem.STATUS_IN_PROGRESS],
		)
		.select_related('owner')
		.order_by('-updated_at')
	)
	request_entries = [serialize_map_problem(problem) for problem in problems]

	return render_page(request, 'map/index.html', current_page='map-view', in_person_requests=request_entries)


@login_required
def verify_id_view(request: HttpRequest) -> HttpResponse:
	profile = ensure_profile(request.user)
	form = IDVerificationForm(instance=profile)
	if request.method == 'POST':
		form = IDVerificationForm(request.POST, request.FILES, instance=profile)
		if form.is_valid():
			form.save(); profile.id_status = UserProfile.ID_STATUS_PENDING
			profile.save(update_fields=['id_status'])
			return flash_redirect(request, 'success', 'ID uploaded successfully. Status set to pending verification.', 'verification')
		messages.error(request, 'Unable to upload ID. Please try again.')

	return render_page(request, 'profile/verification.html', current_page='verification', id_form=form, id_status=profile.id_status)


