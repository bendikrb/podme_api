Introduction
============

The ``podme-api`` library provides an asynchronous interface to interact with the PodMe Web API. It allows users to fetch podcast data, episodes, and more using a variety of methods.

Requirements
------------

podme-api requires Python 3.11 and above.

Usage
-----

To use ``podme-api``, you need to create an instance of the class and call its methods asynchronously.

Example:

.. code-block:: python

    import asyncio
    from podme_api import PodMeClient, PodMeUserCredentials

    async def main():
        username = "testuser@example.com"
        password = "qwerty123"
        user_creds = PodMeUserCredentials(username, password)
        async with PodMeDefaultAuthClient(user_credentials=user_creds) as auth_client:
            async with PodMeClient(auth_client=auth_client) as client:
                podcasts = await client.get_user_podcasts()
                for podcast in podcasts:
                    print(podcast.title)

    asyncio.run(main())


Logging
-------

The library uses a logger named ``podme_api`` to log debug information. You can configure this logger to capture logs as needed.
