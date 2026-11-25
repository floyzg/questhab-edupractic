"""Модели данных приложения бронирования квест-комнат (Вариант 14)."""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class UserProfile(models.Model):
    """Расширенный профиль пользователя с ролью и контактными данными."""

    ROLE_CAPTAIN = 'captain'
    ROLE_OPERATOR = 'operator'
    ROLE_ACTOR = 'actor'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_CAPTAIN, 'Игрок (капитан команды)'),
        (ROLE_OPERATOR, 'Оператор квеста'),
        (ROLE_ACTOR, 'Актёр-аниматор'),
        (ROLE_ADMIN, 'Администратор локации'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Пользователь',
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_CAPTAIN,
        verbose_name='Роль в системе',
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Контактный телефон',
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name='Аватар',
    )

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'
        ordering = ['user__username']

    def __str__(self) -> str:
        return f'{self.user.username} ({self.get_role_display()})'


class Genre(models.Model):
    """Жанр квест-комнаты."""

    name = models.CharField(max_length=80, unique=True, verbose_name='Название жанра')
    slug = models.SlugField(max_length=90, unique=True, verbose_name='URL-метка')
    description = models.TextField(blank=True, verbose_name='Описание')

    class Meta:
        verbose_name = 'Жанр'
        verbose_name_plural = 'Жанры'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class AgeRating(models.Model):
    """Возрастной рейтинг квеста."""

    code = models.CharField(max_length=10, unique=True, verbose_name='Рейтинг')
    min_age = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(21)],
        verbose_name='Минимальный возраст',
    )
    description = models.CharField(max_length=200, blank=True, verbose_name='Пояснение')

    class Meta:
        verbose_name = 'Возрастной рейтинг'
        verbose_name_plural = 'Возрастные рейтинги'
        ordering = ['min_age']

    def __str__(self) -> str:
        return self.code


class QuestRoom(models.Model):
    """Квест-комната (основная сущность каталога)."""

    title = models.CharField(max_length=150, verbose_name='Название квеста')
    slug = models.SlugField(max_length=160, unique=True, verbose_name='URL-метка')
    genre = models.ForeignKey(
        Genre,
        on_delete=models.PROTECT,
        related_name='quests',
        verbose_name='Жанр',
    )
    age_rating = models.ForeignKey(
        AgeRating,
        on_delete=models.PROTECT,
        related_name='quests',
        verbose_name='Возрастной рейтинг',
    )
    description = models.TextField(verbose_name='Описание сюжета')
    fear_level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=2,
        verbose_name='Уровень страха (1–5)',
    )
    difficulty = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=3,
        verbose_name='Сложность (1–5)',
    )
    duration_minutes = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(30), MaxValueValidator(180)],
        verbose_name='Длительность (мин)',
    )
    min_players = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(2), MaxValueValidator(12)],
        verbose_name='Минимум игроков',
    )
    max_players = models.PositiveSmallIntegerField(
        default=6,
        validators=[MinValueValidator(2), MaxValueValidator(16)],
        verbose_name='Максимум игроков',
    )
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('100.00'))],
        verbose_name='Базовая цена (2–4 игрока), ₽',
    )
    extra_player_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('700.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Доплата за доп. игрока сверх 4, ₽',
    )
    image = models.ImageField(
        upload_to='quests/',
        blank=True,
        null=True,
        verbose_name='Обложка квеста',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен в каталоге')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')

    class Meta:
        verbose_name = 'Квест-комната'
        verbose_name_plural = 'Квест-комнаты'
        ordering = ['title']
        constraints = [
            models.CheckConstraint(
                check=Q(min_players__gte=2),
                name='quest_min_players_gte_2',
            ),
            models.CheckConstraint(
                check=Q(max_players__gte=F('min_players')),
                name='quest_max_gte_min_players',
            ),
            models.CheckConstraint(
                check=Q(fear_level__gte=1, fear_level__lte=5),
                name='quest_fear_level_1_5',
            ),
            models.CheckConstraint(
                check=Q(difficulty__gte=1, difficulty__lte=5),
                name='quest_difficulty_1_5',
            ),
            models.CheckConstraint(
                check=Q(base_price__gt=0),
                name='quest_base_price_gt_0',
            ),
            models.CheckConstraint(
                check=Q(extra_player_price__gte=0),
                name='quest_extra_price_gte_0',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.title} ({self.genre.name}, {self.age_rating.code})'


class TariffSlot(models.Model):
    """Тарифный слот по времени суток."""

    name = models.CharField(max_length=60, unique=True, verbose_name='Название тарифа')
    start_time = models.TimeField(verbose_name='Начало действия')
    end_time = models.TimeField(verbose_name='Окончание действия')
    price_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.50')), MaxValueValidator(Decimal('3.00'))],
        verbose_name='Коэффициент цены',
    )
    description = models.CharField(max_length=200, blank=True, verbose_name='Описание')

    class Meta:
        verbose_name = 'Тарифный слот'
        verbose_name_plural = 'Тарифные слоты'
        ordering = ['start_time']

    def __str__(self) -> str:
        return f'{self.name} (×{self.price_multiplier})'


