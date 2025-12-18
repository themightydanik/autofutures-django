from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token
from channels.db import database_sync_to_async


@database_sync_to_async
def get_user(token_key):
    try:
        token = Token.objects.select_related("user").get(key=token_key)
        return token.user
    except Token.DoesNotExist:
        return AnonymousUser()


class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query = parse_qs(query_string)

        token = query.get("token")

        if token:
            scope["user"] = await get_user(token[0])
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)
