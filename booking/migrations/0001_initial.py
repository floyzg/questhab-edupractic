# Generated manually to match booking/models.py for Django 4.2+
from decimal import Decimal
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AgeRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=10, unique=True, verbose_name='Рейтинг')),
                ('min_age', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(21)], verbose_name='Минимальный возраст')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='Пояснение')),
            ],
            options={
                'verbose_name': 'Возрастной рейтинг',
                'verbose_name_plural': 'Возрастные рейтинги',
                'ordering': ['min_age'],
            },
        ),
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('booking_code', models.CharField(max_length=24, unique=True, verbose_name='Код бронирования')),
                ('booking_date', models.DateField(verbose_name='Дата игры')),
                ('start_time', models.TimeField(verbose_name='Время начала')),
                ('end_time', models.TimeField(verbose_name='Время окончания')),
                ('players_count', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(2), django.core.validators.MaxValueValidator(16)], verbose_name='Количество игроков')),
                ('base_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Базовая стоимость (по тарифу), ₽')),
                ('extra_players_fee', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Доплата за игроков сверх 4, ₽')),
                ('extras_total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Сумма доп. услуг, ₽')),
                ('total_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Итоговая стоимость, ₽')),
                ('status', models.CharField(choices=[('pending', 'Ожидает подтверждения'), ('confirmed', 'Подтверждено'), ('completed', 'Игра завершена'), ('cancelled', 'Отменено')], default='pending', max_length=20, verbose_name='Статус')),
                ('notes', models.TextField(blank=True, verbose_name='Пожелания команды')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('captain', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bookings', to=settings.AUTH_USER_MODEL, verbose_name='Капитан (заказчик)')),
                ('operator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='operated_bookings', to=settings.AUTH_USER_MODEL, verbose_name='Оператор квеста')),
            ],
            options={
                'verbose_name': 'Бронирование',
                'verbose_name_plural': 'Бронирования',
                'ordering': ['-booking_date', '-start_time'],
            },
        ),
        migrations.CreateModel(
            name='ExtraOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True, verbose_name='Название услуги')),
                ('option_type', models.CharField(choices=[('actor', 'Актёр-аниматор'), ('lounge', 'Лаунж-зона для чаепития'), ('photo', 'Фотосессия'), ('other', 'Прочая услуга')], default='other', max_length=20, verbose_name='Тип услуги')),
                ('price', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))], verbose_name='Стоимость, ₽')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('is_active', models.BooleanField(default=True, verbose_name='Доступна для заказа')),
            ],
            options={
                'verbose_name': 'Дополнительная опция',
                'verbose_name_plural': 'Дополнительные опции',
                'ordering': ['option_type', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Genre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, unique=True, verbose_name='Название жанра')),
                ('slug', models.SlugField(max_length=90, unique=True, verbose_name='URL-метка')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
            ],
            options={
                'verbose_name': 'Жанр',
                'verbose_name_plural': 'Жанры',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='QuestRoom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150, verbose_name='Название квеста')),
                ('slug', models.SlugField(max_length=160, unique=True, verbose_name='URL-метка')),
                ('description', models.TextField(verbose_name='Описание сюжета')),
                ('fear_level', models.PositiveSmallIntegerField(default=2, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Уровень страха (1–5)')),
                ('difficulty', models.PositiveSmallIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Сложность (1–5)')),
                ('duration_minutes', models.PositiveSmallIntegerField(default=60, validators=[django.core.validators.MinValueValidator(30), django.core.validators.MaxValueValidator(180)], verbose_name='Длительность (мин)')),
                ('min_players', models.PositiveSmallIntegerField(default=2, validators=[django.core.validators.MinValueValidator(2), django.core.validators.MaxValueValidator(12)], verbose_name='Минимум игроков')),
                ('max_players', models.PositiveSmallIntegerField(default=6, validators=[django.core.validators.MinValueValidator(2), django.core.validators.MaxValueValidator(16)], verbose_name='Максимум игроков')),
                ('base_price', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('100.00'))], verbose_name='Базовая цена (2–4 игрока), ₽')),
                ('extra_player_price', models.DecimalField(decimal_places=2, default=Decimal('700.00'), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))], verbose_name='Доплата за доп. игрока сверх 4, ₽')),
                ('image', models.ImageField(blank=True, null=True, upload_to='quests/', verbose_name='Обложка квеста')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен в каталоге')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')),
                ('age_rating', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='quests', to='booking.agerating', verbose_name='Возрастной рейтинг')),
                ('genre', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='quests', to='booking.genre', verbose_name='Жанр')),
            ],
            options={
                'verbose_name': 'Квест-комната',
                'verbose_name_plural': 'Квест-комнаты',
                'ordering': ['title'],
            },
        ),
        migrations.CreateModel(
            name='TariffSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60, unique=True, verbose_name='Название тарифа')),
                ('start_time', models.TimeField(verbose_name='Начало действия')),
                ('end_time', models.TimeField(verbose_name='Окончание действия')),
                ('price_multiplier', models.DecimalField(decimal_places=2, default=Decimal('1.00'), max_digits=4, validators=[django.core.validators.MinValueValidator(Decimal('0.50')), django.core.validators.MaxValueValidator(Decimal('3.00'))], verbose_name='Коэффициент цены')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='Описание')),
            ],
            options={
                'verbose_name': 'Тарифный слот',
                'verbose_name_plural': 'Тарифные слоты',
                'ordering': ['start_time'],
            },
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('captain', 'Игрок (капитан команды)'), ('operator', 'Оператор квеста'), ('actor', 'Актёр-аниматор'), ('admin', 'Администратор локации')], default='captain', max_length=20, verbose_name='Роль в системе')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='Контактный телефон')),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='avatars/', verbose_name='Аватар')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Профиль пользователя',
                'verbose_name_plural': 'Профили пользователей',
                'ordering': ['user__username'],
            },
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название команды')),
                ('contact_phone', models.CharField(max_length=20, verbose_name='Телефон для связи')),
                ('default_players_count', models.PositiveSmallIntegerField(default=4, validators=[django.core.validators.MinValueValidator(2), django.core.validators.MaxValueValidator(16)], verbose_name='Обычный размер команды')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('captain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teams', to=settings.AUTH_USER_MODEL, verbose_name='Капитан команды')),
            ],
            options={
                'verbose_name': 'Команда',
                'verbose_name_plural': 'Команды',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='SessionSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Дата сеанса')),
                ('start_time', models.TimeField(verbose_name='Время начала')),
                ('end_time', models.TimeField(verbose_name='Время окончания')),
                ('is_blocked', models.BooleanField(default=False, verbose_name='Заблокирован (тех. перерыв или обслуживание)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('quest', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='booking.questroom', verbose_name='Квест-комната')),
                ('tariff_slot', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sessions', to='booking.tariffslot', verbose_name='Тарифный слот')),
            ],
            options={
                'verbose_name': 'Сеанс в расписании',
                'verbose_name_plural': 'Расписание сеансов',
                'ordering': ['date', 'start_time'],
            },
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Оценка (1–5)')),
                ('comment', models.TextField(max_length=1500, verbose_name='Текст отзыва')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата публикации')),
                ('is_published', models.BooleanField(default=True, verbose_name='Опубликован')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('quest', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='booking.questroom', verbose_name='Квест-комната')),
            ],
            options={
                'verbose_name': 'Отзыв',
                'verbose_name_plural': 'Отзывы',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='GameResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completion_minutes', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(240)], verbose_name='Время прохождения (мин)')),
                ('hints_used', models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(20)], verbose_name='Использовано подсказок')),
                ('score', models.PositiveIntegerField(verbose_name='Итоговый рейтинг')),
                ('team_photo', models.ImageField(blank=True, null=True, upload_to='results/', verbose_name='Фото команды после игры')),
                ('played_at', models.DateField(verbose_name='Дата прохождения')),
                ('booking', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='result', to='booking.booking', verbose_name='Бронирование')),
                ('quest', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='booking.questroom', verbose_name='Квест-комната')),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_results', to=settings.AUTH_USER_MODEL, verbose_name='Зафиксировал оператор')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='booking.team', verbose_name='Команда')),
            ],
            options={
                'verbose_name': 'Результат игры',
                'verbose_name_plural': 'Таблица рекордов',
                'ordering': ['-score', 'completion_minutes', 'hints_used'],
            },
        ),
        migrations.CreateModel(
            name='BookingExtraOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)], verbose_name='Количество')),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Цена на момент бронирования, ₽')),
                ('assigned_actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='actor_assignments', to=settings.AUTH_USER_MODEL, verbose_name='Назначенный актёр')),
                ('booking', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='booking_extras', to='booking.booking', verbose_name='Бронирование')),
                ('option', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='booking_extras', to='booking.extraoption', verbose_name='Дополнительная опция')),
            ],
            options={
                'verbose_name': 'Опция в бронировании',
                'verbose_name_plural': 'Опции в бронированиях',
            },
        ),
        migrations.AddField(
            model_name='booking',
            name='extra_options',
            field=models.ManyToManyField(blank=True, related_name='bookings', through='booking.BookingExtraOption', to='booking.extraoption', verbose_name='Дополнительные опции'),
        ),
        migrations.AddField(
            model_name='booking',
            name='quest',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bookings', to='booking.questroom', verbose_name='Квест-комната'),
        ),
        migrations.AddField(
            model_name='booking',
            name='session',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings', to='booking.sessionschedule', verbose_name='Слот расписания'),
        ),
        migrations.AddField(
            model_name='booking',
            name='tariff_slot',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bookings', to='booking.tariffslot', verbose_name='Тарифный слот'),
        ),
        migrations.AddField(
            model_name='booking',
            name='team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bookings', to='booking.team', verbose_name='Команда'),
        ),
        migrations.AddConstraint(
            model_name='team',
            constraint=models.UniqueConstraint(fields=('captain', 'name'), name='unique_captain_team_name'),
        ),
        migrations.AddConstraint(
            model_name='sessionschedule',
            constraint=models.UniqueConstraint(fields=('quest', 'date', 'start_time'), name='unique_quest_session_slot'),
        ),
        migrations.AddConstraint(
            model_name='review',
            constraint=models.CheckConstraint(check=models.Q(('rating__gte', 1), ('rating__lte', 5)), name='review_rating_1_5'),
        ),
        migrations.AddConstraint(
            model_name='questroom',
            constraint=models.CheckConstraint(check=models.Q(('min_players__gte', 2)), name='quest_min_players_gte_2'),
        ),
        migrations.AddConstraint(
            model_name='questroom',
            constraint=models.CheckConstraint(check=models.Q(('max_players__gte', models.F('min_players'))), name='quest_max_gte_min_players'),
        ),
        migrations.AddConstraint(
            model_name='questroom',
            constraint=models.CheckConstraint(check=models.Q(('fear_level__gte', 1), ('fear_level__lte', 5)), name='quest_fear_level_1_5'),
        ),
        migrations.AddConstraint(
            model_name='questroom',
            constraint=models.CheckConstraint(check=models.Q(('difficulty__gte', 1), ('difficulty__lte', 5)), name='quest_difficulty_1_5'),
        ),
        migrations.AddConstraint(
            model_name='questroom',
            constraint=models.CheckConstraint(check=models.Q(('base_price__gt', 0)), name='quest_base_price_gt_0'),
        ),
        migrations.AddConstraint(
            model_name='questroom',
            constraint=models.CheckConstraint(check=models.Q(('extra_player_price__gte', 0)), name='quest_extra_price_gte_0'),
        ),
        migrations.AddConstraint(
            model_name='bookingextraoption',
            constraint=models.UniqueConstraint(fields=('booking', 'option'), name='unique_booking_extra_option'),
        ),
        migrations.AddConstraint(
            model_name='booking',
            constraint=models.CheckConstraint(check=models.Q(('players_count__gte', 2)), name='booking_players_gte_2'),
        ),
    ]