class SessionSchedule(models.Model):
    """Сетка сеансов для квест-комнаты."""

    quest = models.ForeignKey(
        QuestRoom,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name='Квест-комната',
    )
    tariff_slot = models.ForeignKey(
        TariffSlot,
        on_delete=models.PROTECT,
        related_name='sessions',
        verbose_name='Тарифный слот',
    )
    date = models.DateField(verbose_name='Дата сеанса')
    start_time = models.TimeField(verbose_name='Время начала')
    end_time = models.TimeField(verbose_name='Время окончания')
    is_blocked = models.BooleanField(
        default=False,
        verbose_name='Заблокирован (тех. перерыв или обслуживание)',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    class Meta:
        verbose_name = 'Сеанс в расписании'
        verbose_name_plural = 'Расписание сеансов'
        ordering = ['date', 'start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['quest', 'date', 'start_time'],
                name='unique_quest_session_slot',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.quest.title} — {self.date:%d.%m.%Y} {self.start_time:%H:%M}'


class Team(models.Model):
    """Команда игроков."""

    name = models.CharField(max_length=100, verbose_name='Название команды')
    captain = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teams',
        verbose_name='Капитан команды',
    )
    contact_phone = models.CharField(max_length=20, verbose_name='Телефон для связи')
    default_players_count = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(2), MaxValueValidator(16)],
        verbose_name='Обычный размер команды',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Команда'
        verbose_name_plural = 'Команды'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['captain', 'name'],
                name='unique_captain_team_name',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.name} (капитан: {self.captain.username})'


class ExtraOption(models.Model):
    """Дополнительная услуга к бронированию (актёр, лаунж-зона и т.д.)."""

    TYPE_ACTOR = 'actor'
    TYPE_LOUNGE = 'lounge'
    TYPE_PHOTO = 'photo'
    TYPE_OTHER = 'other'

    TYPE_CHOICES = [
        (TYPE_ACTOR, 'Актёр-аниматор'),
        (TYPE_LOUNGE, 'Лаунж-зона для чаепития'),
        (TYPE_PHOTO, 'Фотосессия'),
        (TYPE_OTHER, 'Прочая услуга'),
    ]

    name = models.CharField(max_length=120, unique=True, verbose_name='Название услуги')
    option_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_OTHER,
        verbose_name='Тип услуги',
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Стоимость, ₽',
    )
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Доступна для заказа')

    class Meta:
        verbose_name = 'Дополнительная опция'
        verbose_name_plural = 'Дополнительные опции'
        ordering = ['option_type', 'name']

    def __str__(self) -> str:
        return f'{self.name} ({self.price} ₽)'


