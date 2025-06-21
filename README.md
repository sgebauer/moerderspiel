Das Moerderspiel
================

This project is a rewrite of the original [Moerderspiel](https://github.com/orithena/moerderspiel) software.
It is currently work in progress and is not fully usable yet.

Building and Running Locally
----------------------------

```shell
podman build -t moerderspiel .
podman run --rm -it --volume=moerderspiel-data:/data --volume=moerderspiel-cache:/cache \
    --env=BASE_URL=https://moerderspiel.example.com --env=SECRET_KEY=verysecret \
    --env=EMAIL_SMTP_HOST=mail.example.com --env=EMAIL_FROM=moerderspiel@example.com \
    --env=EMAIL_HELO_HOSTNAME=example.com --env=ADMIN_PASSWORD=adminpassword moerderspiel-ng
```

Admin Interface (Optional)
---------------------------

The application includes an optional password-protected admin interface. When enabled, it provides:

* Game management (view, edit, delete games with confirmation)
* Player overview for each game
* Quick access to game statistics
* Gamemaster password reset functionality
* Future: Logging and monitoring capabilities

**To enable admin access:** Set the `ADMIN_PASSWORD` environment variable to your desired admin password.
**If not set or empty:** The admin interface will be disabled and admin routes will return 404 errors.

Project status
--------------

The project is complete enough that it can be used for offline ("paper only") and hybrid-online ("paper + online
recording") games:
* The game master can create games, sign up players, and generate missions
* Players can sign up for games, check recorded murders, and record new ones
* Administrators can manage games through a protected web interface

However, the database schema is not yet final. This is also the reason why there is no public test instance yet.
Check the [issue tracker](https://github.com/sgebauer/moerderspiel/issues) for missing features.


Third Party Licenses
--------------------

* Icons in `moerderspiel/web/static/img/icons` are from pictogrammers.com and licensed unter the Apache 2.0 License.
