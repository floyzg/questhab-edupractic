"""Представления (views) приложения QuestHub (Вариант 14)."""
import logging
from datetime import date, datetime, time
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeDoneView, PasswordChangeView
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_GET

from .forms import (
    BookingForm,
    GameResultForm,
    ProfileUpdateForm,
    QuestRoomForm,
    ReviewForm,
    TeamForm,
    UserRegistrationForm,
)
from .models import (
    AgeRating,
    Booking,
    BookingExtraOption,
    ExtraOption,
    GameResult,
    Genre,
    QuestRoom,
    Review,
    TariffSlot,
    Team,
    UserProfile,
)
from .services import (
    build_bookings_csv_response,
    build_daily_slots_for_quest,
    calculate_booking_price,
    check_slot_availability,
    create_booking_atomic,
    send_booking_notification,
    update_booking_atomic,
)

logger = logging.getLogger('booking')


def _is_staff_or_operator(user) -> bool:
    """Проверяет, является ли пользователь оператором, администратором или staff."""
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.role in (UserProfile.ROLE_OPERATOR, UserProfile.ROLE_ADMIN))


def _is_actor_or_staff(user) -> bool:
    """Проверяет, является ли пользователь актёром, оператором или администратором."""
    if not user.is_authenticated:
        return False
    if _is_staff_or_operator(user):
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.role == UserProfile.ROLE_ACTOR)


def _ensure_booking_access(user, booking: Booking) -> None:
    """Защита от IDOR: доступ только владельцу брони или оператору/администратору."""
    if booking.captain_id != user.id and not _is_staff_or_operator(user):
        logger.warning(
            'Попытка несанкционированного доступа к брони %s пользователем %s.',
            booking.booking_code,
            user.username,
        )
        raise PermissionDenied('У вас нет прав для просмотра или изменения этого бронирования.')


def _ensure_team_access(user, team: Team) -> None:
    """Защита от IDOR: доступ только капитану команды или администратору."""
    if team.captain_id != user.id and not _is_staff_or_operator(user):
        raise PermissionDenied('У вас нет прав для работы с чужой командой.')


def _ensure_review_access(user, review: Review) -> None:
    """Защита от IDOR: редактировать/удалять отзыв может автор или оператор/админ."""
    if review.author_id != user.id and not _is_staff_or_operator(user):
        raise PermissionDenied('У вас нет прав для изменения или удаления чужого отзыва.')


# ---------------------------------------------------------------------------
# Основные публичные страницы
# ---------------------------------------------------------------------------

def home_view(request: HttpRequest) -> HttpResponse:
    """Главная страница проекта."""
    featured_quests = (
        QuestRoom.objects.filter(is_active=True)
        .select_related('genre', 'age_rating')
        .order_by('-created_at')[:6]
    )
    tariffs = TariffSlot.objects.all()
    top_results = (
        GameResult.objects.select_related('quest', 'team')
        .order_by('-score', 'completion_minutes')[:5]
    )
    stats = {
        'quests_count': QuestRoom.objects.filter(is_active=True).count(),
        'bookings_count': Booking.objects.exclude(status=Booking.STATUS_CANCELLED).count(),
        'records_count': GameResult.objects.count(),
    }
    return render(
        request,
        'booking/home.html',
        {
            'featured_quests': featured_quests,
            'tariffs': tariffs,
            'top_results': top_results,
            'stats': stats,
        },
    )


def about_view(request: HttpRequest) -> HttpResponse:
    """Статическая страница правил клуба, тарифов и технических перерывов."""
    tariffs = TariffSlot.objects.all()
    extras = ExtraOption.objects.filter(is_active=True)
    return render(
        request,
        'booking/about.html',
        {
            'tariffs': tariffs,
            'extras': extras,
            'break_minutes': getattr(settings, 'TECH_BREAK_MINUTES', 30),
        },
    )


