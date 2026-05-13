# Управление IT активами (IT Assets API)
RESTful API для управления IT-активами компании.


## Технологический стек
| Компонент             | Технология      | Назначение                           |
|:----------------------|:----------------|:-------------------------------------|
| **Язык**              | Python 3.14.3   | Основная логика приложения           |
| **Фреймворк**         | FastAPI         | Высокопроизводительный веб-фреймворк |
| **ORM**               | SQLAlchemy 2.0  | Асинхронное взаимодействие с БД      |
| **База данных**       | PostgreSQL (17) | Хранение данных об активах, типах    |
| **Миграции**          | Alembic         | Инструмент для миграций              |
| **Валидация**         | Pydantic v2     | Валидация входных/выходных данных    |
| **Драйвер БД**        | asyncpg         | Асинхронный драйвер для PostgreSQL   |
| **Контейнеротизация** | Docker Compose  | Инструмент для CI/CD                 |


## Общая структура проекта
```text
project/
├── alembic/                        # Инструмент для миграций
│   ├── versions/    
│   │   └── *.py                    # Файлы миграций
│   └── env.py                      # Скрипт конфигурации миграций
│
├── app/
│   ├── database/    
│   │   ├── crud_*.py               # CRUD операции каждой таблицы
│   │   └── connection.py           # Настройки асинхронного подключения и сессии БД
│   ├── middleware/ 
│   │   └── LoggingMiddleware.py    # Настройки логирования через middleware
│   ├── models/ 
│   │   └── *.py                    # Модели актива с полями и связями
│   ├── routers/    
│   │   └── router_*.py             # Отдельные роутеры под каждую таблицу
│   ├── schemas/                    # Схемы для каждой таблицы
│   │       └── schema/             # Схема конкретной таблицы
│   │           ├── *Create.py      # Схема создания
│   │           ├── *Response.py    # Схема ответа
│   │           ├── *Update.py      # Схема обновления
│   │           └── excel.py        # Работа с excel
│   ├── services/    
│   │   └── excel/                  # Сервис для работы с Excel файлами
│   │       └── import/export.py    # Работа с excel
│   └── main.py                     # Точка входа: создание FastAPI app, подключение роутеров, lifespan, UI, middleware
│
├── xlsx/                           # Папка для Excel файлов (оригинал + для тестов)
│
├── packages/                       # Папка с зависимостями для локальной сборки 
│   └── *.whl/                      # Файлы для сборки
│
├── alembic.ini                     # Основной конфигурационный файл Alembic
├── Dockerfile                      # Файл сборки образа контейнеров
├── docker-compose.yml              # Файл оркестрации многоконтейнерных приложений
├── entrypoint.sh                   # Исполняемый файл последовательного запуска
├── requirements.txt                # Зависимости проекта с указанными версиями
└── README.md                       # Документация проекта
```


## Настройка переменных окружения `.env`
### Обязательные поля:

База данных:
- `DB_USER` = "postgres"
- `DB_PASSWORD` = "postgres"
- `DB_NAME` = "it_assets_db"
- `DB_HOST` = "@postgres" # или при локальном запуске @localhost

### Не обязательные поля:

Секретный ключ для проверки подписи при декодировании токена:
- `JWT_SECRET_KEY` = "geasd$#3neGG!#@J#nnd28n"

> **Примечание**: Перед запуском проверить и настроить порты: `docker-compose.yml`
> 
> Ссылка для подключения к БД формируется автоматически из полей `DB_*`.
> 
> При локальном запуске необходимо использовать @localhost
> 
> Если запуск через Docker, то @postgres
---


## Запуск через Docker 
C пересборкой проекта (Выполняется единожды при первом запуске):
```bash
docker compose up --build
```

При всех последующих запусков:
```bash
docker compose up -d 
```
---


## Документация API
После запуска приложения доступна интерактивная документация:
*   **Swagger:** `http://127.0.0.1:8800/docs`
*   **ReDoc:** `http://127.0.0.1:8800/redoc`
*   **Adminer:** `http://127.0.0.1:7080/` - Просмотр таблиц в веб-интерфейсе
---

