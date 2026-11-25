"""Автотесты проекта QuestHub (Вариант 14): бизнес-логика, транзакции, права доступа и негативные сценарии."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from booking.models import (
    AgeRating,
    Booking,
    ExtraOption,
    Genre,
    QuestRoom,
    TariffSlot,
    Team,
    UserProfile,
)
from booking.services import calculate_booking_price, create_booking_atomic, find_schedule_conflict


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

        self.client = Client()

    def test_extra_player_surcharge_over_4_players(self):
        """Особое требование: базовая цена на 2–4 чел., доплата за каждого сверх 4."""
        bd_4 = calculate_booking_price(self.quest, time(14, 0), 4, [])
        self.assertEqual(bd_4.extra_players_count, 0)
        self.assertEqual(bd_4.extra_players_fee, Decimal('0.00'))
        self.assertEqual(bd_4.total_price, Decimal('3000.00'))

        bd_6 = calculate_booking_price(self.quest, time(14, 0), 6, [self.extra_lounge])
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
            start_time=time(14, 0),
            players_count=4,
            extra_options=[],
        )
        # 14:00 + 60 мин = 15:00. Попытка на 15:15 (перерыв 15 мин < 30 мин) -> конфликт
        self.assertIsNotNone(find_schedule_conflict(self.quest, tomorrow, time(15, 15)))
        with self.assertRaises(ValidationError):
            create_booking_atomic(
                quest=self.quest,
                team=self.team2,
                captain=self.user2,
                booking_date=tomorrow,
                start_time=time(15, 15),
                players_count=4,
                extra_options=[],
            )
        # Попытка на 15:30 (ровно 30 мин перерыва) -> успешно
        self.assertIsNone(find_schedule_conflict(self.quest, tomorrow, time(15, 30)))

    def test_negative_404_on_nonexistent_quest(self):
        """Негативный тест 1 (Занятие 16): несуществующий квест возвращает 404."""
        resp = self.client.get(reverse('booking:quest_detail', kwargs={'slug': 'no-such-quest'}))
        self.assertEqual(resp.status_code, 404)

    def test_negative_403_idor_on_foreign_booking(self):
        """Негативный тест 2 (Занятие 16): доступ к чужой брони возвращает 403."""
        tomorrow = date.today() + timedelta(days=1)
        booking = create_booking_atomic(
            quest=self.quest,
            team=self.team1,
            captain=self.user1,
            booking_date=tomorrow,
            start_time=time(14, 0),
            players_count=4,
            extra_options=[],
        )
        self.client.force_login(self.user2)
        resp = self.client.get(reverse('booking:booking_detail', kwargs={'pk': booking.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_negative_invalid_form_does_not_create_record(self):
        """Негативный тест 3 (Занятие 16): форма с неверными данными не создаёт запись."""
        self.client.force_login(self.user1)
        resp = self.client.post(
            reverse('booking:team_create'),
            {'name': 'А', 'contact_phone': 'invalid', 'default_players_count': 4},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Team.objects.filter(captain=self.user1).count(), 1)

    def test_negative_analytics_on_empty_dataset(self):
        """Негативный тест 4 (Занятие 16): расчёт сводных показателей на пустой выборке не падает."""
        self.client.force_login(self.user1)
        resp = self.client.get(reverse('booking:analytics'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '0')

    def test_negative_forbidden_file_upload_rejected(self):
        """Негативный тест 5 (Занятие 16): загрузка файла запрещённого типа (.php) отклоняется."""
        self.client.force_login(self.user1)
        bad_file = SimpleUploadedFile('shell.php', b'<?php echo 1; ?>', content_type='application/x-php')
        resp = self.client.post(
            reverse('booking:profile'),
            {'phone': '+7 900 111-11-11', 'avatar': bad_file},
        )
        self.assertEqual(resp.status_code, 200)
        self.user1.profile.refresh_from_db()
        self.assertFalse(bool(self.user1.profile.avatar))