def quest_list_view(request: HttpRequest) -> HttpResponse:
    """Каталог квестов: поиск, 4 фильтра, сортировка по 4 полям, пагинация по 20."""
    qs = QuestRoom.objects.filter(is_active=True).select_related('genre', 'age_rating')

    q = request.GET.get('q', '').strip()
    genre_slug = request.GET.get('genre', '').strip()
    age_code = request.GET.get('age_rating', '').strip()
    fear_level = request.GET.get('fear_level', '').strip()
    difficulty = request.GET.get('difficulty', '').strip()
    sort = request.GET.get('sort', 'title').strip()

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if genre_slug:
        qs = qs.filter(genre__slug=genre_slug)
    if age_code:
        qs = qs.filter(age_rating__code=age_code)
    if fear_level.isdigit():
        qs = qs.filter(fear_level=int(fear_level))
    if difficulty.isdigit():
        qs = qs.filter(difficulty=int(difficulty))

    sort_map = {
        'title': 'title',
        'price_asc': 'base_price',
        'price_desc': '-base_price',
        'fear_desc': '-fear_level',
        'difficulty_asc': 'difficulty',
    }
    qs = qs.order_by(sort_map.get(sort, 'title'))

    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop('page', None)
    query_string = params.urlencode()

    return render(
        request,
        'booking/quest_list.html',
        {
            'page_obj': page_obj,
            'genres': Genre.objects.all(),
            'age_ratings': AgeRating.objects.all(),
            'q': q,
            'selected_genre': genre_slug,
            'selected_age': age_code,
            'selected_fear': fear_level,
            'selected_difficulty': difficulty,
            'selected_sort': sort,
            'query_string': query_string,
            'is_staff_or_operator': _is_staff_or_operator(request.user),
        },
    )


def quest_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Детальная страница квеста, сетка сеансов и отзывы."""
    quest = get_object_or_404(
        QuestRoom.objects.select_related('genre', 'age_rating'),
        slug=slug,
    )
    selected_date_str = request.GET.get('date', '').strip()
    try:
        selected_date = date.fromisoformat(selected_date_str) if selected_date_str else date.today()
    except ValueError:
        selected_date = date.today()

    slots = build_daily_slots_for_quest(quest, selected_date)
    reviews = quest.reviews.filter(is_published=True).select_related('author')
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']

    review_form = ReviewForm()
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('booking:login')
        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            rev = review_form.save(commit=False)
            rev.quest = quest
            rev.author = request.user
            rev.save()
            messages.success(request, 'Спасибо! Ваш отзыв опубликован.')
            return redirect('booking:quest_detail', slug=quest.slug)

    return render(
        request,
        'booking/quest_detail.html',
        {
            'quest': quest,
            'selected_date': selected_date,
            'slots': slots,
            'reviews': reviews,
            'avg_rating': avg_rating,
            'review_form': review_form,
            'is_staff_or_operator': _is_staff_or_operator(request.user),
        },
    )


# ---------------------------------------------------------------------------
# CRUD отзывов
# ---------------------------------------------------------------------------

@login_required
def review_update_view(request: HttpRequest, pk: int) -> HttpResponse:
    review = get_object_or_404(Review.objects.select_related('quest'), pk=pk)
    _ensure_review_access(request.user, review)
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Отзыв обновлён.')
        return redirect('booking:quest_detail', slug=review.quest.slug)
    return render(request, 'booking/review_form.html', {'form': form, 'review': review})


@login_required
def review_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    review = get_object_or_404(Review.objects.select_related('quest'), pk=pk)
    _ensure_review_access(request.user, review)
    quest_slug = review.quest.slug
    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Отзыв удалён.')
        return redirect('booking:quest_detail', slug=quest_slug)
    return render(request, 'booking/review_confirm_delete.html', {'review': review})


# ---------------------------------------------------------------------------
# CRUD квест-комнат на сайте (для администратора / оператора)
# ---------------------------------------------------------------------------

@login_required
def quest_create_view(request: HttpRequest) -> HttpResponse:
    if not _is_staff_or_operator(request.user):
        raise PermissionDenied('Только администратор или оператор может добавлять квесты.')
    form = QuestRoomForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        quest = form.save()
        messages.success(request, f'Квест «{quest.title}» успешно создан.')
        return redirect('booking:quest_detail', slug=quest.slug)
    return render(request, 'booking/quest_form.html', {'form': form, 'is_edit': False})


@login_required
def quest_update_view(request: HttpRequest, slug: str) -> HttpResponse:
    if not _is_staff_or_operator(request.user):
        raise PermissionDenied('Только администратор или оператор может редактировать квесты.')
    quest = get_object_or_404(QuestRoom, slug=slug)
    form = QuestRoomForm(request.POST or None, request.FILES or None, instance=quest)
    if request.method == 'POST' and form.is_valid():
        quest = form.save()
        messages.success(request, f'Квест «{quest.title}» обновлён.')
        return redirect('booking:quest_detail', slug=quest.slug)
    return render(request, 'booking/quest_form.html', {'form': form, 'quest': quest, 'is_edit': True})


@login_required
def quest_delete_view(request: HttpRequest, slug: str) -> HttpResponse:
    if not _is_staff_or_operator(request.user):
        raise PermissionDenied('Только администратор или оператор может удалять квесты.')
    quest = get_object_or_404(QuestRoom, slug=slug)
    if request.method == 'POST':
        title = quest.title
        try:
            quest.delete()
            messages.success(request, f'Квест «{title}» удалён.')
            return redirect('booking:quest_list')
        except Exception:
            messages.error(
                request,
                'Нельзя удалить квест, по которому уже есть бронирования. Сделайте его неактивным.',
            )
            return redirect('booking:quest_detail', slug=quest.slug)
    return render(request, 'booking/quest_confirm_delete.html', {'quest': quest})


# ---------------------------------------------------------------------------
# CRUD бронирований
# ---------------------------------------------------------------------------

@login_required
def booking_create_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Оформление бронирования сеанса с расчётом цены и проверкой 30-мин перерыва."""
    quest = get_object_or_404(QuestRoom, slug=slug, is_active=True)
    user_teams = Team.objects.filter(captain=request.user)
    if not user_teams.exists():
        messages.info(request, 'Сначала создайте команду, чтобы оформить бронирование.')
        return redirect('booking:team_create')

    initial = {}
    if request.GET.get('date'):
        initial['booking_date'] = request.GET['date']
    if request.GET.get('time'):
        initial['start_time'] = request.GET['time']
    initial['players_count'] = min(4, quest.max_players)

    form = BookingForm(
        request.POST or None,
        initial=initial,
        quest=quest,
        captain=request.user,
    )

    if request.method == 'POST' and form.is_valid():
        try:
            booking = create_booking_atomic(
                quest=quest,
                team=form.cleaned_data['team'],
                captain=request.user,
                booking_date=form.cleaned_data['booking_date'],
                start_time=form.cleaned_data['start_time'],
                players_count=form.cleaned_data['players_count'],
                extra_options=list(form.cleaned_data['extra_options']),
                notes=form.cleaned_data.get('notes', ''),
            )
            messages.success(
                request,
                f'Бронирование {booking.booking_code} подтверждено! Итого: {booking.total_price} ₽.',
            )
            return redirect('booking:booking_detail', pk=booking.pk)
        except ValidationError as exc:
            form.add_error(None, exc.message)

    return render(
        request,
        'booking/booking_create.html',
        {
            'quest': quest,
            'form': form,
            'extras': ExtraOption.objects.filter(is_active=True),
        },
    )


