/**
 * Клиентская логика QuestHub (Vanilla JS без фреймворков):
 * 1. Мобильное меню-бургер
 * 2. Клиентская валидация форм перед отправкой
 * 3. Fetch-запросы к JSON API (расчёт цены и сетка сеансов)
 * 4. Отрисовка диаграммы на Canvas на странице аналитики
 */
document.addEventListener('DOMContentLoaded', () => {
  initMobileNav();
  initClientValidation();
  initBookingPricePreview();
  initQuestSlotsLoader();
  initAnalyticsChart();
});

function initMobileNav() {
  const toggleBtn = document.getElementById('nav-toggle-btn');
  const navMenu = document.getElementById('main-nav');
  if (!toggleBtn || !navMenu) return;

  toggleBtn.addEventListener('click', () => {
    const isOpen = navMenu.classList.toggle('is-open');
    toggleBtn.setAttribute('aria-expanded', String(isOpen));
  });
}

function initClientValidation() {
  const forms = document.querySelectorAll('form[data-validate="true"]');
  const phoneRegex = /^\+?[78][\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}$/;

  forms.forEach((form) => {
    form.addEventListener('submit', (event) => {
      let hasErrors = false;
      form.querySelectorAll('.js-client-error').forEach((el) => el.remove());

      const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
      inputs.forEach((input) => {
        if (!input.value.trim()) {
          showClientError(input, 'Это поле обязательно для заполнения.');
          hasErrors = true;
        }
      });

      const phoneInputs = form.querySelectorAll('input[name="phone"], input[name="contact_phone"]');
      phoneInputs.forEach((input) => {
        const val = input.value.trim();
        if (val && !phoneRegex.test(val)) {
          showClientError(input, 'Введите телефон в формате +7 900 000-00-00.');
          hasErrors = true;
        }
      });

      const emailInputs = form.querySelectorAll('input[type="email"]');
      emailInputs.forEach((input) => {
        const val = input.value.trim();
        if (val && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
          showClientError(input, 'Введите корректный адрес электронной почты.');
          hasErrors = true;
        }
      });

      if (hasErrors) {
        event.preventDefault();
      }
    });
  });
}

function showClientError(input, message) {
  const err = document.createElement('div');
  err.className = 'field-errors js-client-error';
  err.textContent = message;
  input.insertAdjacentElement('afterend', err);
}

function initBookingPricePreview() {
  const container = document.getElementById('booking-preview-box');
  if (!container) return;

  const apiUrl = container.dataset.apiUrl;
  const dateInput = document.getElementById('id_booking_date');
  const timeInput = document.getElementById('id_start_time');
  const playersInput = document.getElementById('id_players_count');
  const optionBoxes = document.querySelectorAll('input[name="extra_options"]');
  const spinner = document.getElementById('preview-spinner');
  const resultEl = document.getElementById('preview-result');

  if (!apiUrl || !dateInput || !timeInput || !playersInput || !resultEl) return;

  const updatePreview = async () => {
    const selectedOptions = Array.from(optionBoxes)
      .filter((cb) => cb.checked)
      .map((cb) => cb.value)
      .join(',');

    const params = new URLSearchParams({
      date: dateInput.value || '',
      time: timeInput.value || '',
      players: playersInput.value || '4',
      options: selectedOptions,
    });

    if (spinner) spinner.classList.add('is-active');
    try {
      const response = await fetch(`${apiUrl}?${params.toString()}`);
      const data = await response.json();
      if (!response.ok) {
        resultEl.textContent = data.error || 'Не удалось рассчитать стоимость.';
        return;
      }
      const statusText = data.available ? 'Свободно' : data.conflict_reason;
      resultEl.innerHTML = '';

      const summary = document.createElement('p');
      summary.innerHTML =
        `<strong>Тариф:</strong> ${escapeHtml(data.tariff_name)} (×${escapeHtml(data.tariff_multiplier)})<br>` +
        `<strong>Базовая цена (2–4 чел.):</strong> ${escapeHtml(data.base_price)} ₽<br>` +
        `<strong>Доплата за доп. игроков (${escapeHtml(String(data.extra_players_count))} чел.):</strong> ${escapeHtml(data.extra_players_fee)} ₽<br>` +
        `<strong>Доп. опции:</strong> ${escapeHtml(data.extras_total)} ₽<br>` +
        `<strong>Итого:</strong> <span class="price-tag">${escapeHtml(data.total_price)} ₽</span>`;

      const availability = document.createElement('p');
      availability.className = data.available ? 'badge badge-available' : 'badge badge-busy';
      availability.textContent = statusText;

      resultEl.appendChild(summary);
      resultEl.appendChild(availability);
    } catch (err) {
      resultEl.textContent = 'Ошибка соединения при расчёте стоимости.';
    } finally {
      if (spinner) spinner.classList.remove('is-active');
    }
  };

  [dateInput, timeInput, playersInput].forEach((el) => {
    el.addEventListener('change', updatePreview);
  });
  optionBoxes.forEach((cb) => cb.addEventListener('change', updatePreview));
  updatePreview();
}

