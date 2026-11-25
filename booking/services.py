"""Сервисный слой: расчёт стоимости, сетка сеансов, 30-мин перерыв, транзакции, CSV и email."""
import csv
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponse
from PIL import Image, UnidentifiedImageError

from .models import (
    Booking,
    BookingExtraOption,
    ExtraOption,
    QuestRoom,
    SessionSchedule,
    TariffSlot,
    Team,
)

logger = logging.getLogger('booking')


@dataclass(frozen=True)
class PriceBreakdown:
    """Детализация расчёта стоимости бронирования."""

    tariff_slot: Optional[TariffSlot]
    tariff_multiplier: Decimal
    base_price: Decimal
    extra_players_count: int
    extra_players_fee: Decimal
    extras_total: Decimal
    total_price: Decimal


def get_allowed_start_times(quest: QuestRoom) -> list[time]:
    """Возвращает допустимую сетку времени начала сеансов для квеста (10:00–22:30)."""
    step_minutes = quest.duration_minutes + getattr(settings, 'TECH_BREAK_MINUTES', 30)
    current_dt = datetime.combine(date.today(), time(10, 0))
    end_of_day = datetime.combine(date.today(), time(22, 30))
    times: list[time] = []
    while current_dt <= end_of_day:
        times.append(current_dt.time())
        current_dt += timedelta(minutes=step_minutes)
    return times


def get_tariff_for_time(start_time: time) -> TariffSlot:
    """Определяет тарифный слот по времени начала игры (учитывая ночные интервалы)."""
    slots = list(TariffSlot.objects.all())
    for slot in slots:
        if slot.start_time <= slot.end_time:
            if slot.start_time <= start_time < slot.end_time:
                return slot
        else:
            if start_time >= slot.start_time or start_time < slot.end_time:
                return slot
    if slots:
        return slots[0]
    fallback, _ = TariffSlot.objects.get_or_create(
        name='Стандартный',
        defaults={
            'start_time': time(0, 0),
            'end_time': time(23, 59),
            'price_multiplier': Decimal('1.00'),
            'description': 'Базовый круглосуточный тариф',
        },
    )
    return fallback