## Структура базы данных
Ниже приведено подробное описание таблиц базы данных, используемых в приложении для управления IT-активами на основе моделей (**app.models**).

<details>
<summary>Таблица assets</summary>

| Колонка               | Тип данных  | Описание                                                      |
|:----------------------|:------------|:--------------------------------------------------------------|
| asset_id              | Integer     | Первичный ключ, автоинкремент                                 |
| asset_status          | String(100) | Статус актива (по умолчанию "Приемка ")                       |
| type_domain           | String(100) | Тип домена                                                    |
| asset_type_id         | Integer     | Внешний ключ на `asset_types.asset_type_id`                   |
| inventory_id          | String(50)  | Инвентарный номер (уникальный)                                |
| affixed_inventory_id  | Boolean     | Флаг: инвентарный номер наклеен                               |
| info_storage_location | String(200) | Место хранения информации об активе                           |
| location_id           | Integer     | Внешний ключ на `locations.location_id`                       |
| serial_number         | String(100) | Серийный номер (уникальный)                                   |
| name                  | String(150) | Имя актива (не nullable)                                      |
| date_issue            | Date        | Дата выдачи                                                   |
| date_purchasing       | Date        | Дата покупки                                                  |
| comment               | Text        | Комментарий                                                   |
| price                 | Integer     | Цена                                                          |
| parent_id             | Integer     | Внешний ключ на `assets.asset_id` (для иерархии/комплектации) |
| manufacturer_id       | Integer     | Внешний ключ на `vendors.vendor_id` (производитель)           |
| vendor_id             | Integer     | Внешний ключ на `vendors.vendor_id` (поставщик)               |
| prepared_by           | Integer     | Внешний ключ на `users.user_id` (кто подготовил)              |
| checked_by            | Integer     | Внешний ключ на `users.user_id` (кто проверил)                |
| deleted_at            | DateTime    | Дата мягкого удаления                                         |
| created_at            | DateTime    | Дата создания                                                 |
| updated_at            | DateTime    | Дата обновления                                               |
| software_id           | Integer     | Внешний ключ на `software.software_id`                        |
</details>

<details>
<summary>Таблица asset_classes</summary>

### Таблица: `asset_classes`
| Колонка       | Тип данных  | Описание                                                  |
|:--------------|:------------|:----------------------------------------------------------|
| class_id      | Integer     | Первичный ключ, автоинкремент                             |
| class_name    | String(100) | Название класса (не nullable, индекс)                     |
| class_type_id | Integer     | Внешний ключ на `asset_types.asset_type_id` (не nullable) |
| description   | Text        | Описание класса                                           |
| created_at    | DateTime    | Дата создания                                             |
| updated_at    | DateTime    | Дата обновления                                           |
| created_by    | Integer     | Внешний ключ на `users.user_id` (создатель)               |
| updated_by    | Integer     | Внешний ключ на `users.user_id` (обновивший)              |
</details>

<details>
<summary>Таблица asset_catalog</summary>

### Таблица: `asset_catalog`
| Колонка           | Тип данных | Описание                                                    |
|:------------------|:-----------|:------------------------------------------------------------|
| catalog_id        | Integer    | Первичный ключ, автоинкремент                               |
| class_id          | Integer    | Внешний ключ на `asset_classes.class_id` (не nullable)      |
| model_id          | Integer    | Внешний ключ на `asset_models.model_id` (не nullable)       |
| asset_id          | Integer    | Внешний ключ на `assets.asset_id` (уникальный, не nullable) |
| owner_id          | Integer    | Внешний ключ на `users.user_id` (владелец)                  |
| warehouse_id      | Integer    | Внешний ключ на `warehouses.warehouse_id`                   |
| warranty_end_date | Date       | Дата окончания гарантии                                     |
| created_at        | DateTime   | Дата создания                                               |
| created_by        | Integer    | Внешний ключ на `users.user_id` (создатель записи)          |
</details>

<details>
<summary>Таблица asset_types</summary>

### Таблица: `asset_types`
| Колонка       | Тип данных  | Описание                                |
|:--------------|:------------|:----------------------------------------|
| asset_type_id | Integer     | Первичный ключ, автоинкремент           |
| name          | String(100) | Название типа (не nullable, уникальное) |
</details>

