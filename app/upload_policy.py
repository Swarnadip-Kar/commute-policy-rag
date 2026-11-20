import sys
from pathlib import Path

import httpx

from .auth import issue_token


def main():
    if len(sys.argv) != 3:
        sys.exit('usage: python -m app.upload_policy <company> <policy-file> [BASE_URL via env API_URL]')
    company, path = sys.argv[1], sys.argv[2]
    import os
    base = os.getenv('API_URL', 'http://localhost:8000')
    token = issue_token(company, role='admin', user='policy-admin')
    r = httpx.post(f'{base}/admin/policies', timeout=60,
                   headers={'Authorization': f'Bearer {token}'},
                   json={'company': company, 'text': Path(path).read_text()})
    print(r.status_code, r.text)
    sys.exit(0 if r.status_code == 200 else 1)


if __name__ == '__main__':
    main()