@login_required
def booking_detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    booking = get_object_or_404(
        Booking.objects.select_related('quest', 'team', 'captain', 'tariff_slot')
        .prefetch_related('booking_extras__option'),
        pk=pk,
    )
    _ensure_booking_access(request.user, booking)
    return render(
        request,
        'booking/booking_detail.html',
        {
            'booking': booking,
            'is_staff_or_operator': _is_staff_or_operator(request.user),
        },
    )


@login_required
def booking_update_view(request: HttpRequest, pk: int) -> HttpResponse:
    booking = get_object_or_404(Booking.objects.select_related('quest'), pk=pk)
    _ensure_booking_access(request.user, booking)

    if booking.status in (Booking.STATUS_COMPLETED, Booking.STATUS_CANCELLED):
        messages.error(request, 'Завершённое или отменённое бронирование нельзя редактировать.')
        return redirect('booking:booking_detail', pk=booking.pk)

    form = BookingForm(
        request.POST or None,
        instance=booking,
        quest=booking.quest,
        captain=booking.captain,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            update_booking_atomic(
                booking=booking,
                team=form.cleaned_data['team'],
                booking_date=form.cleaned_data['booking_date'],
                start_time=form.cleaned_data['start_time'],
                players_count=form.cleaned_data['players_count'],
                extra_options=list(form.cleaned_data['extra_options']),
                notes=form.cleaned_data.get('notes', ''),
            )
            messages.success(request, f'Бронирование {booking.booking_code} обновлено.')
            return redirect('booking:booking_detail', pk=booking.pk)
        except ValidationError as exc:
            form.add_error(None, exc.message)

    return render(
        request,
        'booking/booking_form.html',
        {'form': form, 'booking': booking, 'quest': booking.quest},
    )


@login_required
def booking_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    booking = get_object_or_404(Booking, pk=pk)
    _ensure_booking_access(request.user, booking)

    if request.method == 'POST':
        with transaction.atomic():
            booking.status = Booking.STATUS_CANCELLED
            booking.save(update_fields=['status', 'updated_at'])
        send_booking_notification(booking, event='cancelled')
        messages.success(request, f'Бронирование {booking.booking_code} отменено.')
        return redirect('booking:profile')

    return render(request, 'booking/booking_confirm_delete.html', {'booking': booking})


@login_required
def booking_print_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Печатная форма талона бронирования."""
    booking = get_object_or_404(
        Booking.objects.select_related('quest', 'team', 'captain', 'tariff_slot')
        .prefetch_related('booking_extras__option'),
        pk=pk,
    )
    _ensure_booking_access(request.user, booking)
    return render(request, 'booking/booking_print.html', {'booking': booking})


@login_required
def booking_export_csv_view(request: HttpRequest) -> HttpResponse:
    """Экспорт бронирований в CSV."""
    if _is_staff_or_operator(request.user):
        qs = Booking.objects.all()
    else:
        qs = Booking.objects.filter(captain=request.user)
    return build_bookings_csv_response(qs)


# ---------------------------------------------------------------------------
# Расписание актёра-аниматора
# ---------------------------------------------------------------------------

@login_required
def actor_schedule_view(request: HttpRequest) -> HttpResponse:
    """Просмотр назначенных сеансов с услугой актёра-аниматора."""
    if not _is_actor_or_staff(request.user):
        raise PermissionDenied('Раздел доступен только актёрам-аниматорам, операторам и администраторам.')

    qs = (
        BookingExtraOption.objects.select_related(
            'booking__quest',
            'booking__team',
            'option',
            'assigned_actor',
        )
        .filter(option__option_type=ExtraOption.TYPE_ACTOR)
        .exclude(booking__status=Booking.STATUS_CANCELLED)
        .order_by('booking__booking_date', 'booking__start_time')
    )
    if not _is_staff_or_operator(request.user):
        qs = qs.filter(assigned_actor=request.user)

    return render(request, 'booking/actor_schedule.html', {'assignments': qs})


# ---------------------------------------------------------------------------
# CRUD команд игрока
# ---------------------------------------------------------------------------

@login_required
def team_list_view(request: HttpRequest) -> HttpResponse:
    teams = Team.objects.filter(captain=request.user).annotate(
        bookings_count=Count('bookings')
    )
    return render(request, 'booking/team_list.html', {'teams': teams})


@login_required
def team_create_view(request: HttpRequest) -> HttpResponse:
    form = TeamForm(request.POST or None, captain=request.user)
    if request.method == 'POST' and form.is_valid():
        team = form.save(commit=False)
        team.captain = request.user
        team.save()
        messages.success(request, f'Команда «{team.name}» создана.')
        return redirect('booking:team_list')
    return render(request, 'booking/team_form.html', {'form': form, 'is_edit': False})


@login_required
def team_update_view(request: HttpRequest, pk: int) -> HttpResponse:
    team = get_object_or_404(Team, pk=pk)
    _ensure_team_access(request.user, team)
    form = TeamForm(request.POST or None, instance=team, captain=team.captain)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Команда «{team.name}» обновлена.')
        return redirect('booking:team_list')
    return render(request, 'booking/team_form.html', {'form': form, 'team': team, 'is_edit': True})


@login_required
def team_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    team = get_object_or_404(Team, pk=pk)
    _ensure_team_access(request.user, team)
    if request.method == 'POST':
        name = team.name
        try:
            team.delete()
            messages.success(request, f'Команда «{name}» удалена.')
        except Exception:
            messages.error(request, 'Нельзя удалить команду, у которой уже есть бронирования.')
        return redirect('booking:team_list')
    return render(request, 'booking/team_confirm_delete.html', {'team': team})


# ---------------------------------------------------------------------------
# Таблица рекордов и фиксация результата
# ---------------------------------------------------------------------------

def leaderboard_view(request: HttpRequest) -> HttpResponse:
    qs = GameResult.objects.select_related('quest', 'team', 'booking')
    quest_slug = request.GET.get('quest', '').strip()
    if quest_slug:
        qs = qs.filter(quest__slug=quest_slug)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'booking/leaderboard.html',
        {
            'page_obj': page_obj,
            'quests': QuestRoom.objects.filter(is_active=True),
            'selected_quest': quest_slug,
        },
    )


@login_required
def result_create_view(request: HttpRequest, booking_pk: int) -> HttpResponse:
    if not _is_staff_or_operator(request.user):
        raise PermissionDenied('Только оператор или администратор может фиксировать результаты.')
    booking = get_object_or_404(Booking.objects.select_related('quest', 'team'), pk=booking_pk)
    if hasattr(booking, 'result'):
        messages.info(request, 'Результат для этого бронирования уже зафиксирован.')
        return redirect('booking:leaderboard')

    form = GameResultForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            result = form.save(commit=False)
            result.booking = booking
            result.quest = booking.quest
            result.team = booking.team
            result.played_at = booking.booking_date
            result.recorded_by = request.user
            raw_score = 1000 - (result.completion_minutes * 5) - (result.hints_used * 80)
            result.score = max(100, raw_score)
            result.save()

            booking.status = Booking.STATUS_COMPLETED
            booking.save(update_fields=['status', 'updated_at'])

        send_booking_notification(booking, event='completed')
        messages.success(request, f'Результат команды «{booking.team.name}» добавлен в таблицу рекордов.')
        return redirect('booking:leaderboard')

    return render(request, 'booking/result_form.html', {'form': form, 'booking': booking})


# ---------------------------------------------------------------------------
# Сводные показатели и аналитика (только для оператора / администратора)
# ---------------------------------------------------------------------------

@login_required
def analytics_view(request: HttpRequest) -> HttpResponse:
    """Страница со сводными показателями (только для оператора и администратора)."""
    if not _is_staff_or_operator(request.user):
        raise PermissionDenied('Сводная финансовая аналитика доступна только оператору и администратору.')

    active_bookings = Booking.objects.exclude(status=Booking.STATUS_CANCELLED)
    total_count = active_bookings.count()

    agg = active_bookings.aggregate(
        total_revenue=Sum('total_price'),
        avg_check=Avg('total_price'),
        avg_players=Avg('players_count'),
        extra_fee_sum=Sum('extra_players_fee'),
    )
    over_4_count = active_bookings.filter(players_count__gt=4).count()
    over_4_share = round((over_4_count / total_count) * 100, 1) if total_count else 0.0

    with_extras_count = active_bookings.filter(extras_total__gt=0).count()
    extras_share = round((with_extras_count / total_count) * 100, 1) if total_count else 0.0

    genre_stats = list(
        Genre.objects.annotate(
            bookings_total=Count(
                'quests__bookings',
                filter=~Q(quests__bookings__status=Booking.STATUS_CANCELLED),
            ),
            revenue=Sum(
                'quests__bookings__total_price',
                filter=~Q(quests__bookings__status=Booking.STATUS_CANCELLED),
            ),
        ).values('name', 'bookings_total', 'revenue')
    )
    for item in genre_stats:
        item['revenue'] = float(item['revenue'] or 0)

    return render(
        request,
        'booking/analytics.html',
        {
            'total_count': total_count,
            'total_revenue': agg['total_revenue'] or Decimal('0.00'),
            'avg_check': agg['avg_check'] or Decimal('0.00'),
            'avg_players': round(agg['avg_players'] or 0, 1),
            'extra_fee_sum': agg['extra_fee_sum'] or Decimal('0.00'),
            'over_4_share': over_4_share,
            'extras_share': extras_share,
            'genre_stats': genre_stats,
        },
    )


# ---------------------------------------------------------------------------
# JSON API для динамических fetch-запросов
# ---------------------------------------------------------------------------

@require_GET
def api_booking_price_preview(request: HttpRequest, slug: str) -> JsonResponse:
    """Возвращает расчёт стоимости и проверку сетки/блокировки/30-мин перерыва в JSON."""
    quest = get_object_or_404(QuestRoom, slug=slug, is_active=True)

    date_str = request.GET.get('date', '').strip()
    time_str = request.GET.get('time', '').strip()
    players_str = request.GET.get('players', '4').strip()
    options_str = request.GET.get('options', '').strip()

    try:
        target_date = date.fromisoformat(date_str) if date_str else date.today()
        target_time = datetime.strptime(time_str, '%H:%M').time() if time_str else time(18, 0)
        players_count = int(players_str)
    except ValueError:
        return JsonResponse({'error': 'Некорректные параметры даты, времени или числа игроков.'}, status=400)

    option_ids = [int(x) for x in options_str.split(',') if x.strip().isdigit()]
    options = list(ExtraOption.objects.filter(pk__in=option_ids, is_active=True))

    try:
        breakdown = calculate_booking_price(quest, target_time, players_count, options)
    except ValidationError as exc:
        return JsonResponse({'error': exc.message}, status=400)

    available, reason = check_slot_availability(quest, target_date, target_time)

    return JsonResponse({
        'tariff_name': breakdown.tariff_slot.name,
        'tariff_multiplier': str(breakdown.tariff_multiplier),
        'base_price': str(breakdown.base_price),
        'extra_players_count': breakdown.extra_players_count,
        'extra_players_fee': str(breakdown.extra_players_fee),
        'extras_total': str(breakdown.extras_total),
        'total_price': str(breakdown.total_price),
        'available': available,
        'conflict_reason': reason,
    })


@require_GET
def api_quest_slots(request: HttpRequest, slug: str) -> JsonResponse:
    """Возвращает сетку сеансов на выбранную дату в JSON."""
    quest = get_object_or_404(QuestRoom, slug=slug, is_active=True)
    date_str = request.GET.get('date', '').strip()
    try:
        target_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        return JsonResponse({'error': 'Некорректный формат даты (ожидается ГГГГ-ММ-ДД).'}, status=400)

    slots = build_daily_slots_for_quest(quest, target_date)
    return JsonResponse({'date': target_date.isoformat(), 'slots': slots})


# ---------------------------------------------------------------------------
# Аутентификация и личный кабинет
# ---------------------------------------------------------------------------

class CustomLoginView(LoginView):
    """Вход с защитой от перебора паролей (ограничение числа попыток)."""

    template_name = 'registration/login.html'

    def _get_cache_key(self, request: HttpRequest) -> str:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        username = request.POST.get('username', '').strip().lower()
        return f'login_attempts:{ip}:{username}'

    def post(self, request: HttpRequest, *args, **kwargs):
        key = self._get_cache_key(request)
        attempts = cache.get(key, 0)
        max_attempts = getattr(settings, 'LOGIN_MAX_ATTEMPTS', 5)

        if attempts >= max_attempts:
            messages.error(
                request,
                'Слишком много неудачных попыток входа. Повторите через 5 минут.',
            )
            return self.render_to_response(self.get_context_data())

        response = super().post(request, *args, **kwargs)
        if request.user.is_authenticated:
            cache.delete(key)
        else:
            lockout = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 300)
            cache.set(key, attempts + 1, lockout)
        return response


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('booking:home')


class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'registration/password_change.html'
    success_url = reverse_lazy('booking:password_change_done')


class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = 'registration/password_change_done.html'


def register_view(request: HttpRequest) -> HttpResponse:
    """Регистрация нового пользователя."""
    if request.user.is_authenticated:
        return redirect('booking:profile')

    form = UserRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.first_name = form.cleaned_data['first_name']
            user.save()
            UserProfile.objects.create(
                user=user,
                role=UserProfile.ROLE_CAPTAIN,
                phone=form.cleaned_data['phone'],
            )
        try:
            send_mail(
                subject='Добро пожаловать в QuestHub!',
                message=f'Здравствуйте, {user.first_name}! Вы успешно зарегистрировались в QuestHub.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception('Ошибка отправки приветственного письма пользователю %s.', user.username)

        login(request, user)
        messages.success(request, 'Регистрация прошла успешно! Добро пожаловать в QuestHub.')
        return redirect('booking:profile')

    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """Личный кабинет пользователя."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = ProfileUpdateForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Профиль обновлён.')
        return redirect('booking:profile')

    if _is_staff_or_operator(request.user):
        bookings = Booking.objects.select_related('quest', 'team', 'captain')[:25]
    else:
        bookings = Booking.objects.filter(captain=request.user).select_related('quest', 'team')
    teams = Team.objects.filter(captain=request.user)

    return render(
        request,
        'booking/profile.html',
        {
            'profile': profile,
            'form': form,
            'bookings': bookings,
            'teams': teams,
            'is_staff_or_operator': _is_staff_or_operator(request.user),
        },
    )


# ---------------------------------------------------------------------------
# Пользовательские страницы ошибок 403 / 404 / 500
# ---------------------------------------------------------------------------

def custom_403_view(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, '403.html', status=403)


def custom_404_view(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, '404.html', status=404)


def custom_500_view(request: HttpRequest) -> HttpResponse:
    return render(request, '500.html', status=500)