def calculate_booking_price(
    quest: QuestRoom,
    start_time: time,
    players_count: int,
    extra_options: Iterable[ExtraOption],
) -> PriceBreakdown:
    """
    Особое требование Варианта 14:
    Базовая цена рассчитана на команду от 2 до 4 человек с учётом тарифного слота.
    За каждого дополнительного участника сверх 4 (до max_players) начисляется доплата.
    """
    if players_count < quest.min_players or players_count > quest.max_players:
        raise ValidationError(
            f'Количество игроков должно быть от {quest.min_players} до {quest.max_players}.'
        )

    tariff = get_tariff_for_time(start_time)
    multiplier = tariff.price_multiplier

    base_price = (quest.base_price * multiplier).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    included = getattr(settings, 'BASE_INCLUDED_PLAYERS', 4)
    extra_players_count = max(0, players_count - included)
    extra_players_fee = (
        Decimal(extra_players_count) * quest.extra_player_price
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    extras_total = sum(
        (opt.price for opt in extra_options),
        Decimal('0.00'),
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    total_price = (base_price + extra_players_fee + extras_total).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    return PriceBreakdown(
        tariff_slot=tariff,
        tariff_multiplier=multiplier,
        base_price=base_price,
        extra_players_count=extra_players_count,
        extra_players_fee=extra_players_fee,
        extras_total=extras_total,
        total_price=total_price,
    )


def find_schedule_conflict(
    quest: QuestRoom,
    booking_date: date,
    start_time: time,
    exclude_booking_id: Optional[int] = None,
) -> Optional[Booking]:
    """
    Особое требование Варианта 14:
    Между двумя соседними забронированными сеансами одного квеста
    система обязана удерживать технический перерыв 30 минут на сборку реквизита.
    Возвращает конфликтующее бронирование или None.
    """
    break_minutes = getattr(settings, 'TECH_BREAK_MINUTES', 30)
    buffer_delta = timedelta(minutes=break_minutes)

    proposed_start = datetime.combine(booking_date, start_time)
    proposed_end = proposed_start + timedelta(minutes=quest.duration_minutes)

    candidate_dates = [
        booking_date - timedelta(days=1),
        booking_date,
        booking_date + timedelta(days=1),
    ]
    active_statuses = [
        Booking.STATUS_PENDING,
        Booking.STATUS_CONFIRMED,
        Booking.STATUS_COMPLETED,
    ]
    qs = Booking.objects.select_related('quest').filter(
        quest=quest,
        booking_date__in=candidate_dates,
        status__in=active_statuses,
    )
    if exclude_booking_id is not None:
        qs = qs.exclude(pk=exclude_booking_id)

    for existing in qs:
        ex_start = datetime.combine(existing.booking_date, existing.start_time)
        ex_end = ex_start + timedelta(minutes=existing.quest.duration_minutes)
        if proposed_start < (ex_end + buffer_delta) and (proposed_end + buffer_delta) > ex_start:
            return existing

    return None


def check_slot_availability(
    quest: QuestRoom,
    booking_date: date,
    start_time: time,
    exclude_booking_id: Optional[int] = None,
) -> tuple[bool, str]:
    """
    Комплексная проверка доступности слота:
    1. Время начала входит в разрешённую сетку сеансов квеста (или открытый SessionSchedule).
    2. Сеанс не заблокирован в SessionSchedule (is_blocked=True).
    3. Нет пересечения с другими бронями и 30-минутным техническим перерывом.
    """
    allowed_times = get_allowed_start_times(quest)
    has_custom_slot = SessionSchedule.objects.filter(
        quest=quest,
        date=booking_date,
        start_time=start_time,
        is_blocked=False,
    ).exists()
    if start_time not in allowed_times and not has_custom_slot:
        return (
            False,
            'Выбранное время не входит в доступную сетку сеансов квеста.',
        )

    proposed_start = datetime.combine(booking_date, start_time)
    proposed_end = proposed_start + timedelta(minutes=quest.duration_minutes)

    blocked_sessions = SessionSchedule.objects.filter(
        quest=quest,
        date=booking_date,
        is_blocked=True,
    )
    for blocked in blocked_sessions:
        b_start = datetime.combine(blocked.date, blocked.start_time)
        b_end = datetime.combine(blocked.date, blocked.end_time)
        if b_end <= b_start:
            b_end += timedelta(days=1)
        if proposed_start < b_end and proposed_end > b_start:
            return (
                False,
                f'Сеанс {blocked.start_time:%H:%M} заблокирован администратором (обслуживание).',
            )

    conflict = find_schedule_conflict(
        quest,
        booking_date,
        start_time,
        exclude_booking_id=exclude_booking_id,
    )
    if conflict is not None:
        break_min = getattr(settings, 'TECH_BREAK_MINUTES', 30)
        return (
            False,
            f'Пересечение с сеансом {conflict.start_time:%H:%M}–'
            f'{conflict.end_time:%H:%M} или техническим перерывом {break_min} минут.',
        )

    return True, 'Свободно'


def generate_booking_code() -> str:
    """Генерирует уникальный читаемый код бронирования."""
    return f'QH-{uuid.uuid4().hex[:8].upper()}'


def create_booking_atomic(
    *,
    quest: QuestRoom,
    team: Team,
    captain,
    booking_date: date,
    start_time: time,
    players_count: int,
    extra_options: list[ExtraOption],
    notes: str = '',
) -> Booking:
    """Создаёт бронирование и связанные опции в одной транзакции."""
    with transaction.atomic():
        locked_quest = QuestRoom.objects.select_for_update().get(pk=quest.pk)

        available, reason = check_slot_availability(locked_quest, booking_date, start_time)
        if not available:
            raise ValidationError(reason)

        breakdown = calculate_booking_price(
            quest=locked_quest,
            start_time=start_time,
            players_count=players_count,
            extra_options=extra_options,
        )

        end_dt = datetime.combine(booking_date, start_time) + timedelta(
            minutes=locked_quest.duration_minutes
        )

        session_obj, _ = SessionSchedule.objects.get_or_create(
            quest=locked_quest,
            date=booking_date,
            start_time=start_time,
            defaults={
                'tariff_slot': breakdown.tariff_slot,
                'end_time': end_dt.time(),
                'is_blocked': False,
            },
        )

        booking = Booking.objects.create(
            booking_code=generate_booking_code(),
            quest=locked_quest,
            session=session_obj,
            tariff_slot=breakdown.tariff_slot,
            team=team,
            captain=captain,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_dt.time(),
            players_count=players_count,
            base_price=breakdown.base_price,
            extra_players_fee=breakdown.extra_players_fee,
            extras_total=breakdown.extras_total,
            total_price=breakdown.total_price,
            status=Booking.STATUS_CONFIRMED,
            notes=notes,
        )

        for option in extra_options:
            BookingExtraOption.objects.create(
                booking=booking,
                option=option,
                quantity=1,
                unit_price=option.price,
            )

    logger.info(
        'Создано бронирование %s пользователем %s на квест "%s" (%s %s).',
        booking.booking_code,
        captain.username,
        locked_quest.title,
        booking_date,
        start_time,
    )
    send_booking_notification(booking, event='created')
    return booking


def update_booking_atomic(
    *,
    booking: Booking,
    team: Team,
    booking_date: date,
    start_time: time,
    players_count: int,
    extra_options: list[ExtraOption],
    notes: str = '',
) -> Booking:
    """Обновляет бронирование, привязку к SessionSchedule, цену и проверяет перерыв."""
    with transaction.atomic():
        locked_quest = QuestRoom.objects.select_for_update().get(pk=booking.quest_id)
        available, reason = check_slot_availability(
            locked_quest,
            booking_date,
            start_time,
            exclude_booking_id=booking.pk,
        )
        if not available:
            raise ValidationError(reason)

        breakdown = calculate_booking_price(
            quest=locked_quest,
            start_time=start_time,
            players_count=players_count,
            extra_options=extra_options,
        )
        end_dt = datetime.combine(booking_date, start_time) + timedelta(
            minutes=locked_quest.duration_minutes
        )

        session_obj, _ = SessionSchedule.objects.get_or_create(
            quest=locked_quest,
            date=booking_date,
            start_time=start_time,
            defaults={
                'tariff_slot': breakdown.tariff_slot,
                'end_time': end_dt.time(),
                'is_blocked': False,
            },
        )

        booking.team = team
        booking.session = session_obj
        booking.tariff_slot = breakdown.tariff_slot
        booking.booking_date = booking_date
        booking.start_time = start_time
        booking.end_time = end_dt.time()
        booking.players_count = players_count
        booking.base_price = breakdown.base_price
        booking.extra_players_fee = breakdown.extra_players_fee
        booking.extras_total = breakdown.extras_total
        booking.total_price = breakdown.total_price
        booking.notes = notes
        booking.save()

        booking.booking_extras.all().delete()
        for option in extra_options:
            BookingExtraOption.objects.create(
                booking=booking,
                option=option,
                quantity=1,
                unit_price=option.price,
            )

    logger.info('Обновлено бронирование %s.', booking.booking_code)
    return booking


def send_booking_notification(booking: Booking, event: str = 'created') -> None:
    """Отправляет email-уведомление при создании или изменении статуса бронирования."""
    recipient = booking.captain.email
    if not recipient:
        return

    subjects = {
        'created': f'QuestHub: бронь {booking.booking_code} подтверждена',
        'cancelled': f'QuestHub: бронь {booking.booking_code} отменена',
        'completed': f'QuestHub: итоги игры по брони {booking.booking_code}',
    }
    subject = subjects.get(event, f'QuestHub: обновление брони {booking.booking_code}')
    body = (
        f'Здравствуйте, {booking.captain.get_full_name() or booking.captain.username}!\n\n'
        f'Статус вашего бронирования {booking.booking_code}: {booking.get_status_display()}.\n'
        f'Квест: {booking.quest.title}\n'
        f'Дата и время: {booking.booking_date:%d.%m.%Y} в {booking.start_time:%H:%M}\n'
        f'Команда: {booking.team.name} ({booking.players_count} чел.)\n'
        f'Итоговая стоимость: {booking.total_price} ₽\n\n'
        f'Ждём вас за 10 минут до начала сеанса!\n'
        f'Команда QuestHub'
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Ошибка отправки email для брони %s.', booking.booking_code)


def validate_uploaded_image(uploaded_file) -> None:
    """Проверяет размер, расширение и реальную сигнатуру загружаемого изображения."""
    if not uploaded_file:
        return

    max_size = getattr(settings, 'MAX_UPLOAD_IMAGE_SIZE', 2 * 1024 * 1024)
    allowed_ext = getattr(settings, 'ALLOWED_IMAGE_EXTENSIONS', {'.jpg', '.jpeg', '.png', '.webp'})

    if uploaded_file.size > max_size:
        raise ValidationError('Размер изображения не должен превышать 2 МБ.')

    filename = Path(uploaded_file.name).name
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_ext:
        raise ValidationError('Разрешены только изображения форматов JPG, PNG или WEBP.')

    try:
        pos = uploaded_file.tell()
        with Image.open(uploaded_file) as img:
            img.verify()
        uploaded_file.seek(pos)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError('Файл повреждён или не является корректным изображением.') from exc


def build_bookings_csv_response(queryset) -> HttpResponse:
    """Формирует CSV-выгрузку бронирований в кодировке UTF-8 BOM для Excel."""
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="questhub_bookings.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Код брони',
        'Квест',
        'Команда',
        'Капитан',
        'Дата',
        'Начало',
        'Окончание',
        'Игроков',
        'Тариф',
        'База (₽)',
        'Доплата >4 чел (₽)',
        'Доп. услуги (₽)',
        'Итого (₽)',
        'Статус',
    ])

    for b in queryset.select_related('quest', 'team', 'captain', 'tariff_slot'):
        writer.writerow([
            b.booking_code,
            b.quest.title,
            b.team.name,
            b.captain.username,
            b.booking_date.strftime('%d.%m.%Y'),
            b.start_time.strftime('%H:%M'),
            b.end_time.strftime('%H:%M'),
            b.players_count,
            b.tariff_slot.name,
            f'{b.base_price:.2f}',
            f'{b.extra_players_fee:.2f}',
            f'{b.extras_total:.2f}',
            f'{b.total_price:.2f}',
            b.get_status_display(),
        ])
    return response


def build_daily_slots_for_quest(quest: QuestRoom, target_date: date) -> list[dict]:
    """Генерирует сетку сеансов с учётом занятости, блокировок и 30-мин перерыва."""
    slots = []
    for slot_time in get_allowed_start_times(quest):
        tariff = get_tariff_for_time(slot_time)
        available, reason = check_slot_availability(quest, target_date, slot_time)
        price = (quest.base_price * tariff.price_multiplier).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        slots.append({
            'time': slot_time.strftime('%H:%M'),
            'tariff': tariff.name,
            'price': str(price),
            'available': available,
            'reason': reason,
        })
    return slots
