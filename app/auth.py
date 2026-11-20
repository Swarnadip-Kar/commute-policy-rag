import time

import jwt
from fastapi import Depends, Header, HTTPException

from . import config
from .chunking import SLUG


def issue_token(company, role='employee', user='demo-user', ttl_s=3600):
    now = int(time.time())
    claims = {'sub': user, 'company': company, 'role': role, 'iat': now, 'exp': now + ttl_s}
    return jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALGO)


def _verify(authorization):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='missing bearer token')
    try:
        claims = jwt.decode(authorization[7:], config.JWT_SECRET,
                            algorithms=[config.JWT_ALGO],
                            options={'require': ['exp', 'sub', 'company']})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail='invalid or expired token')
    company = claims['company']
    if not isinstance(company, str) or not SLUG.match(company):
        raise HTTPException(status_code=401, detail='invalid company claim')
    return claims


def claims_dep(authorization: str | None = Header(default=None)):
    return _verify(authorization)


def require_company(claims: dict = Depends(claims_dep)):
    return claims['company']


def require_admin(claims: dict = Depends(claims_dep)):
    if claims.get('role') != 'admin':
        raise HTTPException(status_code=403, detail='admin only')
    return claims