<details>
<summary>Таблица asset_models</summary>

### Таблица: `asset_models`
| Колонка            | Тип данных  | Описание                                                 |
|:-------------------|:------------|:---------------------------------------------------------|
| model_id           | Integer     | Первичный ключ, автоинкремент                            |
| model_name         | String(150) | Название модели (не nullable, индекс)                    |
| class_id           | Integer     | Внешний ключ на `asset_classes.class_id` (не nullable)   |
| description        | Text        | Описание модели                                          |
| is_active          | Boolean     | Флаг активности модели (по умолчанию True)               |
| is_serial_required | Boolean     | Флаг обязательности серийного номера (по умолчанию True) |
| created_at         | DateTime    | Дата создания                                            |
| updated_at         | DateTime    | Дата обновления                                          |
| created_by         | Integer     | Внешний ключ на `users.user_id` (создатель)              |
| updated_by         | Integer     | Внешний ключ на `users.user_id` (обновивший)             |
</details>

<details>
<summary>Таблица companies</summary>

### Таблица: `companies`
| Колонка      | Тип данных  | Описание                                |
|:-------------|:------------|:----------------------------------------|
| company_id   | Integer     | Первичный ключ, автоинкремент           |
| company_name | String(255) | Название компании (не nullable, индекс) |
| gen_director | String(150) | Генеральный директор (ФИО)              |
| phone_number | String(50)  | Телефон компании                        |
| location_id  | Integer     | Внешний ключ на `locations.location_id` |
</details>

<details>
<summary>Таблица software</summary>

### Таблица: `software`
| Колонка          | Тип данных  | Описание                                         |
|:-----------------|:------------|:-------------------------------------------------|
| software_id      | Integer     | Первичный ключ, автоинкремент                    |
| office_type      | String(100) | Тип офисного ПО                                  |
| office_key       | String(100) | Ключ лицензии офисного ПО                        |
| os_type          | String(100) | Тип операционной системы                         |
| os_key           | String(100) | Ключ лицензии ОС                                 |
| remote_control   | String(150) | ПО удалённого управления                         |
| admin_permission | Boolean     | Наличие прав администратора (по умолчанию False) |
| who_installed    | Integer     | Внешний ключ на `users.user_id` (кто установил)  |
| installed_at     | DateTime    | Дата установки                                   |
| comment          | Text        | Комментарий                                      |
| created_at       | DateTime    | Дата создания                                    |
| updated_at       | DateTime    | Дата обновления                                  |
</details>

<details>
<summary>Таблица locations</summary>

### Таблица: `locations`
| Колонка     | Тип данных  | Описание                                                    |
|:------------|:------------|:------------------------------------------------------------|
| location_id | Integer     | Первичный ключ, автоинкремент                               |
| country     | String(100) | Страна (по умолчанию "Страна")                              |
| city        | String(100) | Город (по умолчанию "Город")                                |
| address     | String(255) | Адрес (по умолчанию "Улица и номер дома")                   |
| room        | String(50)  | Помещение/кабинет (по умолчанию "Номер помещения/кабинета") |
| floor       | String(10)  | Этаж (по умолчанию "Этаж")                                  |
</details>

<details>
<summary>Таблица users</summary>

### Таблица: `users`
| Колонка       | Тип данных  | Описание                                           |
|:--------------|:------------|:---------------------------------------------------|
| user_id       | Integer     | Первичный ключ, автоинкремент                      |
| user_tab_id   | String(50)  | Табельный номер (уникальный, индекс)               |
| owner         | String(150) | ФИО на русском (не nullable, индекс)               |
| user_en_name  | String(150) | ФИО на английском                                  |
| role          | String(40)  | Роль пользователя                                  |
| user_position | String(100) | Должность                                          |
| department    | String(100) | Отдел (индекс)                                     |
| email         | String(100) | Email (уникальный, не nullable, индекс)            |
| phone         | String(50)  | Телефон                                            |
| is_active     | Boolean     | Статус активности (по умолчанию True, не nullable) |
| created_at    | DateTime    | Дата создания                                      |
| updated_at    | DateTime    | Дата обновления                                    |
</details>

