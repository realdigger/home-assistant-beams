# BEAMS Light

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/realdigger/home-assistant-beams.svg)](https://github.com/realdigger/home-assistant-beams/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Неофициальная пользовательская интеграция Home Assistant для аквариумных светильников BEAMS.

Проект не связан с BeautifulReef или BEAMS и не поддерживается ими.

English: [README.md](README.md)

## Возможности

- Индикатор состояния основного света без управления.
- Переключатели ручного, автоматического и сервисного режимов.
- Общая яркость и управление десятью спектральными каналами.
- Выбор сохранённого спектра и кнопка обновления галереи контроллера.
- Настраиваемый интервал опроса в простое с частым опросом после действий пользователя.
- Настраиваемая длительность ручного режима от одного до шести часов и сенсор оставшегося времени.
- Сенсор DLI текущего дневного цикла.
- Сенсоры PPFD на высоте `25 см`, `35 см` и `45 см`.
- Расчётная мощность, модель, время работы, точка дневного цикла и равномерность освещения.
- Диагностические данные: ID контроллера, число сборок, версии TrueSpectrum, OS, ядра и LCS.
- Встроенные Lovelace-карточки: цветные слайдеры каналов и текущий спектр.
- Сервисы для задания каналов, переключения режима, применения спектра и обновления галереи.

## Поддерживаемые устройства

Проверено со светильником:

- BEAMS 2 PRO R-8.

Другие светильники BEAMS могут работать, если используют тот же локальный API контроллера.

## Установка

### HACS

1. Откройте HACS.
2. Перейдите в **Integrations**.
3. Добавьте пользовательский репозиторий:
   - репозиторий: `https://github.com/realdigger/home-assistant-beams`;
   - категория: `Integration`.
4. Установите **BEAMS Light**.
5. Перезапустите Home Assistant и один раз обновите страницу браузера.

### Вручную

Скопируйте папку интеграции в Home Assistant:

```text
/config/custom_components/beams_light/
```

Затем перезапустите Home Assistant.

## Настройка

Добавьте интеграцию через:

```text
Настройки → Устройства и службы → Добавить интеграцию → BEAMS LED Light
```

Примеры URL контроллера:

```text
http://beams2.sensors.local
http://10.11.1.1
http://192.168.1.55
```

Настройка YAML не требуется.

### Интервал опроса

Откройте страницу **«Настроить»** интеграции, чтобы задать интервал опроса в простое (от 5 до 3600 секунд, по умолчанию — 10 секунд). После действия пользователя контроллер опрашивается каждые 3 секунды в течение минуты, затем возвращается к заданному интервалу.

## Сущности

Во всех примерах `<device_id>` — идентификатор, созданный Home Assistant для вашего светильника.

### Индикатор света

```text
binary_sensor.<device_id>_light
```

Показывает, включён ли хотя бы один канал. Это только индикатор и он не изменяет состояние контроллера.

### Режим и спектр

```text
switch.<device_id>_manual_mode
switch.<device_id>_service_mode
select.<device_id>_spectrum
select.<device_id>_manual_duration
```

Включите `switch.<device_id>_manual_mode` для ручного управления; выключите его для автоматического дневного цикла.

В автоматическом режиме элементы показывают текущие уровни, но интеграция отклоняет попытки их изменить. Селектор спектра показывает `Авто: дневной цикл`: контроллер интерполирует точки цикла, поэтому единого имени спектра нет. Сервисный режим устанавливает все каналы на 20 %, а его выключение возвращает контроллер в Auto.

Селектор спектра применяет сохранённые спектры из галереи контроллера.

### Яркость и каналы

```text
number.<device_id>_brightness
number.<device_id>_ch1_<led_type>
...
number.<device_id>_ch10_<led_type>
```

Значения отображаются в диапазоне `0–100 %`. Общая яркость сохраняет относительные уровни каналов. Для изменения значений сначала включите ручной режим.

Идентификаторы сущностей включают ID устройства и тип светодиода от контроллера. Используйте фактически созданные для вашего устройства идентификаторы.

У каждого канала есть атрибут `color` из `/api/kit`, который используют пользовательские Lovelace-карточки.

### Сенсоры

```text
sensor.<device_id>_current_cycle_dli
sensor.<device_id>_ppfd_25_cm
sensor.<device_id>_ppfd_35_cm
sensor.<device_id>_ppfd_45_cm
sensor.<device_id>_estimated_power
sensor.<device_id>_light_model
sensor.<device_id>_uptime
sensor.<device_id>_cycle_timepoint
sensor.<device_id>_light_uniformity
sensor.<device_id>_assembly_count
sensor.<device_id>_controller_id
sensor.<device_id>_kernel
sensor.<device_id>_lcs
sensor.<device_id>_operating_system
sensor.<device_id>_user_interface
sensor.<device_id>_manual_mode_remaining
```

Время работы показывается в днях, часах и минутах, а точка дневного цикла — в часах и минутах.

DLI рассчитывается по данным текущего дневного цикла. Для PPFD используются штатные коэффициенты контроллера, а при их отсутствии — данные PPFD комплекта светильника.

На странице устройства показываются Model ID и число сборок. ID контроллера является диагностическим сенсором. Версии подписаны как «Версия ядра», «Версия LCS», «Версия OS» и «Версия TrueSpectrum».

## Lovelace-карточки

Интеграция автоматически регистрирует две пользовательские карточки. После установки или обновления интеграции один раз обновите страницу Home Assistant, чтобы фронтенд загрузил модуль карточек.

### Цветные каналы

```yaml
type: custom:beams-channel-card
title: Каналы BEAMS
entities:
  - number.<device_id>_ch1_<led_type>
  - number.<device_id>_ch2_<led_type>
  # Добавьте остальные каналы.
```

Слайдеры используют цвет канала от контроллера. В Auto они показывают текущие значения, но интеграция отклоняет попытки изменения.

### Текущий спектр

```yaml
type: custom:beams-spectrum-card
title: Текущий спектр
entity: binary_sensor.<device_id>_light
```

Карточка строит график по текущим уровням каналов и спектральным кривым светодиодов из `GET /api/led`, повторяя расчёт TrueSpectrum.

## Сервисы

### Задать уровни каналов

```yaml
service: beams_light.set_channels
data:
  channels: [20, 20, 20, 20, 20, 20, 20, 20, 20, 20]
```

Значения задаются в процентах. Контроллер переключается в ручной режим.

### Задать режим

```yaml
service: beams_light.set_mode
data:
  mode: manual
```

или:

```yaml
service: beams_light.set_mode
data:
  mode: auto
```

### Применить спектр

```yaml
service: beams_light.apply_spectrum
data:
  spectrum: "Ice and fire #5"
```

или по числовому ID:

```yaml
service: beams_light.apply_spectrum
data:
  spectrum: 5
```

### Обновить галерею спектров

```yaml
service: beams_light.refresh_spectrums
```

## Диагностика

Включите подробное логирование:

```yaml
logger:
  default: warning
  logs:
    custom_components.beams_light: debug
```

Проверьте доступность контроллера:

```bash
curl -v http://beams2.sensors.local/api/channels/get
```

Если DLI или PPFD недоступны, проверьте ответы контроллера:

```text
/api/state/full
/api/kit
/api/math/get
/api/led
```

## Лицензия

Лицензия MIT. См. [LICENSE](LICENSE).