class Booking(models.Model):
    """Бронирование сеанса квест-комнаты."""

    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидает подтверждения'),
        (STATUS_CONFIRMED, 'Подтверждено'),
        (STATUS_COMPLETED, 'Игра завершена'),
        (STATUS_CANCELLED, 'Отменено'),
    ]

    booking_code = models.CharField(
        max_length=24,
        unique=True,
        verbose_name='Код бронирования',
    )
    quest = models.ForeignKey(
        QuestRoom,
        on_delete=models.PROTECT,
        related_name='bookings',
        verbose_name='Квест-комната',
    )
    session = models.ForeignKey(
        SessionSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        verbose_name='Слот расписания',
    )
    tariff_slot = models.ForeignKey(
        TariffSlot,
        on_delete=models.PROTECT,
        related_name='bookings',
        verbose_name='Тарифный слот',
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name='bookings',
        verbose_name='Команда',
    )
    captain = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='bookings',
        verbose_name='Капитан (заказчик)',
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operated_bookings',
        verbose_name='Оператор квеста',
    )
    booking_date = models.DateField(verbose_name='Дата игры')
    start_time = models.TimeField(verbose_name='Время начала')
    end_time = models.TimeField(verbose_name='Время окончания')
    players_count = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2), MaxValueValidator(16)],
        verbose_name='Количество игроков',
    )
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Базовая стоимость (по тарифу), ₽',
    )
    extra_players_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Доплата за игроков сверх 4, ₽',
    )
    extras_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Сумма доп. услуг, ₽',
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Итоговая стоимость, ₽',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Статус',
    )
    notes = models.TextField(blank=True, verbose_name='Пожелания команды')
    extra_options = models.ManyToManyField(
        ExtraOption,
        through='BookingExtraOption',
        related_name='bookings',
        blank=True,
        verbose_name='Дополнительные опции',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Бронирование'
        verbose_name_plural = 'Бронирования'
        ordering = ['-booking_date', '-start_time']
        constraints = [
            models.CheckConstraint(
                check=Q(players_count__gte=2),
                name='booking_players_gte_2',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.booking_code}: {self.quest.title} ({self.booking_date:%d.%m.%Y} {self.start_time:%H:%M})'


class BookingExtraOption(models.Model):
    """Связующая таблица (многие-ко-многим) между бронированием и доп. опциями."""

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='booking_extras',
        verbose_name='Бронирование',
    )
    option = models.ForeignKey(
        ExtraOption,
        on_delete=models.PROTECT,
        related_name='booking_extras',
        verbose_name='Дополнительная опция',
    )
    quantity = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name='Количество',
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Цена на момент бронирования, ₽',
    )
    assigned_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actor_assignments',
        verbose_name='Назначенный актёр',
    )

    class Meta:
        verbose_name = 'Опция в бронировании'
        verbose_name_plural = 'Опции в бронированиях'
        constraints = [
            models.UniqueConstraint(
                fields=['booking', 'option'],
                name='unique_booking_extra_option',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.booking.booking_code} — {self.option.name} ×{self.quantity}'


class GameResult(models.Model):
    """Результат прохождения квеста для таблицы рекордов."""

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='result',
        verbose_name='Бронирование',
    )
    quest = models.ForeignKey(
        QuestRoom,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='Квест-комната',
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='Команда',
    )
    completion_minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(5), MaxValueValidator(240)],
        verbose_name='Время прохождения (мин)',
    )
    hints_used = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        verbose_name='Использовано подсказок',
    )
    score = models.PositiveIntegerField(verbose_name='Итоговый рейтинг')
    team_photo = models.ImageField(
        upload_to='results/',
        blank=True,
        null=True,
        verbose_name='Фото команды после игры',
    )
    played_at = models.DateField(verbose_name='Дата прохождения')
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_results',
        verbose_name='Зафиксировал оператор',
    )

    class Meta:
        verbose_name = 'Результат игры'
        verbose_name_plural = 'Таблица рекордов'
        ordering = ['-score', 'completion_minutes', 'hints_used']

    def __str__(self) -> str:
        return f'{self.team.name} — {self.quest.title}: {self.completion_minutes} мин ({self.score} б.)'


class Review(models.Model):
    """Отзыв игрока о квест-комнате."""

    quest = models.ForeignKey(
        QuestRoom,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Квест-комната',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Автор',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Оценка (1–5)',
    )
    comment = models.TextField(max_length=1500, verbose_name='Текст отзыва')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата публикации')
    is_published = models.BooleanField(default=True, verbose_name='Опубликован')

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=Q(rating__gte=1, rating__lte=5),
                name='review_rating_1_5',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.author.username} → {self.quest.title} ({self.rating}/5)'