<details>
<summary>Таблица vendors</summary>

### Таблица: `vendors`
| Колонка         | Тип данных  | Описание                                                               |
|:----------------|:------------|:-----------------------------------------------------------------------|
| vendor_id       | Integer     | Первичный ключ, автоинкремент                                          |
| name            | String(255) | Название вендора/поставщика (не nullable, индекс)                      |
| vendor_class_id | Integer     | Внешний ключ на `vendor_classes.vendor_class_id` (не nullable, индекс) |
| company_id      | Integer     | Внешний ключ на `companies.company_id`                                 |
| created_by      | Integer     | Внешний ключ на `users.user_id` (создатель, не nullable)               |
| created_at      | DateTime    | Дата создания                                                          |
</details>

<details>
<summary>Таблица vendor_classes</summary>

### Таблица: `vendor_classes`
| Колонка         | Тип данных  | Описание                                                      |
|:----------------|:------------|:--------------------------------------------------------------|
| vendor_class_id | Integer     | Первичный ключ, автоинкремент, индекс                         |
| name            | String(100) | Название класса контрагента (не nullable, уникальное, индекс) |
| created_at      | DateTime    | Дата создания (не nullable)                                   |
</details>

<details>
<summary>Таблица warehouses</summary>

### Таблица: `warehouses`
| Колонка      | Тип данных  | Описание                                                |
|:-------------|:------------|:--------------------------------------------------------|
| warehouse_id | Integer     | Первичный ключ, автоинкремент, индекс                   |
| name         | String(100) | Название склада (не nullable, уникальное, индекс)       |
| location_id  | Integer     | Внешний ключ на `locations.location_id` (индекс)        |
| prepared_by  | Integer     | Внешний ключ на `users.user_id` (ответственный, индекс) |
</details>


### Схема взаимосвязей таблиц

```mermaid
erDiagram
    %% Справочники и основные сущности
    AssetType ||--o{ Asset : "has"
    AssetType ||--o{ AssetClass : "has"
    
    VendorClass ||--o{ Vendor : "has"
    
    Company ||--o{ Vendor : "has"
    Location ||--o{ Company : "located_at"
    Location ||--o{ Asset : "located_at"
    Location ||--o{ Warehouse : "located_at"
    
    User ||--o{ Asset : "prepared_by/checked_by"
    User ||--o{ AssetCatalog : "owns/created_by"
    User ||--o{ Software : "installed_by"
    User ||--o{ Vendor : "created_by"
    User ||--o{ AssetClass : "created_by/updated_by"
    User ||--o{ AssetModel : "created_by/updated_by"
    User ||--o{ Warehouse : "managed_by"
    
    Vendor ||--o{ Asset : "manufacturer/vendor"
    
    AssetClass ||--o{ AssetModel : "has"
    AssetModel ||--o{ AssetCatalog : "has"
    AssetClass ||--o{ AssetCatalog : "has"
    
    Asset ||--o{ Asset : "parent/children (self-ref)"
    Asset ||--o| AssetCatalog : "linked_to"
    Asset ||--o| Software : "uses"
    
    Warehouse ||--o{ AssetCatalog : "stored_in"

    %% Определение таблиц и ключевых полей для наглядности
    Asset {
        int asset_id PK
        int asset_type_id FK
        int location_id FK
        int manufacturer_id FK
        int vendor_id FK
        int parent_id FK
        int prepared_by FK
        int checked_by FK
        int software_id FK
        string inventory_id
        string serial_number
    }

    AssetType {
        int asset_type_id PK
        string name
    }

    AssetClass {
        int class_id PK
        int class_type_id FK
        string class_name
        int created_by FK
        int updated_by FK
    }

    AssetModel {
        int model_id PK
        int class_id FK
        string model_name
        int created_by FK
        int updated_by FK
    }

    AssetCatalog {
        int catalog_id PK
        int class_id FK
        int model_id FK
        int asset_id FK
        int owner_id FK
        int warehouse_id FK
        int created_by FK
    }

    Vendor {
        int vendor_id PK
        int vendor_class_id FK
        int company_id FK
        int created_by FK
        string name
    }

    VendorClass {
        int vendor_class_id PK
        string name
    }

    Company {
        int company_id PK
        int location_id FK
        string company_name
    }

    Location {
        int location_id PK
        string country
        string city
        string address
    }

    User {
        int user_id PK
        string user_tab_id
        string email
        string owner
    }

    Software {
        int software_id PK
        int who_installed FK
        string os_type
        string office_type
    }

    Warehouse {
        int warehouse_id PK
        int location_id FK
        int prepared_by FK
        string name
    }
```

