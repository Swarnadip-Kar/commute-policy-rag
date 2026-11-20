import argparse

from .auth import issue_token


def main():
    ap = argparse.ArgumentParser(description='Print a development JWT for one company')
    ap.add_argument('company')
    ap.add_argument('--admin', action='store_true', help='role=admin, needed for /admin/policies')
    ap.add_argument('--ttl', type=int, default=3600, help='lifetime in seconds')
    args = ap.parse_args()
    print(issue_token(args.company, role='admin' if args.admin else 'employee', ttl_s=args.ttl))


if __name__ == '__main__':
    main()
