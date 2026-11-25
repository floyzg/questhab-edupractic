"""Регистрация моделей в встроенной админ-панели Django."""
from django.contrib import admin

from .models import (
    AgeRating,
    Booking,
    BookingExtraOption,
    ExtraOption,
    GameResult,
    Genre,
    QuestRoom,
    Review,
    SessionSchedule,
    TariffSlot,
    Team,
    UserProfile,
)


class BookingExtraOptionInline(admin.TabularInline):
    model = BookingExtraOption
    extra = 1


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email', 'phone')


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(AgeRating)
class AgeRatingAdmin(admin.ModelAdmin):
    list_display = ('code', 'min_age', 'description')


@admin.register(QuestRoom)
class QuestRoomAdmin(admin.ModelAdmin):
    list_display = ('title', 'genre', 'age_rating', 'fear_level', 'difficulty', 'base_price', 'extra_player_price', 'is_active')
    list_filter = ('genre', 'age_rating', 'fear_level', 'difficulty', 'is_active')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(TariffSlot)
class TariffSlotAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time', 'price_multiplier')


@admin.register(SessionSchedule)
class SessionScheduleAdmin(admin.ModelAdmin):
    list_display = ('quest', 'date', 'start_time', 'end_time', 'tariff_slot', 'is_blocked')
    list_filter = ('quest', 'date', 'is_blocked')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'captain', 'contact_phone', 'default_players_count', 'created_at')
    search_fields = ('name', 'captain__username', 'contact_phone')


@admin.register(ExtraOption)
class ExtraOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'option_type', 'price', 'is_active')
    list_filter = ('option_type', 'is_active')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_code', 'quest', 'team', 'booking_date', 'start_time', 'players_count', 'total_price', 'status')
    list_filter = ('status', 'booking_date', 'quest')
    search_fields = ('booking_code', 'team__name', 'captain__username')
    inlines = [BookingExtraOptionInline]
    readonly_fields = ('booking_code', 'created_at', 'updated_at')


@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ('team', 'quest', 'completion_minutes', 'hints_used', 'score', 'played_at')
    list_filter = ('quest', 'played_at')
    search_fields = ('team__name', 'quest__title')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('quest', 'author', 'rating', 'created_at', 'is_published')
    list_filter = ('rating', 'is_published', 'quest')
    search_fields = ('comment', 'author__username', 'quest__title')