### Описание основных связей:

1.  **Asset (Активы)**:
    *   Связан с `AssetType` (тип актива).
    *   Связан с `Location` (местоположение).
    *   Связан с `Vendor` дважды: как `manufacturer_id` (производитель) и `vendor_id` (поставщик).
    *   Имеет самореференцию `parent_id` для иерархии (комплектующие внутри основного устройства).
    *   Связан с `User` через `prepared_by` и `checked_by`.
    *   Связан с `Software` (установленное ПО на активе).
    *   Связан с `AssetCatalog` (один к одному, запись в каталоге соответствует физическому активу).

2.  **AssetCatalog (Каталог активов)**:
    *   Связывает конкретный `Asset` с его классом (`AssetClass`) и моделью (`AssetModel`).
    *   Указывает владельца (`User`) и место хранения (`Warehouse`).

3.  **Иерархия типов**:
    *   `AssetType` -> `AssetClass` -> `AssetModel`.
    *   Тип (например, "Компьютеры") содержит Классы (например, "Ноутбуки"), которые содержат Модели (например, "ThinkPad X1").

4.  **Контрагенты**:
    *   `Vendor` (конкретный поставщик/бренд) ссылается на `VendorClass` (роль: производитель, поставщик и т.д.) и опционально на `Company` (юридическое лицо).
    *   `Company` привязана к `Location` (адрес юрлица).

5.  **Пользователи и Локации**:
    *   `User` участвует во многих таблицах как создатель, ответственный или владелец.
    *   `Location` используется в `Asset`, `Company` и `Warehouse` для указания физического адреса.





## Описание API эндпоинтов

### Роутер: Assets (`/assets`)
| Метод  | URL                             | Описание                                                                                                                                                                    |
|:-------|:--------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| POST   | `/assets/`                      | Создать новый актив. Проверяет уникальность инвентарного и серийного номеров, существование родителя, производителя, поставщика, типа актива и ответственных пользователей. |
| GET    | `/assets/`                      | Получить список активов с пагинацией (`skip`, `limit`) и фильтрацией по статусу (`asset_status`), типу (`type_id`) и наличию удаления (`deleted`).                          |
| GET    | `/assets/{asset_id}`            | Получить полную информацию об активе по ID. Возвращает 404, если актив не найден или удален.                                                                                |
| PATCH  | `/assets/{asset_id}`            | Обновить данные актива. Проверяет уникальность изменяемых полей (инвентарный номер, серийный номер) и валидность родительского актива. Запрещает циклические ссылки.        |
| POST   | `/assets/{asset_id}/deactivate` | Деактивация актива (мягкое удаление). Устанавливает дату удаления.                                                                                                          |
| POST   | `/assets/{asset_id}/activate`   | Активация актива (восстановление после мягкого удаления).                                                                                                                   |
| DELETE | `/assets/{asset_id}/hard`       | Жесткое удаление актива. Требует предварительной деактивации. Удаляет актив и всех его дочерних элементов рекурсивно.                                                       |
| GET    | `/assets/{asset_id}/children`   | Получить всех дочерних активов рекурсивно (плоский список) с опциональной глубиной вложенности (`max_depth`).                                                               |


### Роутер: Asset Types (`/assets-types`)
| Метод  | URL                             | Описание                                                                           |
|:-------|:--------------------------------|:-----------------------------------------------------------------------------------|
| POST   | `/assets-types/`                | Создать новый тип актива. Название должно быть уникальным.                         |
| GET    | `/assets-types/`                | Получить список всех типов активов.                                                |
| GET    | `/assets-types/{asset_type_id}` | Получить тип актива по ID.                                                         |
| PATCH  | `/assets-types/{asset_type_id}` | Обновить тип актива по ID.                                                         |
| DELETE | `/assets-types/{asset_type_id}` | Удалить тип актива по ID. Не позволяет удалить, если есть ссылки из других таблиц. |


