"""Management-команда для заполнения базы демонстрационными данными (>= 30 записей)."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from booking.models import (
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
from booking.services import calculate_booking_price, generate_booking_code


class Command(BaseCommand):
    help = 'Заполняет базу данных демонстрационными данными (32 квеста, тарифы, команды, бронирования).'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('Загрузка демонстрационных данных QuestHub...')

        users_spec = [
            ('admin', 'admin@questhub.local', 'AdminPass123!', UserProfile.ROLE_ADMIN, True),
            ('operator1', 'operator@questhub.local', 'OperPass123!', UserProfile.ROLE_OPERATOR, True),
            ('actor1', 'actor@questhub.local', 'ActorPass123!', UserProfile.ROLE_ACTOR, False),
            ('captain1', 'captain1@questhub.local', 'PlayerPass123!', UserProfile.ROLE_CAPTAIN, False),
            ('captain2', 'captain2@questhub.local', 'PlayerPass123!', UserProfile.ROLE_CAPTAIN, False),
        ]
        users = {}
        for username, email, pwd, role, is_staff in users_spec:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'first_name': username.capitalize(), 'is_staff': is_staff},
            )
            if created:
                user.set_password(pwd)
                user.save()
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': role, 'phone': '+7 900 111-22-33'},
            )
            users[username] = user

        genres_data = [
            ('Хоррор', 'horror', 'Мрачные локации с атмосферой напряжения и актёрами.'),
            ('Детектив', 'detective', 'Расследование преступлений и поиск улик.'),
            ('Приключения', 'adventure', 'Динамичные экспедиции, тайники и древние артефакты.'),
            ('Фантастика', 'sci-fi', 'Космические станции, лаборатории будущего и ИИ.'),
            ('Мистика', 'mystery', 'Загадочные особняки, спиритизм и параллельные миры.'),
            ('Семейный', 'family', 'Добрые сказочные сюжеты для детей и родителей.'),
        ]
        genres = []
        for name, slug, desc in genres_data:
            g, _ = Genre.objects.get_or_create(slug=slug, defaults={'name': name, 'description': desc})
            genres.append(g)

        ratings_data = [
            ('6+', 6, 'Подходит для семейного отдыха с детьми.'),
            ('12+', 12, 'Умеренная сложность, без пугающих сцен.'),
            ('16+', 16, 'Напряжённая атмосфера, возможен контактный режим.'),
            ('18+', 18, 'Хоррор повышенной интенсивности.'),
        ]
        ratings = []
        for code, min_age, desc in ratings_data:
            r, _ = AgeRating.objects.get_or_create(code=code, defaults={'min_age': min_age, 'description': desc})
            ratings.append(r)

        tariffs_data = [
            ('Утренний', time(9, 0), time(12, 0), Decimal('0.85'), 'Скидка 15% на утренние игры'),
            ('Дневной', time(12, 0), time(18, 0), Decimal('1.00'), 'Базовый дневной тариф'),
            ('Вечерний', time(18, 0), time(22, 0), Decimal('1.20'), 'Вечерний прайм-тайм (+20%)'),
            ('Ночной', time(22, 0), time(9, 0), Decimal('1.35'), 'Ночные сеансы (+35%)'),
        ]
        for name, st, et, mult, desc in tariffs_data:
            TariffSlot.objects.get_or_create(
                name=name,
                defaults={'start_time': st, 'end_time': et, 'price_multiplier': mult, 'description': desc},
            )

        extras_data = [
            ('Профессиональный актёр-аниматор', ExtraOption.TYPE_ACTOR, Decimal('1500.00'), 'Живое участие актёра в сценарии.'),
            ('Лаунж-зона антикафе (60 мин)', ExtraOption.TYPE_LOUNGE, Decimal('1200.00'), 'Чай, кофе, настольные игры после квеста.'),
            ('Фотосессия команды', ExtraOption.TYPE_PHOTO, Decimal('900.00'), '15 обработанных снимков в интерьере квеста.'),
            ('Сладкий стол и торт', ExtraOption.TYPE_LOUNGE, Decimal('1800.00'), 'Сервировка для дня рождения.'),
            ('Видеозапись прохождения', ExtraOption.TYPE_OTHER, Decimal('1100.00'), 'Монтаж лучших моментов игры.'),
        ]
        extras = []
        for name, o_type, price, desc in extras_data:
            opt, _ = ExtraOption.objects.get_or_create(
                name=name,
                defaults={'option_type': o_type, 'price': price, 'description': desc},
            )
            extras.append(opt)

        quest_titles = [
            'Тайна заброшенной обсерватории', 'Проклятие старого маяка', 'Бункер-47: Перезагрузка',
            'Ограбление банка на Уолл-стрит', 'Лаборатория доктора Моро', 'Побег из Алькатраса',
            'Призрак оперного театра', 'Станция «Орбита-9»', 'Шерлок: Дело о пропавшем рубине',
            'Алиса в Зазеркалье', 'Тайна египетской пирамиды', 'Заброшенный санаторий',
            'Секретный архив КГБ', 'Корабль-призрак «Летучий голландец»', 'Киберпанк: Взлом матрицы',
            'Особняк семьи Блэквуд', 'Метро 2033: Тоннель надежды', 'Школа магии и чародейства',
            'Подземелье алхимика', 'Квест-перформанс «Зеркала»', 'Загадка Леонардо да Винчи',
            'Полярная экспедиция «Восток»', 'Казино «Рояль»', 'Тайная комната графини',
            'Вирус «Омега»: Вакцина', 'Остров сокровищ', 'Антикафе: Ночь детективов',
            'Машина времени профессора', 'Склеп древнего ордена', 'Последний экспресс',
            'Ловушка иллюзиониста', 'Хроники потерянного города',
        ]
        quests = []
        for idx, title in enumerate(quest_titles, start=1):
            slug = f'quest-{idx:02d}'
            q, _ = QuestRoom.objects.get_or_create(
                slug=slug,
                defaults={
                    'title': title,
                    'genre': genres[(idx - 1) % len(genres)],
                    'age_rating': ratings[(idx - 1) % len(ratings)],
                    'description': (
                        f'Захватывающий сюжет «{title}»: командная работа, логические загадки, '
                        f'атмосферные декорации и неожиданные повороты.'
                    ),
                    'fear_level': ((idx - 1) % 5) + 1,
                    'difficulty': ((idx + 1) % 5) + 1,
                    'duration_minutes': 60,
                    'min_players': 2,
                    'max_players': 6 if idx % 2 == 0 else 8,
                    'base_price': Decimal('3200.00') + Decimal((idx % 5) * 300),
                    'extra_player_price': Decimal('700.00'),
                    'is_active': True,
                },
            )
            quests.append(q)

        teams = []
        for i in range(1, 13):
            cap = users['captain1'] if i % 2 == 1 else users['captain2']
            t, _ = Team.objects.get_or_create(
                captain=cap,
                name=f'Команда «Искатели-{i}»',
                defaults={
                    'contact_phone': f'+7 900 555-01-{i:02d}',
                    'default_players_count': 4 + (i % 3),
                },
            )
            teams.append(t)

        if Booking.objects.count() < 15:
            slot_times = [time(10, 0), time(11, 30), time(13, 0), time(14, 30), time(16, 0), time(17, 30), time(19, 0)]
            actor_opt = extras[0]
            for i in range(15):
                q = quests[i % len(quests)]
                t = teams[i % len(teams)]
                b_date = date.today() + timedelta(days=(i // 3) + 1)
                s_time = slot_times[i % len(slot_times)]
                players = min(q.max_players, 3 + (i % 4))
                selected_extras = [actor_opt] if i in (0, 10, 12) else ([extras[i % len(extras)]] if i % 2 == 0 else [])

                if Booking.objects.filter(quest=q, booking_date=b_date, start_time=s_time).exists():
                    continue

                breakdown = calculate_booking_price(q, s_time, players, selected_extras)
                end_time = time((s_time.hour + 1) % 24, s_time.minute)
                b = Booking.objects.create(
                    booking_code=generate_booking_code(),
                    quest=q,
                    tariff_slot=breakdown.tariff_slot,
                    team=t,
                    captain=t.captain,
                    operator=users['operator1'],
                    booking_date=b_date,
                    start_time=s_time,
                    end_time=end_time,
                    players_count=players,
                    base_price=breakdown.base_price,
                    extra_players_fee=breakdown.extra_players_fee,
                    extras_total=breakdown.extras_total,
                    total_price=breakdown.total_price,
                    status=Booking.STATUS_COMPLETED if i < 10 else Booking.STATUS_CONFIRMED,
                    notes='Демонстрационное бронирование для проверки системы.',
                )
                for opt in selected_extras:
                    BookingExtraOption.objects.create(
                        booking=b,
                        option=opt,
                        quantity=1,
                        unit_price=opt.price,
                        assigned_actor=users['actor1'] if opt.option_type == ExtraOption.TYPE_ACTOR else None,
                    )

                if b.status == Booking.STATUS_COMPLETED and not hasattr(b, 'result'):
                    mins = 38 + (i * 2)
                    hints = i % 4
                    GameResult.objects.create(
                        booking=b,
                        quest=q,
                        team=t,
                        completion_minutes=mins,
                        hints_used=hints,
                        score=max(100, 1000 - mins * 5 - hints * 80),
                        played_at=b_date - timedelta(days=7),
                        recorded_by=users['operator1'],
                    )

        if Review.objects.count() < 12:
            for i in range(12):
                Review.objects.create(
                    quest=quests[i],
                    author=users['captain1'] if i % 2 == 0 else users['captain2'],
                    rating=5 if i % 3 != 0 else 4,
                    comment=f'Отличный квест «{quests[i].title}»! Загадки логичные, оператор очень внимательный.',
                    is_published=True,
                )

        self.stdout.write(self.style.SUCCESS(
            f'Готово! Квестов: {QuestRoom.objects.count()}, '
            f'Команд: {Team.objects.count()}, '
            f'Бронирований: {Booking.objects.count()}, '
            f'Рекордов: {GameResult.objects.count()}.'
        ))
