from fastapi import HTTPException, status


class GameException(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundError(GameException):
    def __init__(self, resource: str, identifier: int | str):
        super().__init__(
            detail=f"{resource} with id '{identifier}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ValidationError(GameException):
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class CombatError(GameException):
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class InventoryError(GameException):
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)