### Роутер: Catalog (`/catalog`)
| Метод  | URL                                | Описание                                                                                             |
|:-------|:-----------------------------------|:-----------------------------------------------------------------------------------------------------|
| POST   | `/catalog/classes`                 | Создать новый класс оборудования.                                                                    |
| GET    | `/catalog/classes`                 | Получить список классов оборудования с пагинацией.                                                   |
| GET    | `/catalog/classes/{class_id}`      | Получить класс оборудования по ID.                                                                   |
| PATCH  | `/catalog/classes/{class_id}`      | Обновить класс оборудования по ID.                                                                   |
| DELETE | `/catalog/classes/{class_id}`      | Удалить класс оборудования по ID.                                                                    |
| POST   | `/catalog/models`                  | Создать новую модель оборудования.                                                                   |
| GET    | `/catalog/models`                  | Получить список моделей оборудования с пагинацией и опциональной фильтрацией по классу (`class_id`). |
| GET    | `/catalog/models/{model_id}`       | Получить модель оборудования по ID.                                                                  |
| PATCH  | `/catalog/models/{model_id}`       | Обновить модель оборудования по ID.                                                                  |
| GET    | `/catalog/models/{model_id}/stats` | Получить статистику (количество) активов для конкретной модели.                                      |
| POST   | `/catalog/items`                   | Добавить запись в каталог (связь актива с моделью и классом).                                        |
| GET    | `/catalog/items`                   | Получить список записей каталога с пагинацией.                                                       |
| GET    | `/catalog/items/{catalog_id}`      | Получить запись каталога по ID.                                                                      |


### Роутер: Companies (`/companies`)
| Метод  | URL                       | Описание                                                                 |
|:-------|:--------------------------|:-------------------------------------------------------------------------|
| POST   | `/companies/`             | Создать новую компанию. Проверяет уникальность названия.                 |
| GET    | `/companies/`             | Получить список компаний с пагинацией (`skip`, `limit`).                 |
| GET    | `/companies/{company_id}` | Получить компанию по ID.                                                 |
| PATCH  | `/companies/{company_id}` | Обновить данные компании. Проверяет уникальность названия при изменении. |
| DELETE | `/companies/{company_id}` | Удалить компанию по ID.                                                  |


### Роутер: Assets Excel (`/assets/excel`)
| Метод | URL                      | Описание                                                                         |
|:------|:-------------------------|:---------------------------------------------------------------------------------|
| GET   | `/assets/excel/export`   | Экспорт списка активов в файл Excel. Поддерживает пагинацию (`skip`, `limit`).   |
| GET   | `/assets/excel/template` | Скачать шаблон Excel файла для импорта активов.                                  |
| POST  | `/assets/excel/import`   | Импортировать активы из загруженного Excel файла. Возвращает результаты импорта. |


### Роутер: Vendors (`/vendors`)
| Метод  | URL                    | Описание                                                                                                                               |
|:-------|:-----------------------|:---------------------------------------------------------------------------------------------------------------------------------------|
| POST   | `/vendors/`            | Создать нового вендора или поставщика.                                                                                                 |
| GET    | `/vendors/`            | Получить список вендоров с пагинацией (`skip`, `limit`) и фильтрацией по классу вендора (`vendor_class_id`) и компании (`company_id`). |
| GET    | `/vendors/{vendor_id}` | Получить информацию о вендоре по ID.                                                                                                   |
| PATCH  | `/vendors/{vendor_id}` | Обновить данные вендора по ID.                                                                                                         |
| DELETE | `/vendors/{vendor_id}` | Удалить вендора по ID.                                                                                                                 |


