# remailer
## A PGP-enforcing newsletter implementation

`remailer` is a newsletter implementation that relies on PGP signatures for authentication.

For the sender, posting to the newsletter is absolutely transparent: compose an email, sign it, send it.

The subscriber gets the usual mailing list options: subscribe, verify subscription, unsubscribe, subscription details, as well as transparent sender verification via PGP/GPG.

To use it on your webserver, you need to do the following:

  1. Copy `remailer.cfg.sample` to `remailer.cfg` and edit it according to your needs;
  2. Copy the `sample` directory to the list's name and edit the contents to reflect your list's properties.
  3. Add the PGP keys of the persons allowed to post to the keyring you have referenced in `remailer.cfg`;
  4. Add the `From:` string of the person allowed to post to the `list_owner` key in the configuration file;
  5. Create a mail filter which pipes incoming messages for the newsletter to the `remailer.py` script. Examples for EXIM:

__On private hosting, with a dedicated `remailer` user:__

In `/etc/aliases`:

    list: remailer
    list-request: remailer

In `/home/remailer/.forward` (or equivalent):

    # Exim filter
    if not delivered then
        pipe "/path/to/remailer.py"
    endif

__On private hosting, without a dedicated `remailer` user:__

In `/etc/aliases`:

    list: |/path/to/remailer.py
    list-request: |/path/to/remailer.py

Since it's not immediately obvious which user ends up running that script, make sure to test your configuration to get your file permissions right.

__For a shared hosting environment:__

In your `.forward`:

    # Exim filter
    if $local_part is "list" or $local_part is "list-request" then
        pipe "/path/to/remailer.py"
    endif

__User management:__

To subscribe to the newsletter, have the user send an email with the subject "subscribe" to the list-request address. They will receive a verification email to which they will need to reply.

To unsubscribe, have the user send an email with the subject "unsubscribe" to the list-request address.

To see the details of their subscription, have the user send an email with the subject "details" to the list-request address.

Invalid emails (those with unrecognized commands or from unauthorized senders) are saved in the script's working directory for future examination.

***

This program is free software, released under the Apache License, Version 2.0. See the LICENSE file for more information.

The program's canonical project page resides at https://github.com/simon-v/remailer/

I gratefully accept appreciation for my work in material form at __[bitcoincash:qr9mj4r9sq3urkjl6hhspeyjj62l3k3mzckaqq0kj8](bitcoincash:qr9mj4r9sq3urkjl6hhspeyjj62l3k3mzckaqq0kj8)__.
