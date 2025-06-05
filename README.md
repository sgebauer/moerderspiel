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
    --env=EMAIL_HELO_HOSTNAME=example.com moerderspiel-ng
```

Project status
--------------

The project is complete enough that it can be used for offline ("paper only") and hybrid-online ("paper + online
recording") games:
* The game master can create games, sign up players, and generate missions
* Players can sign up for games, check recorded murders, and record new ones

However, the database schema is not yet final. This is also the reason why there is no public test instance yet.
Check the [issue tracker](https://github.com/sgebauer/moerderspiel/issues) for missing features.


Third Party Licenses
--------------------

* Icons in `moerderspiel/web/static/img/icons` are from pictogrammers.com and licensed unter the Apache 2.0 License.