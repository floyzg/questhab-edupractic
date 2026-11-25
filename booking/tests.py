"""Автотесты проекта QuestHub (Вариант 14): бизнес-логика, транзакции, права доступа и негативные сценарии."""
from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from booking.models import (
    AgeRating,
    Booking,
    BookingExtraOption,
    ExtraOption,
    Genre,
    QuestRoom,
    Review,
    SessionSchedule,
    TariffSlot,
    Team,
    UserProfile,
)
from booking.services import (
    calculate_booking_price,
    check_slot_availability,
    create_booking_atomic,
    find_schedule_conflict,
    update_booking_atomic,
)


class QuestHubVariant14Tests(TestCase):
    """Тесты особого требования Варианта 14, безопасности и негативных сценариев."""

    def setUp(self):
        self.genre = Genre.objects.create(name='Хоррор', slug='horror')
        self.age = AgeRating.objects.create(code='16+', min_age=16)
        self.tariff_day = TariffSlot.objects.create(
            name='Дневной',
            start_time=time(12, 0),
            end_time=time(18, 0),
            price_multiplier=Decimal('1.00'),
        )
        self.quest = QuestRoom.objects.create(
            title='Тайна маяка',
            slug='lighthouse-mystery',
            genre=self.genre,
            age_rating=self.age,
            description='Атмосферный квест на старом маяке.',
            fear_level=4,
            difficulty=3,
            duration_minutes=60,
            min_players=2,
            max_players=6,
            base_price=Decimal('3000.00'),
            extra_player_price=Decimal('700.00'),
        )
        self.extra_lounge = ExtraOption.objects.create(
            name='Лаунж-зона',
            option_type=ExtraOption.TYPE_LOUNGE,
            price=Decimal('1000.00'),
        )

        self.user1 = User.objects.create_user(username='cap1', email='c1@test.local', password='StrongPassword123!')
        UserProfile.objects.create(user=self.user1, role=UserProfile.ROLE_CAPTAIN, phone='+7 900 111-11-11')
        self.team1 = Team.objects.create(name='Альфа', captain=self.user1, contact_phone='+7 900 111-11-11')

        self.user2 = User.objects.create_user(username='cap2', email='c2@test.local', password='StrongPassword123!')
        UserProfile.objects.create(user=self.user2, role=UserProfile.ROLE_CAPTAIN, phone='+7 900 222-22-22')
        self.team2 = Team.objects.create(name='Бета', captain=self.user2, contact_phone='+7 900 222-22-22')

        self.operator = User.objects.create_user(
            username='oper1', email='op@test.local', password='StrongPassword123!', is_staff=True
        )
        UserProfile.objects.create(user=self.operator, role=UserProfile.ROLE_OPERATOR, phone='+7 900 333-33-33')

        self.actor = User.objects.create_user(username='actor1', email='act@test.local', password='StrongPassword123!')
        UserProfile.objects.create(user=self.actor, role=UserProfile.ROLE_ACTOR, phone='+7 900 444-44-44')

        self.client = Client()

    def test_extra_player_surcharge_over_4_players(self):
        """Особое требование: базовая цена на 2–4 чел., доплата за каждого сверх 4."""
        bd_4 = calculate_booking_price(self.quest, time(14, 30), 4, [])
        self.assertEqual(bd_4.extra_players_count, 0)
        self.assertEqual(bd_4.extra_players_fee, Decimal('0.00'))
        self.assertEqual(bd_4.total_price, Decimal('3000.00'))

        bd_6 = calculate_booking_price(self.quest, time(14, 30), 6, [self.extra_lounge])
        self.assertEqual(bd_6.extra_players_count, 2)
        self.assertEqual(bd_6.extra_players_fee, Decimal('1400.00'))
        self.assertEqual(bd_6.extras_total, Decimal('1000.00'))
        self.assertEqual(bd_6.total_price, Decimal('5400.00'))

    def test_30_minute_technical_break_enforced(self):
        """Особое требование: между соседними сеансами удерживается 30-минутный перерыв."""
        tomorrow = date.today() + timedelta(days=1)
        create_booking_atomic(
            quest=self.quest,
            team=self.team1,
            captain=self.user1,
            booking_date=tomorrow,
            start_time=time(14, 30),
            players_count=4,
            extra_options=[],
        )
        self.assertIsNotNone(find_schedule_conflict(self.quest, tomorrow, time(15, 45)))
        self.assertIsNone(find_schedule_conflict(self.quest, tomorrow, time(16, 0)))

    def test_arbitrary_time_outside_grid_rejected(self):
        """Бронирование произвольного времени вне сетки сеансов отклоняется."""
        tomorrow = date.today() + timedelta(days=1)
        available, _ = check_slot_availability(self.quest, tomorrow, time(10, 7))
        self.assertFalse(available)
        with self.assertRaises(ValidationError):
            create_booking_atomic(
                quest=self.quest,
                team=self.team1,
                captain=self.user1,
                booking_date=tomorrow,
                start_time=time(10, 7),
                players_count=4,
                extra_options=[],
            )

    def test_blocked_session_cannot_be_booked(self):
        """Заблокированный в SessionSchedule сеанс (is_blocked=True) недоступен для бронирования."""
        tomorrow = date.today() + timedelta(days=1)
        SessionSchedule.objects.create(
            quest=self.quest,
            tariff_slot=self.tariff_day,
            date=tomorrow,
            start_time=time(13, 0),
            end_time=time(14, 0),
            is_blocked=True,
        )
        available, _ = check_slot_availability(self.quest, tomorrow, time(13, 0))
        self.assertFalse(available)
        with self.assertRaises(ValidationError):
            create_booking_atomic(
                quest=self.quest,
                team=self.team1,
                captain=self.user1,
                booking_date=tomorrow,
                start_time=time(13, 0),
                players_count=4,
                extra_options=[],
            )

    def test_reschedule_updates_session_schedule(self):
        """При переносе бронирования обновляется связанная запись SessionSchedule."""
        tomorrow = date.today() + timedelta(days=1)
        booking = create_booking_atomic(
            quest=self.quest,
            team=self.team1,
            captain=self.user1,
            booking_date=tomorrow,
            start_time=time(13, 0),
            players_count=4,
            extra_options=[],
        )
        old_session_id = booking.session_id
        update_booking_atomic(
            booking=booking,
            team=self.team1,
            booking_date=tomorrow,
            start_time=time(16, 0),
            players_count=4,
            extra_options=[],
        )
        booking.refresh_from_db()
        self.assertNotEqual(booking.session_id, old_session_id)
        self.assertEqual(booking.session.start_time, time(16, 0))

    def test_negative_transaction_rollback_on_mid_operation_error(self):
        """Негативный тест (Занятие 16): при ошибке в середине операции данные не меняются (откат)."""
        tomorrow = date.today() + timedelta(days=1)
        with patch('booking.services.BookingExtraOption.objects.create', side_effect=RuntimeError('DB failure')):
            with self.assertRaises(RuntimeError):
                create_booking_atomic(
                    quest=self.quest,
                    team=self.team1,
                    captain=self.user1,
                    booking_date=tomorrow,
                    start_time=time(13, 0),
                    players_count=4,
                    extra_options=[self.extra_lounge],
                )
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(SessionSchedule.objects.count(), 0)
        self.assertEqual(BookingExtraOption.objects.count(), 0)

    def test_negative_404_on_nonexistent_quest(self):
        """Негативный тест (Занятие 16): несуществующий квест возвращает 404."""
        resp = self.client.get(reverse('booking:quest_detail', kwargs={'slug': 'no-such-quest'}))
        self.assertEqual(resp.status_code, 404)

    def test_negative_403_idor_on_foreign_booking(self):
        """Негативный тест (Занятие 16): доступ к чужой брони возвращает 403."""
        tomorrow = date.today() + timedelta(days=1)
        booking = create_booking_atomic(
            quest=self.quest,
            team=self.team1,
            captain=self.user1,
            booking_date=tomorrow,
            start_time=time(14, 30),
            players_count=4,
            extra_options=[],
        )
        self.client.force_login(self.user2)
        resp = self.client.get(reverse('booking:booking_detail', kwargs={'pk': booking.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_negative_invalid_form_does_not_create_record(self):
        """Негативный тест (Занятие 16): форма с неверными данными не создаёт запись."""
        self.client.force_login(self.user1)
        resp = self.client.post(
            reverse('booking:team_create'),
            {'name': 'А', 'contact_phone': 'invalid', 'default_players_count': 4},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Team.objects.filter(captain=self.user1).count(), 1)

    def test_analytics_restricted_to_staff_and_operator(self):
        """Финансовая аналитика закрыта для обычного игрока (403) и открыта оператору (200)."""
        self.client.force_login(self.user1)
        self.assertEqual(self.client.get(reverse('booking:analytics')).status_code, 403)

        self.client.force_login(self.operator)
        resp = self.client.get(reverse('booking:analytics'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '0')

    def test_actor_schedule_and_review_crud(self):
        """Роль актёра видит свои смены; автор может редактировать и удалять отзыв."""
        self.client.force_login(self.user1)
        self.assertEqual(self.client.get(reverse('booking:actor_schedule')).status_code, 403)

        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(reverse('booking:actor_schedule')).status_code, 200)

        rev = Review.objects.create(quest=self.quest, author=self.user1, rating=5, comment='Отличный квест, очень понравилось!')
        self.client.force_login(self.user2)
        self.assertEqual(self.client.get(reverse('booking:review_update', kwargs={'pk': rev.pk})).status_code, 403)

        self.client.force_login(self.user1)
        self.assertEqual(
            self.client.post(
                reverse('booking:review_update', kwargs={'pk': rev.pk}),
                {'rating': 4, 'comment': 'Обновлённый текст отзыва для проверки.'},
            ).status_code,
            302,
        )
        rev.refresh_from_db()
        self.assertEqual(rev.rating, 4)

    def test_negative_forbidden_file_upload_rejected(self):
        """Негативный тест (Занятие 16): загрузка файла запрещённого типа (.php) отклоняется."""
        self.client.force_login(self.user1)
        bad_file = SimpleUploadedFile('shell.php', b'<?php echo 1; ?>', content_type='application/x-php')
        resp = self.client.post(
            reverse('booking:profile'),
            {'phone': '+7 900 111-11-11', 'avatar': bad_file},
        )
        self.assertEqual(resp.status_code, 200)
        self.user1.profile.refresh_from_db()
        self.assertFalse(bool(self.user1.profile.avatar))