function initQuestSlotsLoader() {
  const datePicker = document.getElementById('slots-date-picker');
  const slotsContainer = document.getElementById('slots-grid-container');
  const spinner = document.getElementById('slots-spinner');
  if (!datePicker || !slotsContainer) return;

  const apiUrl = datePicker.dataset.apiUrl;
  const bookUrl = datePicker.dataset.bookUrl;

  datePicker.addEventListener('change', async () => {
    if (!datePicker.value) return;
    if (spinner) spinner.classList.add('is-active');
    try {
      const response = await fetch(`${apiUrl}?date=${encodeURIComponent(datePicker.value)}`);
      const data = await response.json();
      if (!response.ok || !Array.isArray(data.slots)) return;

      slotsContainer.innerHTML = '';
      data.slots.forEach((slot) => {
        const card = document.createElement('div');
        card.className = slot.available ? 'slot-item' : 'slot-item is-busy';

        const title = document.createElement('strong');
        title.textContent = slot.time;

        const meta = document.createElement('span');
        meta.textContent = `${slot.tariff} — ${slot.price} ₽`;

        const badge = document.createElement('span');
        badge.className = slot.available ? 'badge badge-available' : 'badge badge-busy';
        badge.textContent = slot.available ? 'Свободно' : slot.reason;

        card.appendChild(title);
        card.appendChild(meta);
        card.appendChild(badge);

        if (slot.available && bookUrl) {
          const link = document.createElement('a');
          link.className = 'btn btn-primary btn-sm';
          link.href = `${bookUrl}?date=${encodeURIComponent(data.date)}&time=${encodeURIComponent(slot.time)}`;
          link.textContent = 'Выбрать';
          card.appendChild(link);
        }

        slotsContainer.appendChild(card);
      });
    } finally {
      if (spinner) spinner.classList.remove('is-active');
    }
  });
}

function initAnalyticsChart() {
  const canvas = document.getElementById('genre-chart');
  const dataScript = document.getElementById('genre-stats-data');
  if (!canvas || !dataScript) return;

  let stats = [];
  try {
    stats = JSON.parse(dataScript.textContent);
  } catch (e) {
    return;
  }
  if (!stats.length) return;

  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  const maxBookings = Math.max(...stats.map((s) => s.bookings_total), 1);
  const paddingLeft = 48;
  const paddingBottom = 42;
  const chartHeight = height - paddingBottom - 20;
  const barWidth = Math.max(24, Math.floor((width - paddingLeft - 20) / stats.length) - 16);

  ctx.font = '12px system-ui, sans-serif';
  ctx.fillStyle = '#0f172a';
  ctx.strokeStyle = '#cbd5e1';
  ctx.beginPath();
  ctx.moveTo(paddingLeft, 15);
  ctx.lineTo(paddingLeft, height - paddingBottom);
  ctx.lineTo(width - 10, height - paddingBottom);
  ctx.stroke();

  stats.forEach((item, idx) => {
    const x = paddingLeft + 14 + idx * (barWidth + 16);
    const barH = Math.round((item.bookings_total / maxBookings) * chartHeight);
    const y = height - paddingBottom - barH;

    ctx.fillStyle = '#4338ca';
    ctx.fillRect(x, y, barWidth, barH);

    ctx.fillStyle = '#0f172a';
    ctx.fillText(String(item.bookings_total), x + barWidth / 2 - 4, y - 6);
    ctx.fillText(item.name.slice(0, 10), x, height - 16);
  });
}

function escapeHtml(str) {
  return str
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
