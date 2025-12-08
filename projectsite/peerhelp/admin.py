from django.contrib import admin
from django.utils.html import format_html

from .models import Problem, Review, Solution, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ['user', 'id_status', 'credits', 'rating', 'view_id_document']
	list_filter = ['id_status']
	search_fields = ['user__username', 'user__email', 'user__display_name']
	readonly_fields = ['id_document_preview']

	def view_id_document(self, obj):
		if obj.id_document:
			return format_html('<a href="{}" target="_blank">View ID</a>', obj.id_document.url)
		return "No document"
	view_id_document.short_description = "ID Document"

	def id_document_preview(self, obj):
		if obj.id_document:
			return format_html('<img src="{}" style="max-width: 400px; max-height: 300px;" />', obj.id_document.url)
		return "No document uploaded"
	id_document_preview.short_description = "ID Preview"


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
	list_display = ['title', 'owner', 'status', 'credits_offered', 'created_at']
	list_filter = ['status', 'mode', 'urgency']
	search_fields = ['title', 'description']


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
	list_display = ['problem', 'author', 'is_accepted', 'created_at']
	list_filter = ['is_accepted']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
	list_display = ['reviewer', 'reviewee', 'rating', 'created_at']
	list_filter = ['rating']
