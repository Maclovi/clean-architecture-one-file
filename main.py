from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import (
    DishkaRoute,
    FastapiProvider,
    FromDishka,
    setup_dishka,
)
from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic


# --------------- DOMAIN LAYER ---------------
@dataclass
class User:
    username: str
    password: str


# --------------- DOMAIN LAYER ---------------


# --------------- APPLICATION LAYER ---------------
class ApplicationError(BaseException):
    pass


class UserNotFoundError(ApplicationError):
    pass


class UserNotAuthenticatedError(ApplicationError):
    pass


class HTTPBasicCredentialsProtocol(Protocol):
    username: str
    password: str


class UserRepositoryProtocol(Protocol):
    @abstractmethod
    def with_username(self, username: str) -> User | None: ...


class AccessService:
    def __init__(
        self,
        credentials: HTTPBasicCredentialsProtocol,
        user_repository: UserRepositoryProtocol,
    ) -> None:
        self._credentials = credentials
        self._user_repository = user_repository

    def check_auth(self) -> User | None:
        data = self._credentials
        repo = self._user_repository
        user: User | None = repo.with_username(data.username)
        if user is None:
            raise UserNotFoundError
        if user.password != data.password:
            raise UserNotAuthenticatedError
        return user


# --------------- APPLICATION LAYER ---------------


# --------------- PRESENTATION LAYER ---------------
router = APIRouter(route_class=DishkaRoute)


@router.get("/")
async def index() -> FileResponse:
    return FileResponse("public/index.html")


@router.get("/protected_resource/")
async def get_protected_resource(access_service: FromDishka[AccessService]) -> str:
    try:
        access_service.check_auth()
    except (UserNotFoundError, UserNotAuthenticatedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        ) from exc
    return "You got my secret, welcome!"


# --------------- PRESENTATION LAYER ---------------


# --------------- INFRASTRUCTURE LAYER ---------------
class UserRepository(UserRepositoryProtocol):
    def __init__(self, database: list[User]) -> None:
        self._database = database

    def with_username(self, username: str) -> User | None:
        user = next(filter(lambda u: u.username == username, self._database), None)
        return user


class DBProvider(Provider):
    @provide(scope=Scope.APP)
    def database(self) -> list[User]:
        return [
            User(username="user1", password="pass1"),
            User(username="user2", password="pass2"),
            User(username="user3", password="pass3"),
            User(username="user4", password="pass4"),
            User(username="user5", password="pass5"),
        ]

    user_repository = provide(
        UserRepository, scope=Scope.REQUEST, provides=UserRepositoryProtocol
    )


def service_provider() -> Provider:
    security = HTTPBasic()
    provider = Provider()
    provider.provide(AccessService, scope=Scope.REQUEST)
    provider.provide(
        security, scope=Scope.REQUEST, provides=HTTPBasicCredentialsProtocol
    )
    return provider


def setup_providers() -> list[Provider]:
    return [DBProvider(), FastapiProvider(), service_provider()]


# --------------- INFRASTRUCTURE LAYER ---------------


# --------------- ENTRYPOINT/MAIN ---------------
def create_app() -> FastAPI:
    container = make_async_container(*setup_providers())
    app = FastAPI(title="Course", description="Studying")
    app.include_router(router)
    setup_dishka(container, app)
    return app


# --------------- ENTRYPOINT/MAIN ---------------
