"""
CRUD операции для интеграции с 1С-ЗУП
"""

from app.database.zup.crud_zup_employees import (
    get_employee_by_guid,
    get_employee_by_id,
    get_employee_by_login_or_email,
    create_employee,
    update_employee,
    get_employees_list,
    upsert_employee
)

from app.database.zup.crud_zup_positions import (
    get_position_by_guid,
    create_position,
    update_position,
    get_positions_list,
    upsert_position
)

from app.database.zup.crud_zup_departments import (
    get_department_by_guid,
    create_department,
    update_department,
    get_departments_list,
    upsert_department
)

from app.database.zup.crud_zup_managers import (
    get_manager_by_id,
    create_manager,
    get_managers_list,
    upsert_manager
)

from app.database.zup.crud_zup_assignments import (
    get_assignment_by_id,
    create_assignment,
    get_assignments_list,
    upsert_assignment
)

from app.database.zup.crud_zup_reports import (
    create_report,
    get_reports_list
)

__all__ = [
    # Employees
    "get_employee_by_guid",
    "get_employee_by_id",
    "get_employee_by_login_or_email",
    "create_employee",
    "update_employee",
    "get_employees_list",
    "upsert_employee",

    # Positions
    "get_position_by_guid",
    "create_position",
    "update_position",
    "get_positions_list",
    "upsert_position",

    # Departments
    "get_department_by_guid",
    "create_department",
    "update_department",
    "get_departments_list",
    "upsert_department",

    # Managers
    "get_manager_by_id",
    "create_manager",
    "get_managers_list",
    "upsert_manager",

    # Assignments
    "get_assignment_by_id",
    "create_assignment",
    "get_assignments_list",
    "upsert_assignment",

    # Reports
    "create_report",
    "get_reports_list"
]