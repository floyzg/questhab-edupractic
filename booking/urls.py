"""Маршруты приложения booking (именованные URL для {% url %})."""
from django.urls import path

from . import views

app_name = 'booking'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('about/', views.about_view, name='about'),

    # Каталог и CRUD квестов
    path('quests/', views.quest_list_view, name='quest_list'),
    path('quests/create/', views.quest_create_view, name='quest_create'),
    path('quests/<slug:slug>/', views.quest_detail_view, name='quest_detail'),
    path('quests/<slug:slug>/edit/', views.quest_update_view, name='quest_update'),
    path('quests/<slug:slug>/delete/', views.quest_delete_view, name='quest_delete'),
    path('quests/<slug:slug>/book/', views.booking_create_view, name='booking_create'),

    # CRUD отзывов
    path('reviews/<int:pk>/edit/', views.review_update_view, name='review_update'),
    path('reviews/<int:pk>/delete/', views.review_delete_view, name='review_delete'),

    # JSON API (fetch)
    path('api/quests/<slug:slug>/price-preview/', views.api_booking_price_preview, name='api_price_preview'),
    path('api/quests/<slug:slug>/slots/', views.api_quest_slots, name='api_quest_slots'),

    # CRUD бронирований и экспорт
    path('bookings/<int:pk>/', views.booking_detail_view, name='booking_detail'),
    path('bookings/<int:pk>/edit/', views.booking_update_view, name='booking_update'),
    path('bookings/<int:pk>/cancel/', views.booking_delete_view, name='booking_delete'),
    path('bookings/<int:pk>/print/', views.booking_print_view, name='booking_print'),
    path('bookings/<int:booking_pk>/result/', views.result_create_view, name='result_create'),
    path('bookings/export/csv/', views.booking_export_csv_view, name='booking_export_csv'),

    # Расписание актёра-аниматора
    path('actor/schedule/', views.actor_schedule_view, name='actor_schedule'),

    # CRUD команд
    path('teams/', views.team_list_view, name='team_list'),
    path('teams/create/', views.team_create_view, name='team_create'),
    path('teams/<int:pk>/edit/', views.team_update_view, name='team_update'),
    path('teams/<int:pk>/delete/', views.team_delete_view, name='team_delete'),

    # Таблица рекордов и аналитика
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('analytics/', views.analytics_view, name='analytics'),

    # Аутентификация и профиль
    path('accounts/login/', views.CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('accounts/password-change/done/', views.CustomPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('profile/', views.profile_view, name='profile'),
]
