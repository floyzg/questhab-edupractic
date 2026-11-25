"""Формы Django с серверной валидацией, clean_<field> и межпольными проверками clean."""
import re
from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import (
    Booking,
    ExtraOption,
    GameResult,
    QuestRoom,
    Review,
    Team,
    UserProfile,
)
from .services import find_schedule_conflict, validate_uploaded_image

PHONE_PATTERN = re.compile(r'^\+?[78][\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$')


class UserRegistrationForm(UserCreationForm):
    """Форма регистрации нового игрока с проверкой уникальности email и формата телефона."""

    email = forms.EmailField(
        required=True,
        label='Электронная почта',
        help_text='На этот адрес придёт подтверждение бронирования.',
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label='Имя',
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        label='Телефон',
        help_text='Формат: +7 900 000-00-00',
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'email', 'phone', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Пользователь с такой электронной почтой уже зарегистрирован.')
        return email

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if not PHONE_PATTERN.match(phone):
            raise ValidationError('Введите телефон в формате +7 900 000-00-00.')
        return phone


class ProfileUpdateForm(forms.ModelForm):
    """Форма редактирования профиля пользователя с проверкой аватара."""

    class Meta:
        model = UserProfile
        fields = ('phone', 'avatar')

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone and not PHONE_PATTERN.match(phone):
            raise ValidationError('Введите телефон в формате +7 900 000-00-00.')
        return phone

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and hasattr(avatar, 'content_type'):
            validate_uploaded_image(avatar)
        return avatar


class TeamForm(forms.ModelForm):
    """Форма создания и редактирования команды игроков."""

    class Meta:
        model = Team
        fields = ('name', 'contact_phone', 'default_players_count')
        help_texts = {
            'contact_phone': 'Формат: +7 900 000-00-00',
            'default_players_count': 'Базовая цена квестов рассчитана на 2–4 человека.',
        }

    def __init__(self, *args, captain=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.captain = captain

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise ValidationError('Название команды должно содержать не менее 2 символов.')
        if self.captain is not None:
            qs = Team.objects.filter(captain=self.captain, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('У вас уже есть команда с таким названием.')
        return name

    def clean_contact_phone(self):
        phone = self.cleaned_data['contact_phone'].strip()
        if not PHONE_PATTERN.match(phone):
            raise ValidationError('Введите телефон в формате +7 900 000-00-00.')
        return phone


class QuestRoomForm(forms.ModelForm):
    """Форма создания и редактирования квест-комнаты (для администратора и оператора)."""

    class Meta:
        model = QuestRoom
        fields = (
            'title',
            'slug',
            'genre',
            'age_rating',
            'description',
            'fear_level',
            'difficulty',
            'duration_minutes',
            'min_players',
            'max_players',
            'base_price',
            'extra_player_price',
            'image',
            'is_active',
        )

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'content_type'):
            validate_uploaded_image(image)
        return image

    def clean(self):
        cleaned_data = super().clean()
        min_p = cleaned_data.get('min_players')
        max_p = cleaned_data.get('max_players')
        if min_p is not None and max_p is not None and max_p < min_p:
            self.add_error(
                'max_players',
                'Максимальное число игроков не может быть меньше минимального.',
            )
        return cleaned_data


class BookingForm(forms.ModelForm):
    """Форма бронирования сеанса квест-комнаты с проверкой 30-мин перерыва и вместимости."""

    extra_options = forms.ModelMultipleChoiceField(
        queryset=ExtraOption.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Дополнительные опции',
    )

    class Meta:
        model = Booking
        fields = ('team', 'booking_date', 'start_time', 'players_count', 'extra_options', 'notes')
        widgets = {
            'booking_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, quest=None, captain=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.quest = quest or getattr(self.instance, 'quest', None)
        self.captain = captain
        if captain is not None:
            self.fields['team'].queryset = Team.objects.filter(captain=captain)
        if self.quest is not None:
            self.fields['players_count'].help_text = (
                f'От {self.quest.min_players} до {self.quest.max_players} чел. '
                f'(до 4 чел. включено в базовую цену, сверх 4 — +{self.quest.extra_player_price} ₽/чел.)'
            )

    def clean_booking_date(self):
        b_date = self.cleaned_data['booking_date']
        if b_date < date.today():
            raise ValidationError('Нельзя забронировать сеанс на прошедшую дату.')
        return b_date

    def clean(self):
        cleaned_data = super().clean()
        b_date = cleaned_data.get('booking_date')
        s_time = cleaned_data.get('start_time')
        players = cleaned_data.get('players_count')

        if self.quest is not None and players is not None:
            if players < self.quest.min_players or players > self.quest.max_players:
                self.add_error(
                    'players_count',
                    f'Для этого квеста допустимо от {self.quest.min_players} '
                    f'до {self.quest.max_players} участников.',
                )

        if self.quest is not None and b_date is not None and s_time is not None:
            conflict = find_schedule_conflict(
                self.quest,
                b_date,
                s_time,
                exclude_booking_id=self.instance.pk,
            )
            if conflict is not None:
                self.add_error(
                    'start_time',
                    f'Слот недоступен: пересечение с сеансом {conflict.start_time:%H:%M}–'
                    f'{conflict.end_time:%H:%M} или техническим перерывом 30 минут.',
                )
        return cleaned_data


class ReviewForm(forms.ModelForm):
    """Форма публикации отзыва о квест-комнате."""

    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {
            'rating': forms.Select(choices=[(i, f'{i} из 5') for i in range(5, 0, -1)]),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_comment(self):
        text = self.cleaned_data['comment'].strip()
        if len(text) < 10:
            raise ValidationError('Напишите чуть подробнее — минимум 10 символов.')
        return text


class GameResultForm(forms.ModelForm):
    """Форма фиксации результата прохождения квеста оператором."""

    class Meta:
        model = GameResult
        fields = ('completion_minutes', 'hints_used', 'team_photo')

    def clean_team_photo(self):
        photo = self.cleaned_data.get('team_photo')
        if photo and hasattr(photo, 'content_type'):
            validate_uploaded_image(photo)
        return photo
