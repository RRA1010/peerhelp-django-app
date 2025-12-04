"""
URL configuration for projectsite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.contrib import admin


from peerhelp import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('activity/', views.dashboard_view, name='activity'),
    path('login/', views.login_view, name='login'),
    path('accounts/login/', views.login_view),
    path('register/', views.register_view, name='register'),
    path('accounts/signup/', views.register_view),
    path('logout/', views.logout_view, name='logout'),
    path('accounts/logout/', views.logout_view),
    path('accounts/profile/', views.profile_view),
    path('problems/', views.problem_browse_view, name='browse-problems'),
    path('problems/new/', views.problem_submit_view, name='post-problem'),
    path('problems/<slug:slug>/', views.problem_detail_view, name='problem-detail'),
    path('problems/<slug:slug>/accept/', views.problem_accept_view, name='problem-accept'),
    path('problems/<slug:slug>/release/', views.problem_release_view, name='problem-release'),
    path('problems/<slug:slug>/meeting-reply/', views.problem_meeting_reply_view, name='problem-meeting-reply'),
    path('problems/<slug:slug>/edit/', views.problem_edit_view, name='problem-edit'),
    path('problems/<slug:slug>/delete/', views.problem_delete_view, name='problem-delete'),
    path('problems/<slug:slug>/submit-solution/', views.solution_submit_view, name='submit-solution'),
    path('problems/<int:problem_id>/pick-location/', views.pick_location, name='pick_location'),
    path('solutions/<int:pk>/accept/', views.solution_accept_view, name='solution-accept'),
    path('solutions/<int:pk>/edit/', views.solution_edit_view, name='solution-edit'),
    path('solutions/<int:pk>/delete/', views.solution_delete_view, name='solution-delete'),
    path('profile/', views.profile_view, name='user-profile'),
    path('reviews/', views.reviews_view, name='ratings'),
    path('map/', views.map_view, name='map-view'),
    path('verify-id/', views.verify_id_view, name='verification'),
    path('accounts/', include('allauth.urls')),
    path('admin/', admin.site.urls),
]

