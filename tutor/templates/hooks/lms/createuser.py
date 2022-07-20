#!/usr/bin/env python

import argparse
import subprocess


def main():
    parser = argparse.ArgumentParser(description="Create an LMS user")
    parser.add_argument("username")
    parser.add_argument("email")
    parser.add_argument("--staff", action="store_true")
    parser.add_argument("--superuser", action="store_true")
    parser.add_argument("--password", default="")
    parser.set_defaults(func=run_create_user)
    args = parser.parse_args()
    args.func(args)


def run_create_user(args):
    opts = []
    username = args["username"]
    email = args["email"]
    password = args["password"]
    if args["superuser"]:
        opts.append("--superuser")
    if args["staff"]:
        opts.append("--staff")
    subprocess.check_call(
        [
            "./manage.py",
            "lms",
            "manage_user",
            *opts,
            username,
            email,
        ]
    )
    if args["password"]:
        subprocess.check_call(
            "./manage.py",
            "lms",
            "shell",
            "-c",
            ";".join(
                [
                    "from django.contrib.auth import get_user_model",
                    f"u = get_user_model().get(username='{username}",
                    f"u.set_password('{password}')",
                    "u.save()",
                ]
            ),
        )
    else:
        subprocess.check_call(["./manage.py", "lms", "changepassword", username])


if __name__ == "__main__":
    main()
