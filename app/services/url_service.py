import logging
from dataclasses import dataclass

from app.cache import get_existing_code, get_original_url, invalidate_code, set_url
from app.models.url import URL, User, generate_code

logger = logging.getLogger(__name__)

MAX_RETRIES = 10  


@dataclass
class ShortenResult:
    short_code: str
    original_url: str
    click_count: int
    is_active: bool
    created_at: str
    is_new: bool  


class URLNotFoundError(Exception):
    pass


class URLInactiveError(Exception):
    pass


class CodeGenerationError(Exception):
    pass



def shorten(
    original_url: str,
    user_id: int | None = None,
    allow_duplicate: bool = False,
) -> ShortenResult:


    if not allow_duplicate:
        existing_code = _find_existing_code(original_url)
        if existing_code:
            url_row = URL.get(URL.short_code == existing_code)
            logger.info("dedup hit short_code=%s original_url=%s", existing_code, original_url)
            return ShortenResult(
                short_code=url_row.short_code,
                original_url=url_row.original_url,
                click_count=url_row.click_count,
                is_active=url_row.is_active,
                created_at=url_row.created_at.isoformat(),
                is_new=False,
            )

    user = None
    if user_id is not None:
        try:
            user = User.get_by_id(user_id)
        except User.DoesNotExist:
            raise ValueError(f"User {user_id} not found")
        if not user.is_active:
            raise ValueError("User account is inactive")

    short_code = _generate_unique_code()

    url_row = URL.create(
        original_url=original_url,
        short_code=short_code,
        user=user,
    )

    set_url(short_code, original_url)

    logger.info("created short_code=%s original_url=%s", short_code, original_url)
    return ShortenResult(
        short_code=url_row.short_code,
        original_url=url_row.original_url,
        click_count=url_row.click_count,
        is_active=url_row.is_active,
        created_at=url_row.created_at.isoformat(),
        is_new=True,
    )


def resolve(short_code: str) -> str:

    cached = get_original_url(short_code)
    if cached:
        logger.info("cache hit short_code=%s", short_code)
        URL.update(click_count=URL.click_count + 1).where(
            URL.short_code == short_code
        ).execute()
        return cached

    try:
        url_row = URL.get(URL.short_code == short_code)
    except URL.DoesNotExist:
        raise URLNotFoundError(short_code)

    if not url_row.is_active:
        raise URLInactiveError(short_code)

    set_url(short_code, url_row.original_url)

    URL.update(click_count=URL.click_count + 1).where(URL.id == url_row.id).execute()

    logger.info("db hit short_code=%s", short_code)
    return url_row.original_url


def deactivate(short_code: str) -> None:
    try:
        url_row = URL.get(URL.short_code == short_code)
    except URL.DoesNotExist:
        raise URLNotFoundError(short_code)

    url_row.is_active = False
    url_row.save()

    invalidate_code(short_code, url_row.original_url)
    logger.info("deactivated short_code=%s", short_code)


def _find_existing_code(original_url: str) -> str | None:

    code = get_existing_code(original_url)
    if code:
        return code

    try:
        url_row = URL.get(
            (URL.original_url == original_url) & (URL.is_active == True)
        )
        set_url(url_row.short_code, original_url)
        return url_row.short_code
    except URL.DoesNotExist:
        return None


def _generate_unique_code() -> str:

    for attempt in range(1, MAX_RETRIES + 1):
        code = generate_code()

        if get_original_url(code) is not None:
            logger.debug("code collision in Redis attempt=%d code=%s", attempt, code)
            continue

        if URL.select().where(URL.short_code == code).exists():
            logger.debug("code collision in DB attempt=%d code=%s", attempt, code)
            continue

        return code  

    raise CodeGenerationError(
        f"Could not generate a unique code after {MAX_RETRIES} attempts. "
        "This is astronomically unlikely — check your DB/cache state."
    )