### Роутер: Locations (`/locations`)
| Метод  | URL                        | Описание                                                                                                      |
|:-------|:---------------------------|:--------------------------------------------------------------------------------------------------------------|
| POST   | `/locations/`              | Создать новую локацию (адрес/помещение).                                                                      |
| GET    | `/locations/`              | Получить список локаций с пагинацией (`skip`, `limit`) и фильтрацией по городу (`city`) и стране (`country`). |
| GET    | `/locations/{location_id}` | Получить полную информацию о локации по ID.                                                                   |
| PATCH  | `/locations/{location_id}` | Обновить данные локации по ID.                                                                                |
| DELETE | `/locations/{location_id}` | Удалить локацию по ID.                                                                                        |


### Роутер: Vendor Classes (`/vendor-classes`)
| Метод  | URL                                 | Описание                                                                                               |
|:-------|:------------------------------------|:-------------------------------------------------------------------------------------------------------|
| POST   | `/vendor-classes/`                  | Создать новый класс вендора (например, "Производитель", "Поставщик"). Проверяет уникальность названия. |
| GET    | `/vendor-classes/`                  | Получить список классов вендоров с пагинацией (`skip`, `limit`).                                       |
| GET    | `/vendor-classes/{vendor_class_id}` | Получить класс вендора по ID.                                                                          |
| PATCH  | `/vendor-classes/{vendor_class_id}` | Обновить класс вендора. Проверяет уникальность названия при изменении.                                 |
| DELETE | `/vendor-classes/{vendor_class_id}` | Удалить класс вендора по ID.                                                                           |


### Роутер: Users (`/users`)
| Метод  | URL                           | Описание                                                                                                                                |
|:-------|:------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------|
| POST   | `/users/`                     | Создать нового пользователя (сотрудника). Проверяет уникальность email и табельного номера.                                             |
| GET    | `/users/`                     | Получить список пользователей с пагинацией (`skip`, `limit`) и фильтрацией по отделу (`department`) и статусу активности (`is_active`). |
| GET    | `/users/{user_id}`            | Получить пользователя по ID.                                                                                                            |
| PATCH  | `/users/{user_id}`            | Обновить данные пользователя. Проверяет уникальность email и табельного номера при изменении.                                           |
| POST   | `/users/{user_id}/activate`   | Активировать пользователя. Возвращает ошибку, если пользователь уже активен.                                                            |
| POST   | `/users/{user_id}/deactivate` | Деактивировать пользователя. Возвращает ошибку, если пользователь уже деактивирован.                                                    |
| DELETE | `/users/{user_id}`            | Жестко удалить пользователя. Разрешено только для деактивированных пользователей.                                                       |


### Роутер: Software (`/software`)
| Метод  | URL                              | Описание                                                                                                                                   |
|:-------|:---------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------|
| POST   | `/software/`                     | Создать новую запись о программном обеспечении.                                                                                            |
| GET    | `/software/`                     | Получить список ПО с пагинацией (`skip`, `limit`) и фильтрацией по наличию прав администратора (`admin_permission`) и типу ОС (`os_type`). |
| GET    | `/software/{software_id}`        | Получить запись о ПО по ID.                                                                                                                |
| PATCH  | `/software/{software_id}`        | Обновить запись о ПО по ID.                                                                                                                |
| DELETE | `/software/{software_id}`        | Удалить запись о ПО. Запрещено, если ПО привязано к активным активам.                                                                      |
| GET    | `/software/{software_id}/assets` | Получить список активов, на которых установлено данное ПО.                                                                                 |


### Роутер: Warehouses (`/warehouses`)
| Метод  | URL                          | Описание                                                                         |
|:-------|:-----------------------------|:---------------------------------------------------------------------------------|
| POST   | `/warehouses/`               | Создать новый склад. Проверяет уникальность названия склада.                     |
| GET    | `/warehouses/`               | Получить список всех складов с пагинацией (`skip`, `limit`).                     |
| GET    | `/warehouses/{warehouse_id}` | Получить полную информацию о складе по ID. Возвращает 404, если склад не найден. |
| PATCH  | `/warehouses/{warehouse_id}` | Обновить данные склада по ID. Проверяет уникальность названия при изменении.     |
| DELETE | `/warehouses/{warehouse_id}` | Удалить склад по ID. Возвращает 204 при успешном удалении.                       |