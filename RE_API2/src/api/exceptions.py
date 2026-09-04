class AppError(Exception):
    status_code = 400
    description = "Application error occurred."